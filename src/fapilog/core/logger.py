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
from ..plugins.redactors import BaseRedactor
from .concurrency import NonBlockingRingQueue
from .events import LogEvent
from .worker import (
    LoggerWorker,
    enqueue_with_backpressure,
    strict_envelope_mode_enabled,
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


class _WorkerCountersMixin:
    _counters: dict[str, int]

    @property
    def _processed(self) -> int:
        return self._counters.get("processed", 0)

    @_processed.setter
    def _processed(self, value: int) -> None:
        self._counters["processed"] = value

    @property
    def _dropped(self) -> int:
        return self._counters.get("dropped", 0)

    @_dropped.setter
    def _dropped(self, value: int) -> None:
        self._counters["dropped"] = value


class SyncLoggerFacade(_WorkerCountersMixin):
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
        num_workers: int = 1,
    ) -> None:
        self._name = name or "root"
        self._queue = NonBlockingRingQueue[dict[str, Any]](capacity=queue_capacity)
        self._queue_high_watermark = 0
        self._counters: dict[str, int] = {"processed": 0, "dropped": 0}
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
        self._num_workers = max(1, int(num_workers))
        self._drained_event: asyncio.Event | None = None
        self._flush_event: asyncio.Event | None = None
        self._flush_done_event: asyncio.Event | None = None
        self._submitted = 0
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
        # Track sinks for health aggregation
        self._sinks: list[Any] = []

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
            self._flush_done_event = asyncio.Event()
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
                self._flush_done_event = asyncio.Event()
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

    async def _stop_enrichers_and_redactors(self) -> None:
        """Stop enrichers and redactors, containing any errors."""
        # Stop redactors first (reverse order)
        for redactor in reversed(self._redactors):
            try:
                if hasattr(redactor, "stop"):
                    await redactor.stop()
            except Exception as exc:
                try:
                    from .diagnostics import warn

                    warn(
                        "redactor",
                        "plugin stop failed",
                        plugin=getattr(redactor, "name", type(redactor).__name__),
                        error=str(exc),
                    )
                except Exception:
                    pass

        # Stop enrichers (reverse order)
        for enricher in reversed(self._enrichers):
            try:
                if hasattr(enricher, "stop"):
                    await enricher.stop()
            except Exception as exc:
                try:
                    from .diagnostics import warn

                    warn(
                        "enricher",
                        "plugin stop failed",
                        plugin=getattr(enricher, "name", type(enricher).__name__),
                        error=str(exc),
                    )
                except Exception:
                    pass

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

            # Stop enrichers and redactors
            await self._stop_enrichers_and_redactors()

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

        result = await asyncio.to_thread(_drain_thread_mode)
        # Stop enrichers and redactors after thread-mode drain
        await self._stop_enrichers_and_redactors()
        return result

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
            self._schedule_metrics_call(self._metrics.record_events_submitted, 1)
        # Ensure worker running and loop bound
        self.start()
        wait_seconds = self._backpressure_wait_ms / 1000.0
        loop = self._worker_loop
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

    def unbind(self, *keys: str) -> SyncLoggerFacade:
        """Remove specific keys from the bound context for current task and return self."""
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        for k in keys:
            current.pop(k, None)
        self._bound_context_var.set(current)
        return self

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

    def _make_worker(self) -> LoggerWorker:
        return LoggerWorker(
            queue=self._queue,
            batch_max_size=self._batch_max_size,
            batch_timeout_seconds=self._batch_timeout_seconds,
            sink_write=self._sink_write,
            sink_write_serialized=self._sink_write_serialized,
            enrichers_getter=lambda: list(self._enrichers),
            redactors_getter=lambda: list(self._redactors),
            metrics=self._metrics,
            serialize_in_flush=self._serialize_in_flush,
            strict_envelope_mode_provider=strict_envelope_mode_enabled,
            stop_flag=lambda: self._stop_flag,
            drained_event=self._drained_event,
            flush_event=self._flush_event,
            flush_done_event=self._flush_done_event,
            emit_enricher_diagnostics=True,
            emit_redactor_diagnostics=True,
            counters=self._counters,
        )

    async def _worker_main(self) -> None:
        worker = self._make_worker()
        await worker.run(in_thread_mode=self._worker_thread is not None)

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        worker = self._make_worker()
        await worker.flush_batch(batch)

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

    async def check_health(self) -> Any:
        """Aggregated health across enrichers, redactors, and sinks.

        Returns:
            AggregatedHealth with overall status and per-plugin details.
        """
        from ..plugins.health import aggregate_plugin_health

        sinks = getattr(self, "_sinks", None)
        sink_list = sinks if isinstance(sinks, list) and sinks else [self._sink_write]
        return await aggregate_plugin_health(
            enrichers=list(self._enrichers),
            redactors=list(self._redactors),
            sinks=sink_list,
        )

    async def _async_enqueue(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> bool:
        """
        Async enqueue executed in the worker loop; returns True if enqueued.
        """
        ok, high_watermark = await enqueue_with_backpressure(
            self._queue,
            payload,
            timeout=timeout,
            drop_on_full=self._drop_on_full,
            metrics=self._metrics,
            current_high_watermark=self._queue_high_watermark,
        )
        self._queue_high_watermark = high_watermark
        return ok

    def _schedule_metrics_call(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        """Best-effort metrics scheduling without blocking callers.

        Prefers the worker loop if available; falls back to a background thread.
        """
        if self._metrics is None:
            return
        loop = self._worker_loop
        if loop is not None:
            try:
                fut = asyncio.run_coroutine_threadsafe(fn(*args, **kwargs), loop)
                # Avoid blocking; ignore result
                _ = fut
                return
            except Exception:
                pass

        def _run() -> None:
            try:
                asyncio.run(fn(*args, **kwargs))
            except Exception:
                return

        threading.Thread(target=_run, daemon=True).start()


class AsyncLoggerFacade(_WorkerCountersMixin):
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
        num_workers: int = 1,
    ) -> None:
        self._name = name or "root"
        self._queue = NonBlockingRingQueue[dict[str, Any]](capacity=queue_capacity)
        self._queue_high_watermark = 0
        self._counters: dict[str, int] = {"processed": 0, "dropped": 0}
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
        self._num_workers = max(1, int(num_workers))
        self._drained_event: asyncio.Event | None = None
        self._flush_event: asyncio.Event | None = None
        self._flush_done_event: asyncio.Event | None = None
        self._submitted = 0
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
            self._flush_done_event = asyncio.Event()
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
                self._flush_done_event = asyncio.Event()
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

        # Clear any prior completion signal
        if self._flush_done_event is not None:
            self._flush_done_event.clear()

        # Set flush event to trigger immediate flush in workers
        self._flush_event.set()

        # Wait for flush to complete (workers will signal done)
        if self._flush_done_event is not None:
            try:
                await asyncio.wait_for(self._flush_done_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Best-effort: proceed even if workers did not acknowledge
                pass
        # Leave flush_event cleared by workers

    async def drain(self) -> DrainResult:
        """Gracefully stop workers and return DrainResult.

        This method delegates to the existing stop_and_drain() functionality
        and returns the same DrainResult structure.
        """
        return await self.stop_and_drain()

    async def _stop_enrichers_and_redactors(self) -> None:
        """Stop enrichers and redactors, containing any errors."""
        # Stop redactors first (reverse order)
        for redactor in reversed(self._redactors):
            try:
                if hasattr(redactor, "stop"):
                    await redactor.stop()
            except Exception as exc:
                try:
                    from .diagnostics import warn

                    warn(
                        "redactor",
                        "plugin stop failed",
                        plugin=getattr(redactor, "name", type(redactor).__name__),
                        error=str(exc),
                    )
                except Exception:
                    pass

        # Stop enrichers (reverse order)
        for enricher in reversed(self._enrichers):
            try:
                if hasattr(enricher, "stop"):
                    await enricher.stop()
            except Exception as exc:
                try:
                    from .diagnostics import warn

                    warn(
                        "enricher",
                        "plugin stop failed",
                        plugin=getattr(enricher, "name", type(enricher).__name__),
                        error=str(exc),
                    )
                except Exception:
                    pass

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

            # Stop enrichers and redactors
            await self._stop_enrichers_and_redactors()

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

        result = await asyncio.to_thread(_drain_thread_mode)
        # Stop enrichers and redactors after thread-mode drain
        await self._stop_enrichers_and_redactors()
        return result

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

    def unbind(self, *keys: str) -> AsyncLoggerFacade:
        """Remove specific keys from the bound context for current task and return self."""
        try:
            ctx_val = self._bound_context_var.get(None)
            current = dict(ctx_val or {})
        except Exception:
            current = {}
        for k in keys:
            current.pop(k, None)
        self._bound_context_var.set(current)
        return self

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

    def _make_worker(self) -> LoggerWorker:
        return LoggerWorker(
            queue=self._queue,
            batch_max_size=self._batch_max_size,
            batch_timeout_seconds=self._batch_timeout_seconds,
            sink_write=self._sink_write,
            sink_write_serialized=self._sink_write_serialized,
            enrichers_getter=lambda: list(self._enrichers),
            redactors_getter=lambda: list(self._redactors),
            metrics=self._metrics,
            serialize_in_flush=self._serialize_in_flush,
            strict_envelope_mode_provider=strict_envelope_mode_enabled,
            stop_flag=lambda: self._stop_flag,
            drained_event=self._drained_event,
            flush_event=self._flush_event,
            flush_done_event=self._flush_done_event,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters=self._counters,
        )

    async def _worker_main(self) -> None:
        worker = self._make_worker()
        await worker.run(in_thread_mode=self._worker_thread is not None)

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        worker = self._make_worker()
        await worker.flush_batch(batch)

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

    async def check_health(self) -> Any:
        """Aggregated health across enrichers, redactors, and sinks.

        Returns:
            AggregatedHealth with overall status and per-plugin details.
        """
        from ..plugins.health import aggregate_plugin_health

        sinks = getattr(self, "_sinks", None)
        sink_list = sinks if isinstance(sinks, list) and sinks else [self._sink_write]
        return await aggregate_plugin_health(
            enrichers=list(self._enrichers),
            redactors=list(self._redactors),
            sinks=sink_list,
        )

    async def _async_enqueue(
        self,
        payload: dict[str, Any],
        *,
        timeout: float,
    ) -> bool:
        """
        Async enqueue executed in the worker loop; returns True if enqueued.
        """
        ok, high_watermark = await enqueue_with_backpressure(
            self._queue,
            payload,
            timeout=timeout,
            drop_on_full=self._drop_on_full,
            metrics=self._metrics,
            current_high_watermark=self._queue_high_watermark,
        )
        self._queue_high_watermark = high_watermark
        return ok
