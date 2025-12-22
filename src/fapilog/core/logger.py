"""
Async logging API surface.

For story 2.1a we only define the minimal surface used by tests and
serialization. The full pipeline will be expanded in later stories.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading
import time
from dataclasses import dataclass
from typing import Any, Iterable, cast

from ..metrics.metrics import MetricsCollector
from ..plugins.enrichers import BaseEnricher
from ..plugins.redactors import BaseRedactor, redact_in_order
from .concurrency import NonBlockingRingQueue
from .events import LogEvent
from .serialization import (
    SerializedView,
    serialize_envelope,
    serialize_mapping_to_json_bytes,
)


class AsyncLogger:
    """Minimal async logger facade used by the core pipeline tests."""

    async def log_many(self, events: Iterable[LogEvent]) -> int:
        """Placeholder batching API for later pipeline integration."""
        return sum(1 for _ in events)


@dataclass
class DrainResult:
    submitted: int
    processed: int
    dropped: int
    retried: int
    queue_depth_high_watermark: int
    flush_latency_seconds: float


class SyncLoggerFacade:
    """Sync facade that enqueues log calls to a background async worker.

    - Non-blocking in async contexts
    - Backpressure policy: wait up to configured ms, then drop
    - Batching: size and time based
    """

    def __init__(
        self,
        *,
        name: str | None,
        queue_capacity: int,
        batch_max_size: int,
        batch_timeout_seconds: float,
        backpressure_wait_ms: int,
        drop_on_full: bool,
        sink_write: Any,
        sink_write_serialized: Any | None = None,
        enrichers: list[BaseEnricher] | None = None,
        metrics: MetricsCollector | None = None,
        exceptions_enabled: bool = True,
        exceptions_max_frames: int = 50,
        exceptions_max_stack_chars: int = 20000,
        serialize_in_flush: bool = False,
    ) -> None:
        self._name = name or "root"
        self._queue = NonBlockingRingQueue[dict[str, Any]](capacity=queue_capacity)
        self._queue_high_watermark = 0
        self._batch_max_size = int(batch_max_size)
        self._batch_timeout_seconds = float(batch_timeout_seconds)
        self._backpressure_wait_ms = int(backpressure_wait_ms)
        self._drop_on_full = bool(drop_on_full)
        self._sink_write = sink_write
        self._sink_write_serialized = sink_write_serialized
        self._metrics = metrics
        # Store enrichers with explicit type
        self._enrichers: list[BaseEnricher] = list(enrichers or [])
        # Redactors are optional and configured via settings at construction.
        self._redactors: list[BaseRedactor] = []
        # Worker binding and lifecycle
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._stop_flag = False
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_thread: threading.Thread | None = None
        self._thread_ready = threading.Event()
        self._loop_thread_ident: int | None = None
        self._num_workers = 1
        self._drained_event: asyncio.Event | None = None
        self._submitted = 0
        self._processed = 0
        self._dropped = 0
        self._retried = 0
        # Fast-path serialization toggle
        self._serialize_in_flush = bool(serialize_in_flush)
        # Exceptions config
        self._exceptions_enabled = bool(exceptions_enabled)
        self._exceptions_max_frames = int(exceptions_max_frames)
        self._exceptions_max_stack_chars = int(exceptions_max_stack_chars)
        # Context binding per task
        self._bound_context_var: contextvars.ContextVar[dict[str, Any] | None] = (
            contextvars.ContextVar(
                "fapilog_bound_context",
                default=None,
            )
        )
        # Error dedupe (message -> (first_ts, suppressed_count))
        self._error_dedupe: dict[str, tuple[float, int]] = {}

    def start(self) -> None:
        """Start worker group bound to an event loop.

        If called inside a running loop, bind to that loop and spawn tasks.
        Otherwise, start a dedicated thread with its own loop and wait until
        it is ready.
        """
        if self._worker_loop is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            # Bind to existing loop (async app)
            self._worker_loop = loop
            self._loop_thread_ident = threading.get_ident()
            self._drained_event = asyncio.Event()
            for _ in range(self._num_workers):
                task = loop.create_task(self._worker_main())
                self._worker_tasks.append(task)
        except RuntimeError:
            # No running loop: start dedicated loop in a thread
            self._stop_flag = False

            def _run() -> None:  # pragma: no cover - thread-loop fallback
                loop_local = asyncio.new_event_loop()
                self._worker_loop = loop_local
                self._loop_thread_ident = threading.get_ident()
                asyncio.set_event_loop(loop_local)
                self._drained_event = asyncio.Event()
                # Create worker tasks and mark ready
                for _ in range(self._num_workers):
                    self._worker_tasks.append(
                        loop_local.create_task(self._worker_main())
                    )
                self._thread_ready.set()
                try:
                    loop_local.run_forever()
                finally:
                    try:
                        pending = asyncio.all_tasks(loop_local)
                        for t in pending:
                            t.cancel()
                        if pending:
                            # Add timeout to prevent hanging during task cleanup
                            try:
                                cleanup_coro = asyncio.wait_for(
                                    asyncio.gather(*pending, return_exceptions=True),
                                    timeout=3.0,  # 3 second timeout
                                )
                                loop_local.run_until_complete(cleanup_coro)
                            except asyncio.TimeoutError:
                                # Tasks didn't complete within timeout, continue cleanup
                                try:
                                    from .diagnostics import warn

                                    warn(
                                        "logger",
                                        "task cleanup timeout during shutdown",
                                        pending_count=len(pending),
                                        timeout_seconds=3.0,
                                    )
                                except Exception:
                                    pass
                            except Exception:
                                # Handle other exceptions during task cleanup
                                pass
                    finally:
                        try:
                            loop_local.close()
                        except Exception:
                            # Handle exceptions during loop closure
                            pass

            self._worker_thread = threading.Thread(target=_run, daemon=True)
            self._worker_thread.start()
            self._thread_ready.wait(timeout=2.0)

    async def stop_and_drain(self) -> DrainResult:
        # If we're bound to the current running loop (async mode), await drain
        # directly
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if (
            running_loop is not None
            and self._worker_thread is None
            and self._drained_event is not None
        ):
            start = time.perf_counter()
            self._stop_flag = True
            try:
                # Add timeout to prevent hanging during drain event wait
                await asyncio.wait_for(self._drained_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                # Drain event didn't fire within timeout, log warning
                try:
                    from .diagnostics import warn

                    warn(
                        "logger",
                        "drain event timeout during async shutdown",
                        timeout_seconds=10.0,
                    )
                except Exception:
                    pass
            except Exception:
                # Handle other exceptions during drain event wait
                pass
            flush_latency = time.perf_counter() - start
            return DrainResult(
                submitted=self._submitted,
                processed=self._processed,
                dropped=self._dropped,
                retried=self._retried,
                queue_depth_high_watermark=self._queue_high_watermark,
                flush_latency_seconds=flush_latency,
            )

        def _drain_thread_mode() -> DrainResult:
            start = time.perf_counter()
            self._stop_flag = True
            loop = self._worker_loop
            if loop is not None and self._worker_thread is not None:
                # Signal the worker loop to stop gracefully
                try:
                    # Set stop flag and signal loop to stop
                    loop.call_soon_threadsafe(lambda: setattr(self, "_stop_flag", True))
                    # Give the loop a moment to process the stop signal
                    time.sleep(0.01)
                except Exception:
                    # Loop might be closed, continue with cleanup
                    pass

                # Wait for worker thread with timeout to prevent hanging
                try:
                    self._worker_thread.join(timeout=5.0)  # 5 second timeout
                    if self._worker_thread.is_alive():
                        # Thread didn't exit gracefully, log warning but continue
                        try:
                            from .diagnostics import warn

                            warn(
                                "logger",
                                "worker thread cleanup timeout",
                                thread_id=self._worker_thread.ident,
                                timeout_seconds=5.0,
                            )
                        except Exception:
                            pass
                except Exception:
                    # Handle any exceptions during thread join
                    pass

                # Clean up references regardless of thread state
                self._worker_thread = None
                self._worker_loop = None
            flush_latency = time.perf_counter() - start
            return DrainResult(
                submitted=self._submitted,
                processed=self._processed,
                dropped=self._dropped,
                retried=self._retried,
                queue_depth_high_watermark=self._queue_high_watermark,
                flush_latency_seconds=flush_latency,
            )

        return await asyncio.to_thread(_drain_thread_mode)

    # Public sync API
    def _enqueue(
        self,
        level: str,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        from uuid import uuid4

        from .context import request_id_var
        from .settings import Settings

        try:
            current_corr = request_id_var.get()
        except LookupError:
            current_corr = None
        if current_corr is None:
            current_corr = str(uuid4())

        # Probabilistic sampling (fast-path when 1.0). Only apply to
        # low-severity logs to avoid losing warnings/errors.
        try:
            s = Settings()
            rate = float(s.observability.logging.sampling_rate)
            if rate < 1.0 and level in {"DEBUG", "INFO"}:
                import random

                if random.random() > rate:
                    return
        except Exception:
            pass

        # ERROR-level dedupe: suppress identical messages within window
        try:
            if level in {"ERROR", "CRITICAL"}:
                from .settings import Settings as _S

                window = float(_S().core.error_dedupe_window_seconds)
                if window > 0.0:
                    import time as _t

                    now = _t.monotonic()
                    existing = self._error_dedupe.get(message)
                    if existing is None:
                        # First occurrence: set window and allow emit
                        self._error_dedupe[message] = (now, 0)
                    else:
                        first_ts, count = existing
                        if now - first_ts <= window:
                            # Suppress and bump count
                            self._error_dedupe[message] = (first_ts, count + 1)
                            return
                        # Window rollover: if suppressed existed, emit summary
                        if count > 0:
                            from .diagnostics import warn as _warn

                            try:
                                _warn(
                                    "error-dedupe",
                                    "suppressed duplicate errors",
                                    error_message=message,
                                    suppressed=count,
                                    window_seconds=window,
                                )
                            except Exception:
                                pass
                        # Reset window starting now
                        self._error_dedupe[message] = (now, 0)
        except Exception:
            pass

        # Merge precedence:
        # 1) Base event fields
        # 2) Enrichers (applied later)
        # 3) Bound context (per-task)
        # 4) Per-call kwargs (highest precedence)
        bound_context = {}
        try:
            ctx_val = self._bound_context_var.get(None)
            bound_context = dict(ctx_val or {})
        except Exception:
            bound_context = {}

        merged_metadata: dict[str, Any] = {}
        # Start with bound context, then overlay per-call metadata
        merged_metadata.update(bound_context)
        merged_metadata.update(metadata)

        # Structured exception serialization
        if self._exceptions_enabled:
            try:
                # Normalize precedence: exc > exc_info
                norm_exc_info = None
                if exc is not None:
                    norm_exc_info = (
                        type(exc),
                        exc,
                        getattr(exc, "__traceback__", None),
                    )
                elif exc_info is True:
                    import sys as _sys

                    norm_exc_info = _sys.exc_info()  # type: ignore[assignment]
                elif isinstance(exc_info, tuple):
                    norm_exc_info = exc_info
                if norm_exc_info:
                    from .errors import serialize_exception as _ser_exc

                    exc_map = _ser_exc(
                        norm_exc_info,
                        max_frames=self._exceptions_max_frames,
                        max_stack_chars=self._exceptions_max_stack_chars,
                    )
                    if exc_map:
                        merged_metadata.update(exc_map)
            except Exception:
                pass

        event = LogEvent(
            level=level,
            message=message,
            logger=self._name,
            metadata=merged_metadata,
            correlation_id=current_corr,
        )
        payload = event.to_mapping()
        self._submitted += 1
        # metrics: submitted
        if self._metrics is not None:
            try:
                # Try to get running loop first (preferred approach)
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._metrics.record_events_submitted(1))
                except RuntimeError:
                    # No running loop: run in thread mode
                    asyncio.run(self._metrics.record_events_submitted(1))
            except Exception:
                pass
        # Ensure worker running and loop bound
        self.start()
        wait_seconds = self._backpressure_wait_ms / 1000.0
        loop = self._worker_loop  # type: ignore[assignment]
        # If on the worker loop thread, do non-blocking enqueue only
        if (
            self._loop_thread_ident is not None
            and self._loop_thread_ident == threading.get_ident()
        ):
            if self._queue.try_enqueue(cast(dict[str, Any], payload)):
                qsize = self._queue.qsize()
                if qsize > self._queue_high_watermark:
                    self._queue_high_watermark = qsize
            else:
                self._dropped += 1
                # Throttled WARN for backpressure drop on same-thread path
                try:
                    from .diagnostics import warn

                    warn(
                        "backpressure",
                        "drop on full (same-thread)",
                        drop_total=self._dropped,
                        queue_hwm=self._queue_high_watermark,
                        capacity=self._queue.capacity,
                    )
                except Exception:
                    pass
            return
        # Cross-thread submission: schedule coroutine and wait up to timeout
        if loop is not None:
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self._async_enqueue(
                        cast(dict[str, Any], payload),
                        timeout=wait_seconds,
                    ),
                    loop,
                )
                ok = fut.result(timeout=wait_seconds + 0.05)
                if not ok:
                    self._dropped += 1
                    # Throttled WARN for backpressure drop on cross-thread path
                    try:
                        from .diagnostics import warn

                        warn(
                            "backpressure",
                            "drop on full (cross-thread)",
                            drop_total=self._dropped,
                            queue_hwm=self._queue_high_watermark,
                            capacity=self._queue.capacity,
                        )
                    except Exception:
                        pass
            except Exception:
                self._dropped += 1
                try:
                    from .diagnostics import warn

                    warn(
                        "backpressure",
                        "enqueue exception (drop)",
                        drop_total=self._dropped,
                        queue_hwm=self._queue_high_watermark,
                        capacity=self._queue.capacity,
                    )
                except Exception:
                    pass
            return

    def info(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue("INFO", message, exc=exc, exc_info=exc_info, **metadata)

    def debug(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue("DEBUG", message, exc=exc, exc_info=exc_info, **metadata)

    def warning(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue(
            "WARNING",
            message,
            exc=exc,
            exc_info=exc_info,
            **metadata,
        )

    def error(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        self._enqueue("ERROR", message, exc=exc, exc_info=exc_info, **metadata)

    def exception(self, message: str = "", **metadata: Any) -> None:
        """Convenience API: log at ERROR level with current exception info.

        Equivalent to error(message, exc_info=True, **metadata) inside except.
        """
        self._enqueue("ERROR", message, exc_info=True, **metadata)

    # Context binding API
    def bind(self, **context: Any) -> SyncLoggerFacade:
        """Return a child logger with additional bound context for
        current task.

        Binding is additive and scoped to the current async task/thread via
        ContextVar.
        """
        current = {}
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        current.update(context)
        self._bound_context_var.set(current)
        return self

    def unbind(self, *keys: str) -> None:
        """Remove specific keys from the bound context for current task."""
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        for k in keys:
            current.pop(k, None)
        self._bound_context_var.set(current)

    def clear_context(self) -> None:
        """Clear all bound context for current task."""
        self._bound_context_var.set(None)

    # Runtime toggles for enrichers
    def enable_enricher(self, enricher: BaseEnricher) -> None:
        try:
            name = getattr(enricher, "name", None)
        except Exception:
            name = None
        if name is None:
            return
        if all(getattr(e, "name", "") != name for e in self._enrichers):
            self._enrichers.append(enricher)

    def disable_enricher(self, name: str) -> None:
        self._enrichers = [e for e in self._enrichers if getattr(e, "name", "") != name]

    async def _worker_main(self) -> None:
        batch: list[dict[str, Any]] = []
        next_flush_deadline: float | None = None
        try:
            while True:
                # Stop requested: drain queue and flush immediately
                if self._stop_flag:
                    # Drain any remaining items into the batch
                    while True:
                        ok, item = self._queue.try_dequeue()
                        if not ok or item is None:
                            break
                        batch.append(item)
                    await self._flush_batch(batch)
                    # Stop loop in thread mode
                    if self._worker_thread is not None:
                        loop = asyncio.get_running_loop()
                        loop.stop()
                    # Signal drained for async mode
                    if self._drained_event is not None:
                        self._drained_event.set()
                    return
                # Pull as much as possible up to batch size
                ok, item = self._queue.try_dequeue()
                if ok and item is not None:
                    batch.append(item)
                    if len(batch) >= self._batch_max_size:
                        await self._flush_batch(batch)
                        next_flush_deadline = None
                        continue
                    if next_flush_deadline is None:
                        next_flush_deadline = (
                            time.perf_counter() + self._batch_timeout_seconds
                        )
                    continue

                # No item available; check deadline
                now = time.perf_counter()
                if next_flush_deadline is not None and now >= next_flush_deadline:
                    await self._flush_batch(batch)
                    next_flush_deadline = None
                    continue

                # Sleep briefly to yield loop
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - defensive catch
            # Contain worker failures; optionally emit diagnostics
            try:
                from .diagnostics import warn

                warn(
                    "worker",
                    "worker_main error",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            except Exception:
                pass
            return

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        start = time.perf_counter()
        try:
            from ..plugins.enrichers import enrich_parallel

            for entry in batch:
                # Enrich before sink write
                if self._enrichers:
                    try:
                        entry = await enrich_parallel(
                            entry,
                            list(self._enrichers),
                            metrics=self._metrics,
                        )
                    except Exception:
                        # Emit diagnostics for enrichment failures and continue
                        try:
                            from .diagnostics import warn as _warn

                            _warn(
                                "enricher",
                                "enrichment error",
                                _rate_limit_key="enrich",
                            )
                        except Exception:
                            pass
                        pass
                # Redactors stage (sequential, deterministic)
                if self._redactors:
                    try:
                        entry = await redact_in_order(
                            entry,
                            list(self._redactors),
                            metrics=self._metrics,
                        )
                    except Exception:
                        # Emit diagnostics for redaction failures and continue
                        try:
                            from .diagnostics import warn as _warn

                            _warn(
                                "redactor",
                                "redaction error",
                                _rate_limit_key="redact",
                            )
                        except Exception:
                            pass
                        pass
                # Optional fast-path: pre-serialize once and pass to sink
                if self._serialize_in_flush and self._sink_write_serialized is not None:
                    view: SerializedView | None = None
                    try:
                        view = serialize_envelope(entry)
                    except Exception as e:
                        # Strict vs best-effort behavior mirrors sinks
                        strict = False
                        try:
                            from . import settings as _settings

                            strict = bool(
                                _settings.Settings().core.strict_envelope_mode
                            )
                        except Exception:
                            strict = False
                        # Emit diagnostics but contain errors
                        try:
                            from .diagnostics import warn as _warn

                            _warn(
                                "sink",
                                "envelope serialization error",
                                mode="strict" if strict else "best-effort",
                                reason=type(e).__name__,
                                detail=str(e),
                            )
                        except Exception:
                            pass
                        if strict:
                            # Drop entry on strict failure
                            continue
                        try:
                            view = serialize_mapping_to_json_bytes(entry)
                        except Exception:
                            # As ultimate containment, fall back to dict write path
                            view = None

                    if view is not None:
                        try:
                            await self._sink_write_serialized(view)
                            self._processed += 1
                            continue
                        except Exception:
                            # Contain sink errors on serialized path and fall back below
                            pass

                # Fallback/default path
                await self._sink_write(entry)
                self._processed += 1
        except Exception as exc:
            # Contain sink errors; count as dropped
            self._dropped += len(batch)
            if self._metrics is not None:
                try:
                    # Attempt to derive a sink name if available via write callable
                    sink_name = None
                    try:
                        target = getattr(self._sink_write, "__self__", None)
                        if target is not None:
                            sink_name = type(target).__name__
                    except Exception:
                        sink_name = None
                    await self._metrics.record_sink_error(sink=sink_name)
                except Exception:
                    pass
            # Optional diagnostics
            try:
                from .diagnostics import warn

                warn(
                    "sink",
                    "flush error",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            except Exception:
                pass
        finally:
            if self._metrics is not None:
                try:
                    latency = time.perf_counter() - start
                    await self._metrics.record_flush(
                        batch_size=len(batch),
                        latency_seconds=latency,
                    )
                except Exception:
                    pass
            batch.clear()

    async def self_test(self) -> dict[str, Any]:
        """Perform a basic sink readiness probe.

        Calls sink_write with a minimal payload and returns structured result.
        """
        try:
            probe = {
                "level": "DEBUG",
                "message": "self_test",
                "metadata": {},
            }
            await self._sink_write(dict(probe))
            return {"ok": True, "sink": "default"}
        except Exception as exc:  # pragma: no cover - error path
            return {"ok": False, "sink": "default", "error": str(exc)}

    async def _async_enqueue(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> bool:
        """
        Async enqueue executed in the worker loop; returns True if enqueued.
        """
        effective_timeout: float | None = timeout if self._drop_on_full else None
        # Fast path
        if self._queue.try_enqueue(payload):
            qsize = self._queue.qsize()
            if qsize > self._queue_high_watermark:
                self._queue_high_watermark = qsize
                if self._metrics is not None:
                    await self._metrics.set_queue_high_watermark(qsize)
            return True
        # Backpressure handling
        if effective_timeout is not None and effective_timeout > 0:
            if self._metrics is not None:
                await self._metrics.record_backpressure_wait(1)
            try:
                await self._queue.await_enqueue(payload, timeout=effective_timeout)
                qsize = self._queue.qsize()
                if qsize > self._queue_high_watermark:
                    self._queue_high_watermark = qsize
                    if self._metrics is not None:
                        await self._metrics.set_queue_high_watermark(qsize)
                return True
            except Exception:
                if self._metrics is not None:
                    await self._metrics.record_events_dropped(1)
                return False
        if not self._drop_on_full:
            # Wait indefinitely (best-effort) when configured to never drop
            if self._metrics is not None:
                await self._metrics.record_backpressure_wait(1)
            try:
                await self._queue.await_enqueue(payload, timeout=None)
                qsize = self._queue.qsize()
                if qsize > self._queue_high_watermark:
                    self._queue_high_watermark = qsize
                    if self._metrics is not None:
                        await self._metrics.set_queue_high_watermark(qsize)
                return True
            except Exception:
                if self._metrics is not None:
                    await self._metrics.record_events_dropped(1)
                return False
        if self._metrics is not None:
            await self._metrics.record_events_dropped(1)
        return False


class AsyncLoggerFacade:
    """Async facade that enqueues log calls without blocking and honors backpressure.

    - Non-blocking awaitable methods that enqueue without thread hops
    - Binds to current event loop when available
    - Graceful shutdown with flush() and drain() methods
    - Maintains compatibility with existing sync facade patterns
    """

    def __init__(
        self,
        *,
        name: str | None,
        queue_capacity: int,
        batch_max_size: int,
        batch_timeout_seconds: float,
        backpressure_wait_ms: int,
        drop_on_full: bool,
        sink_write: Any,
        sink_write_serialized: Any | None = None,
        enrichers: list[BaseEnricher] | None = None,
        metrics: MetricsCollector | None = None,
        exceptions_enabled: bool = True,
        exceptions_max_frames: int = 50,
        exceptions_max_stack_chars: int = 20000,
        serialize_in_flush: bool = False,
    ) -> None:
        self._name = name or "root"
        self._queue = NonBlockingRingQueue[dict[str, Any]](capacity=queue_capacity)
        self._queue_high_watermark = 0
        self._batch_max_size = int(batch_max_size)
        self._batch_timeout_seconds = float(batch_timeout_seconds)
        self._backpressure_wait_ms = int(backpressure_wait_ms)
        self._drop_on_full = bool(drop_on_full)
        self._sink_write = sink_write
        self._sink_write_serialized = sink_write_serialized
        self._metrics = metrics
        # Store enrichers with explicit type
        self._enrichers: list[BaseEnricher] = list(enrichers or [])
        # Redactors are optional and configured via settings at construction.
        self._redactors: list[BaseRedactor] = []
        # Worker binding and lifecycle
        self._worker_tasks: list[asyncio.Task[None]] = []
        self._stop_flag = False
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_thread: threading.Thread | None = None
        self._thread_ready = threading.Event()
        self._loop_thread_ident: int | None = None
        self._num_workers = 1
        self._drained_event: asyncio.Event | None = None
        self._submitted = 0
        self._processed = 0
        self._dropped = 0
        self._retried = 0
        # Fast-path serialization toggle
        self._serialize_in_flush = bool(serialize_in_flush)
        # Exceptions config
        self._exceptions_enabled = bool(exceptions_enabled)
        self._exceptions_max_frames = int(exceptions_max_frames)
        self._exceptions_max_stack_chars = int(exceptions_max_stack_chars)
        # Context binding per task
        self._bound_context_var: contextvars.ContextVar[dict[str, Any] | None] = (
            contextvars.ContextVar(
                "fapilog_bound_context",
                default=None,
            )
        )
        # Error dedupe (message -> (first_ts, suppressed_count))
        self._error_dedupe: dict[str, tuple[float, int]] = {}
        # Flush event for immediate flush requests
        self._flush_event: asyncio.Event | None = None

    async def start_async(self) -> None:
        """Async start that ensures workers are scheduled before returning."""
        self.start()
        if self._worker_loop is not None and self._worker_loop.is_running():
            # Yield to let worker tasks get scheduled on the current loop
            await asyncio.sleep(0)
        elif self._thread_ready.is_set():
            # Threaded start: nothing to await, but ensure the thread signaled ready
            return

    def start(self) -> None:
        """Start worker group bound to an event loop.

        If called inside a running loop, bind to that loop and spawn tasks.
        Otherwise, start a dedicated thread with its own loop and wait until
        it is ready.
        """
        if self._worker_loop is not None:
            return
        try:
            loop = asyncio.get_running_loop()
            # Bind to existing loop (async app)
            self._worker_loop = loop
            self._loop_thread_ident = threading.get_ident()
            self._drained_event = asyncio.Event()
            self._flush_event = asyncio.Event()
            for _ in range(self._num_workers):
                task = loop.create_task(self._worker_main())
                self._worker_tasks.append(task)
        except RuntimeError:
            # No running loop: start dedicated loop in a thread
            self._stop_flag = False

            def _run() -> None:  # pragma: no cover - thread-loop fallback
                loop_local = asyncio.new_event_loop()
                self._worker_loop = loop_local
                self._loop_thread_ident = threading.get_ident()
                asyncio.set_event_loop(loop_local)
                self._drained_event = asyncio.Event()
                self._flush_event = asyncio.Event()
                # Create worker tasks and mark ready
                for _ in range(self._num_workers):
                    self._worker_tasks.append(
                        loop_local.create_task(self._worker_main())
                    )
                self._thread_ready.set()
                try:
                    loop_local.run_forever()
                finally:
                    try:
                        pending = asyncio.all_tasks(loop_local)
                        for t in pending:
                            t.cancel()
                        if pending:
                            loop_local.run_until_complete(
                                asyncio.gather(
                                    *pending,
                                    return_exceptions=True,
                                )
                            )
                    finally:
                        loop_local.close()

            self._worker_thread = threading.Thread(target=_run, daemon=True)
            self._worker_thread.start()
            self._thread_ready.wait(timeout=2.0)

    async def flush(self) -> None:
        """Flush current batches without stopping workers.

        This method triggers an immediate flush of the current batch(es) by
        setting an internal flush event and awaiting completion.
        """
        if self._flush_event is None:
            return

        # Set flush event to trigger immediate flush in workers
        self._flush_event.set()

        # Wait for flush to complete (workers will clear the event)
        await self._flush_event.wait()

        # Reset the event for future flush requests
        self._flush_event.set()

    async def drain(self) -> DrainResult:
        """Gracefully stop workers and return DrainResult.

        This method delegates to the existing stop_and_drain() functionality
        and returns the same DrainResult structure.
        """
        return await self.stop_and_drain()

    async def stop_and_drain(self) -> DrainResult:
        # If we're bound to the current running loop (async mode), await drain
        # directly
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if (
            running_loop is not None
            and self._worker_thread is None
            and self._drained_event is not None
        ):
            start = time.perf_counter()
            self._stop_flag = True
            await self._drained_event.wait()
            flush_latency = time.perf_counter() - start
            return DrainResult(
                submitted=self._submitted,
                processed=self._processed,
                dropped=self._dropped,
                retried=self._retried,
                queue_depth_high_watermark=self._queue_high_watermark,
                flush_latency_seconds=flush_latency,
            )

        def _drain_thread_mode() -> DrainResult:
            start = time.perf_counter()
            self._stop_flag = True
            loop = self._worker_loop
            if loop is not None and self._worker_thread is not None:
                loop.call_soon_threadsafe(lambda: None)
                self._worker_thread.join()
                self._worker_thread = None
                self._worker_loop = None
            flush_latency = time.perf_counter() - start
            return DrainResult(
                submitted=self._submitted,
                processed=self._processed,
                dropped=self._dropped,
                retried=self._retried,
                queue_depth_high_watermark=self._queue_high_watermark,
                flush_latency_seconds=flush_latency,
            )

        return await asyncio.to_thread(_drain_thread_mode)

    # Public async API
    async def _enqueue(
        self,
        level: str,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        from uuid import uuid4

        from .context import request_id_var
        from .settings import Settings

        try:
            current_corr = request_id_var.get()
        except LookupError:
            current_corr = None
        if current_corr is None:
            current_corr = str(uuid4())

        # Probabilistic sampling (fast-path when 1.0). Only apply to
        # low-severity logs to avoid losing warnings/errors.
        try:
            s = Settings()
            rate = float(s.observability.logging.sampling_rate)
            if rate < 1.0 and level in {"DEBUG", "INFO"}:
                import random

                if random.random() > rate:
                    return
        except Exception:
            pass

        # ERROR-level dedupe: suppress identical messages within window
        try:
            if level in {"ERROR", "CRITICAL"}:
                from .settings import Settings as _S

                window = float(_S().core.error_dedupe_window_seconds)
                if window > 0.0:
                    import time as _t

                    now = _t.monotonic()
                    existing = self._error_dedupe.get(message)
                    if existing is None:
                        # First occurrence: set window and allow emit
                        self._error_dedupe[message] = (now, 0)
                    else:
                        first_ts, count = existing
                        if now - first_ts <= window:
                            # Suppress and bump count
                            self._error_dedupe[message] = (first_ts, count + 1)
                            return
                        # Window rollover: if suppressed existed, emit summary
                        if count > 0:
                            from .diagnostics import warn as _warn

                            try:
                                _warn(
                                    "error-dedupe",
                                    "suppressed duplicate errors",
                                    error_message=message,
                                    suppressed=count,
                                    window_seconds=window,
                                )
                            except Exception:
                                pass
                        # Reset window starting now
                        self._error_dedupe[message] = (now, 0)
        except Exception:
            pass

        # Merge precedence:
        # 1) Base event fields
        # 2) Enrichers (applied later)
        # 3) Bound context (per-task)
        # 4) Per-call kwargs (highest precedence)
        bound_context = {}
        try:
            ctx_val = self._bound_context_var.get(None)
            bound_context = dict(ctx_val or {})
        except Exception:
            bound_context = {}

        merged_metadata: dict[str, Any] = {}
        # Start with bound context, then overlay per-call metadata
        merged_metadata.update(bound_context)
        merged_metadata.update(metadata)

        # Structured exception serialization
        if self._exceptions_enabled:
            try:
                # Normalize precedence: exc > exc_info
                norm_exc_info = None
                if exc is not None:
                    norm_exc_info = (
                        type(exc),
                        exc,
                        getattr(exc, "__traceback__", None),
                    )
                elif exc_info is True:
                    import sys as _sys

                    norm_exc_info = _sys.exc_info()  # type: ignore[assignment]
                elif isinstance(exc_info, tuple):
                    norm_exc_info = exc_info
                if norm_exc_info:
                    from .errors import serialize_exception as _ser_exc

                    exc_map = _ser_exc(
                        norm_exc_info,
                        max_frames=self._exceptions_max_frames,
                        max_stack_chars=self._exceptions_max_stack_chars,
                    )
                    if exc_map:
                        merged_metadata.update(exc_map)
            except Exception:
                pass

        event = LogEvent(
            level=level,
            message=message,
            logger=self._name,
            metadata=merged_metadata,
            correlation_id=current_corr,
        )
        payload = event.to_mapping()
        self._submitted += 1
        # metrics: submitted
        if self._metrics is not None:
            try:
                await self._metrics.record_events_submitted(1)
            except Exception:
                pass
        # Ensure worker running and loop bound
        self.start()

        # Async enqueue: use the async path directly
        ok = await self._async_enqueue(
            cast(dict[str, Any], payload),
            timeout=self._backpressure_wait_ms / 1000.0,
        )
        if not ok:
            self._dropped += 1
            # Throttled WARN for backpressure drop on async path
            try:
                from .diagnostics import warn

                warn(
                    "backpressure",
                    "drop on full (async)",
                    drop_total=self._dropped,
                    queue_hwm=self._queue_high_watermark,
                    capacity=self._queue.capacity,
                )
            except Exception:
                pass

    async def info(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue("INFO", message, exc=exc, exc_info=exc_info, **metadata)

    async def debug(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue("DEBUG", message, exc=exc, exc_info=exc_info, **metadata)

    async def warning(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue(
            "WARNING",
            message,
            exc=exc,
            exc_info=exc_info,
            **metadata,
        )

    async def error(
        self,
        message: str,
        *,
        exc: BaseException | None = None,
        exc_info: Any | None = None,
        **metadata: Any,
    ) -> None:
        await self._enqueue("ERROR", message, exc=exc, exc_info=exc_info, **metadata)

    async def exception(self, message: str = "", **metadata: Any) -> None:
        """Convenience API: log at ERROR level with current exception info.

        Equivalent to error(message, exc_info=True, **metadata) inside except.
        """
        await self._enqueue("ERROR", message, exc_info=True, **metadata)

    # Context binding API
    def bind(self, **context: Any) -> AsyncLoggerFacade:
        """Return a child logger with additional bound context for
        current task.

        Binding is additive and scoped to the current async task/thread via
        ContextVar.
        """
        current = {}
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        current.update(context)
        self._bound_context_var.set(current)
        return self

    def unbind(self, *keys: str) -> None:
        """Remove specific keys from the bound context for current task."""
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        for k in keys:
            current.pop(k, None)
        self._bound_context_var.set(current)

    def clear_context(self) -> None:
        """Clear all bound context for current task."""
        self._bound_context_var.set(None)

    # Runtime toggles for enrichers
    def enable_enricher(self, enricher: BaseEnricher) -> None:
        try:
            name = getattr(enricher, "name", None)
        except Exception:
            name = None
        if name is None:
            return
        if all(getattr(e, "name", "") != name for e in self._enrichers):
            self._enrichers.append(enricher)

    def disable_enricher(self, name: str) -> None:
        self._enrichers = [e for e in self._enrichers if getattr(e, "name", "") != name]

    async def _worker_main(self) -> None:
        batch: list[dict[str, Any]] = []
        next_flush_deadline: float | None = None
        try:
            while True:
                # Stop requested: drain queue and flush immediately
                if self._stop_flag:
                    # Drain any remaining items into the batch
                    while True:
                        ok, item = self._queue.try_dequeue()
                        if not ok or item is None:
                            break
                        batch.append(item)
                    await self._flush_batch(batch)
                    # Stop loop in thread mode
                    if self._worker_thread is not None:
                        loop = asyncio.get_running_loop()
                        loop.stop()
                    # Signal drained for async mode
                    if self._drained_event is not None:
                        self._drained_event.set()
                    return

                # Check for immediate flush request
                if self._flush_event is not None and self._flush_event.is_set():
                    if batch:
                        await self._flush_batch(batch)
                        next_flush_deadline = None
                    # Clear the flush event to signal completion
                    self._flush_event.clear()
                    continue

                # Pull as much as possible up to batch size
                ok, item = self._queue.try_dequeue()
                if ok and item is not None:
                    batch.append(item)
                    if len(batch) >= self._batch_max_size:
                        await self._flush_batch(batch)
                        next_flush_deadline = None
                        continue
                    if next_flush_deadline is None:
                        next_flush_deadline = (
                            time.perf_counter() + self._batch_timeout_seconds
                        )
                    continue

                # No item available; check deadline
                now = time.perf_counter()
                if next_flush_deadline is not None and now >= next_flush_deadline:
                    await self._flush_batch(batch)
                    next_flush_deadline = None
                    continue

                # Sleep briefly to yield loop
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - defensive catch
            # Contain worker failures; optionally emit diagnostics
            try:
                from .diagnostics import warn

                warn(
                    "worker",
                    "worker_main error",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            except Exception:
                pass
            return

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        start = time.perf_counter()
        try:
            from ..plugins.enrichers import enrich_parallel

            for entry in batch:
                # Enrich before sink write
                if self._enrichers:
                    try:
                        entry = await enrich_parallel(
                            entry,
                            list(self._enrichers),
                            metrics=self._metrics,
                        )
                    except Exception:
                        # Contain enrichment errors
                        pass
                # Redactors stage (sequential, deterministic)
                if self._redactors:
                    try:
                        entry = await redact_in_order(
                            entry,
                            list(self._redactors),
                            metrics=self._metrics,
                        )
                    except Exception:
                        # Contain redaction errors and continue
                        pass
                # Optional fast-path: pre-serialize once and pass to sink
                if self._serialize_in_flush and self._sink_write_serialized is not None:
                    view: SerializedView | None = None
                    try:
                        view = serialize_envelope(entry)
                    except Exception as e:
                        # Strict vs best-effort behavior mirrors sinks
                        strict = False
                        try:
                            from . import settings as _settings

                            strict = bool(
                                _settings.Settings().core.strict_envelope_mode
                            )
                        except Exception:
                            strict = False
                        # Emit diagnostics but contain errors
                        try:
                            from .diagnostics import warn as _warn

                            _warn(
                                "sink",
                                "envelope serialization error",
                                mode="strict" if strict else "best-effort",
                                reason=type(e).__name__,
                                detail=str(e),
                            )
                        except Exception:
                            pass
                        if strict:
                            # Drop entry on strict failure
                            continue
                        try:
                            view = serialize_mapping_to_json_bytes(entry)
                        except Exception:
                            # As ultimate containment, fall back to dict write path
                            view = None

                    if view is not None:
                        try:
                            await self._sink_write_serialized(view)
                            self._processed += 1
                            continue
                        except Exception:
                            # Contain sink errors on serialized path and fall back below
                            pass

                # Fallback/default path
                await self._sink_write(entry)
                self._processed += 1
        except Exception as exc:
            # Contain sink errors; count as dropped
            self._dropped += len(batch)
            if self._metrics is not None:
                try:
                    # Attempt to derive a sink name if available via write callable
                    sink_name = None
                    try:
                        target = getattr(self._sink_write, "__self__", None)
                        if target is not None:
                            sink_name = type(target).__name__
                    except Exception:
                        sink_name = None
                    await self._metrics.record_sink_error(sink=sink_name)
                except Exception:
                    pass
            # Optional diagnostics
            try:
                from .diagnostics import warn

                warn(
                    "sink",
                    "flush error",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            except Exception:
                pass
        finally:
            if self._metrics is not None:
                try:
                    latency = time.perf_counter() - start
                    await self._metrics.record_flush(
                        batch_size=len(batch),
                        latency_seconds=latency,
                    )
                except Exception:
                    pass
            batch.clear()

    async def self_test(self) -> dict[str, Any]:
        """Perform a basic sink readiness probe.

        Calls sink_write with a minimal payload and returns structured result.
        """
        try:
            probe = {
                "level": "DEBUG",
                "message": "self_test",
                "metadata": {},
            }
            await self._sink_write(dict(probe))
            return {"ok": True, "sink": "default"}
        except Exception as exc:  # pragma: no cover - error path
            return {"ok": False, "sink": "default", "error": str(exc)}

    async def _async_enqueue(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> bool:
        """
        Async enqueue executed in the worker loop; returns True if enqueued.
        """
        effective_timeout: float | None = timeout if self._drop_on_full else None
        # Fast path
        if self._queue.try_enqueue(payload):
            qsize = self._queue.qsize()
            if qsize > self._queue_high_watermark:
                self._queue_high_watermark = qsize
                if self._metrics is not None:
                    await self._metrics.set_queue_high_watermark(qsize)
            return True
        # Backpressure handling
        if effective_timeout is not None and effective_timeout > 0:
            if self._metrics is not None:
                await self._metrics.record_backpressure_wait(1)
            try:
                await self._queue.await_enqueue(payload, timeout=effective_timeout)
                qsize = self._queue.qsize()
                if qsize > self._queue_high_watermark:
                    self._queue_high_watermark = qsize
                    if self._metrics is not None:
                        await self._metrics.set_queue_high_watermark(qsize)
                return True
            except Exception:
                if self._metrics is not None:
                    await self._metrics.record_events_dropped(1)
                return False
        if not self._drop_on_full:
            # Wait indefinitely (best-effort) when configured to never drop
            if self._metrics is not None:
                await self._metrics.record_backpressure_wait(1)
            try:
                await self._queue.await_enqueue(payload, timeout=None)
                qsize = self._queue.qsize()
                if qsize > self._queue_high_watermark:
                    self._queue_high_watermark = qsize
                    if self._metrics is not None:
                        await self._metrics.set_queue_high_watermark(qsize)
                return True
            except Exception:
                if self._metrics is not None:
                    await self._metrics.record_events_dropped(1)
                return False
        if self._metrics is not None:
            await self._metrics.record_events_dropped(1)
        return False
