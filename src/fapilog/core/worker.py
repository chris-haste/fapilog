"""
Shared logger worker logic for SyncLoggerFacade and AsyncLoggerFacade.

Extracted to reduce duplication of batch flushing and worker loops.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Literal

from ..metrics.metrics import MetricsCollector, plugin_timer
from ..plugins.enrichers import BaseEnricher, enrich_parallel
from ..plugins.filters import filter_in_order
from ..plugins.processors import BaseProcessor
from ..plugins.redactors import BaseRedactor, redact_in_order
from .concurrency import NonBlockingRingQueue
from .diagnostics import warn
from .serialization import (
    SerializedView,
    serialize_envelope,
    serialize_mapping_to_json_bytes,
)


def strict_envelope_mode_enabled() -> bool:
    """Best-effort lookup for strict envelope mode."""
    try:
        from . import settings as _settings

        return bool(_settings.Settings().core.strict_envelope_mode)
    except Exception:
        return False


async def stop_plugins(
    processors: list[Any],
    filters: list[Any],
    redactors: list[Any],
    enrichers: list[Any],
) -> None:
    """Stop plugins in reverse order, containing errors and emitting diagnostics.

    Stop order: processors → filters → redactors → enrichers.
    Within each category, plugins are stopped in reverse registration order.
    Errors during stop() are logged via diagnostics but never propagate.
    """
    for plugin_type, plugins in [
        ("processor", processors),
        ("filter", filters),
        ("redactor", redactors),
        ("enricher", enrichers),
    ]:
        for plugin in reversed(plugins):
            try:
                if hasattr(plugin, "stop"):
                    await plugin.stop()
            except Exception as exc:  # noqa: BLE001
                try:
                    warn(
                        plugin_type,
                        "plugin stop failed",
                        plugin=getattr(plugin, "name", type(plugin).__name__),
                        error=str(exc),
                    )
                except Exception:
                    # Diagnostics should never block shutdown
                    pass


async def enqueue_with_backpressure(
    queue: NonBlockingRingQueue[dict[str, Any]],
    payload: dict[str, Any],
    *,
    timeout: float,
    drop_on_full: bool,
    metrics: MetricsCollector | None,
    current_high_watermark: int,
) -> tuple[bool, int]:
    """Shared enqueue logic with optional backpressure and metrics."""

    effective_timeout: float | None = timeout if drop_on_full else None
    high_watermark = current_high_watermark

    if queue.try_enqueue(payload):
        qsize = queue.qsize()
        if qsize > high_watermark:
            high_watermark = qsize
            if metrics is not None:
                await metrics.set_queue_high_watermark(qsize)
        return True, high_watermark

    if effective_timeout is not None and effective_timeout > 0:
        if metrics is not None:
            await metrics.record_backpressure_wait(1)
        try:
            await queue.await_enqueue(payload, timeout=effective_timeout)
            qsize = queue.qsize()
            if qsize > high_watermark:
                high_watermark = qsize
                if metrics is not None:
                    await metrics.set_queue_high_watermark(qsize)
            return True, high_watermark
        except Exception:
            if metrics is not None:
                await metrics.record_events_dropped(1)
            return False, high_watermark

    if not drop_on_full:
        if metrics is not None:
            await metrics.record_backpressure_wait(1)
        try:
            await queue.await_enqueue(payload, timeout=None)
            qsize = queue.qsize()
            if qsize > high_watermark:
                high_watermark = qsize
                if metrics is not None:
                    await metrics.set_queue_high_watermark(qsize)
            return True, high_watermark
        except Exception:
            if metrics is not None:
                await metrics.record_events_dropped(1)
            return False, high_watermark

    if metrics is not None:
        await metrics.record_events_dropped(1)
    return False, high_watermark


class LoggerWorker:
    """Background worker that processes log batches."""

    def __init__(
        self,
        *,
        queue: NonBlockingRingQueue[dict[str, Any]],
        batch_max_size: int,
        batch_timeout_seconds: float,
        sink_write: Callable[[dict[str, Any]], Awaitable[None]],
        sink_write_serialized: Callable[[SerializedView], Awaitable[None]] | None,
        filters_getter: Callable[[], list[Any]] | None = None,
        enrichers_getter: Callable[[], list[BaseEnricher]],
        redactors_getter: Callable[[], list[BaseRedactor]],
        processors_getter: Callable[[], list[BaseProcessor]] | None = None,
        metrics: MetricsCollector | None,
        serialize_in_flush: bool,
        strict_envelope_mode_provider: Callable[[], bool],
        stop_flag: Callable[[], bool],
        drained_event: asyncio.Event | None,
        flush_event: asyncio.Event | None,
        flush_done_event: asyncio.Event | None,
        emit_filter_diagnostics: bool = False,
        emit_enricher_diagnostics: bool,
        emit_redactor_diagnostics: bool,
        emit_processor_diagnostics: bool = False,
        counters: dict[str, int],
        redaction_fail_mode: Literal["open", "closed", "warn"] = "warn",
        enqueue_event: asyncio.Event | None = None,
    ) -> None:
        self._queue = queue
        self._batch_max_size = batch_max_size
        self._batch_timeout_seconds = batch_timeout_seconds
        self._sink_write = sink_write
        self._sink_write_serialized = sink_write_serialized
        self._filters_getter = filters_getter or (lambda: [])
        self._enrichers_getter = enrichers_getter
        self._redactors_getter = redactors_getter
        self._processors_getter = processors_getter or (lambda: [])
        self._metrics = metrics
        self._serialize_in_flush = serialize_in_flush
        self._strict_envelope_mode_provider = strict_envelope_mode_provider
        self._stop_flag = stop_flag
        self._drained_event = drained_event
        self._flush_event = flush_event
        self._flush_done_event = flush_done_event
        self._emit_filter_diagnostics = emit_filter_diagnostics
        self._emit_enricher_diagnostics = emit_enricher_diagnostics
        self._emit_redactor_diagnostics = emit_redactor_diagnostics
        self._emit_processor_diagnostics = emit_processor_diagnostics
        self._counters = counters
        self._redaction_fail_mode = redaction_fail_mode
        self._enqueue_event = enqueue_event

    async def run(self, *, in_thread_mode: bool = False) -> None:
        batch: list[dict[str, Any]] = []
        next_flush_deadline: float | None = None
        try:
            while True:
                if self._stop_flag():
                    self._drain_queue(batch)
                    await self._flush_batch(batch)
                    # NOTE: Do NOT call loop.stop() here. With multiple workers,
                    # the first worker to finish would stop the loop and cancel
                    # other workers still flushing. The drain coordinator handles
                    # waiting for all workers and stopping the loop.
                    if self._drained_event is not None:
                        self._drained_event.set()
                    return

                if self._flush_event is not None and self._flush_event.is_set():
                    self._drain_queue(batch)
                    if batch:
                        await self._flush_batch(batch)
                        next_flush_deadline = None
                    self._flush_event.clear()
                    if self._flush_done_event is not None:
                        self._flush_done_event.set()
                    continue

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

                now = time.perf_counter()
                if next_flush_deadline is not None and now >= next_flush_deadline:
                    await self._flush_batch(batch)
                    next_flush_deadline = None
                    continue

                # Wait for enqueue signal or batch timeout
                if self._enqueue_event is not None:
                    timeout: float | None = None
                    if next_flush_deadline is not None:
                        timeout = max(0.0, next_flush_deadline - now)
                    elif batch:
                        timeout = self._batch_timeout_seconds
                    else:
                        # No batch pending, wait indefinitely for enqueue
                        timeout = None

                    try:
                        await asyncio.wait_for(
                            self._enqueue_event.wait(),
                            timeout=timeout,
                        )
                        self._enqueue_event.clear()
                    except asyncio.TimeoutError:
                        pass  # Timeout expired, loop to check batch deadline
                else:
                    # Fallback to polling for backwards compatibility
                    await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - defensive catch
            self._emit_worker_error(exc)
            return

    async def flush_batch(self, batch: list[dict[str, Any]]) -> None:
        await self._flush_batch(batch)

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        """Flush a batch of log events through the processing pipeline.

        Pipeline Stage Order (with rationale):

        1. FILTERS: Applied first to drop unwanted events before any
           processing cost is incurred. Filters see raw events from queue.

        2. ENRICHERS: Applied second to add contextual data. Run after
           filters so dropped events don't waste enrichment cycles.

        3. REDACTORS: Applied third to mask sensitive data. Run after
           enrichers so they can redact both original AND enriched fields.

        4. PROCESSORS: Applied fourth to transform final payload. Run on
           serialized bytes when serialize_in_flush is enabled.

        5. SINK: Final stage writes to destination.

        Error Handling:
        - Stages 1-4: Errors contained; original event passed through
        - Stage 5: Errors logged via diagnostics; event dropped

        See: docs/architecture/pipeline-stages.md
        """
        if not batch:
            return
        start = time.perf_counter()
        batch_size = len(batch)
        processed_in_batch = 0
        dropped_in_batch = 0
        try:
            for entry in batch:
                # Stage 1: FILTERS - drop unwanted events early
                filtered = await self._apply_filters(entry)
                if filtered is None:
                    continue
                # Stage 2: ENRICHERS - add contextual data
                entry = await self._apply_enrichers(filtered)
                # Stage 3: REDACTORS - mask sensitive data (including enriched fields)
                redacted = await self._apply_redactors(entry)
                if redacted is None:
                    # Event dropped by fail-closed mode
                    dropped_in_batch += 1
                    if self._metrics is not None:
                        await self._metrics.record_events_dropped(1)
                    continue
                entry = redacted
                if self._serialize_in_flush and self._sink_write_serialized is not None:
                    view, drop_entry = await self._try_serialize(entry)
                    if drop_entry:
                        dropped_in_batch += 1
                        if self._metrics is not None:
                            await self._metrics.record_events_dropped(1)
                        continue
                    if view is not None:
                        # Stage 4: PROCESSORS - transform serialized bytes
                        view = await self._apply_processors(view)
                        try:
                            # Stage 5: SINK - write to destination
                            await self._sink_write_serialized(view)
                            processed_in_batch += 1
                            continue
                        except Exception:
                            # Fall back to default path on serialized sink errors
                            pass
                # Stage 5: SINK - write to destination (fallback or non-serialized path)
                await self._sink_write(entry)
                processed_in_batch += 1
        except Exception as exc:
            # Only count events that weren't already processed or explicitly dropped
            # as dropped. This maintains the invariant: processed + dropped <= submitted
            remaining = batch_size - processed_in_batch - dropped_in_batch
            dropped_in_batch += remaining
            if self._metrics is not None:
                await self._record_sink_error()
            self._emit_sink_flush_error(exc)
        finally:
            # Atomically update shared counters at the end of batch processing
            # to minimize the window for race conditions
            self._counters["processed"] += processed_in_batch
            self._counters["dropped"] += dropped_in_batch
            await self._record_flush_metrics(batch_size, time.perf_counter() - start)
            batch.clear()

    def _drain_queue(self, batch: list[dict[str, Any]]) -> None:
        while True:
            ok, item = self._queue.try_dequeue()
            if not ok or item is None:
                break
            batch.append(item)

    async def _apply_enrichers(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Apply enrichers to add contextual data to log event.

        Pipeline Stage 2: Runs after filters to avoid wasting cycles on
        dropped events. Enrichers add metadata like runtime info, request
        context, and custom business data.

        On error: Returns original entry unchanged (fail-safe).
        """
        enrichers = self._enrichers_getter()
        if not enrichers:
            return entry
        try:
            return await enrich_parallel(entry, enrichers, metrics=self._metrics)
        except Exception:
            if self._emit_enricher_diagnostics:
                try:
                    warn("enricher", "enrichment error", _rate_limit_key="enrich")
                except Exception:
                    pass
            return entry

    async def _apply_filters(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Apply filters to drop unwanted events early in the pipeline.

        Pipeline Stage 1: Runs first to minimize processing cost for
        events that will be discarded. Filters see raw events before
        any enrichment or redaction.

        Returns: Entry dict if kept, None if dropped.
        On error: Returns original entry unchanged (fail-safe).
        """
        filters = self._filters_getter()
        if not filters:
            return entry
        try:
            return await filter_in_order(entry, filters, metrics=self._metrics)
        except Exception:
            if self._emit_filter_diagnostics:
                try:
                    warn("filter", "filter error", _rate_limit_key="filter")
                except Exception:
                    pass
            return entry

    async def _apply_redactors(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Apply redactors to mask sensitive data in log event.

        Pipeline Stage 3: Runs after enrichers so redactors can mask
        both original fields AND enriched fields (e.g., request context
        that may contain PII).

        Behavior on error depends on redaction_fail_mode:
        - "open": Returns original entry unchanged (fail-safe, default)
        - "closed": Returns None to signal event should be dropped
        - "warn": Returns original entry but emits diagnostic warning
        """
        redactors = self._redactors_getter()
        if not redactors:
            return entry
        try:
            return await redact_in_order(entry, redactors, metrics=self._metrics)
        except Exception as exc:
            # Record metric for all fail modes
            if self._metrics:
                await self._metrics.record_redaction_exception()

            fail_mode = self._redaction_fail_mode

            if fail_mode == "closed":
                try:
                    warn(
                        "redactor",
                        "dropping event due to redaction exception",
                        error=str(exc),
                        _rate_limit_key="redaction_exception",
                    )
                except Exception:
                    pass
                return None  # Signal to drop event

            if fail_mode == "warn":
                try:
                    warn(
                        "redactor",
                        "redaction exception, passing original",
                        error=str(exc),
                        _rate_limit_key="redaction_exception",
                    )
                except Exception:
                    pass

            # "open" mode or fallback: return original entry
            return entry

    async def _apply_processors(self, view: SerializedView) -> SerializedView:
        """Apply processors to transform serialized log payload.

        Pipeline Stage 4: Runs on serialized bytes when serialize_in_flush
        is enabled. Processors can compress, encrypt, or transform the
        final payload before sink write.

        On error: Preserves original view unchanged (fail-safe).
        """
        processors = self._processors_getter()
        if not processors:
            return view

        base_view = view.view
        current_view: memoryview = base_view

        for processor in processors:
            proc_name = getattr(processor, "name", type(processor).__name__)
            try:
                async with plugin_timer(self._metrics, proc_name):
                    current_view = await processor.process(current_view)
            except Exception as exc:
                if self._emit_processor_diagnostics:
                    try:
                        warn(
                            "processor",
                            "processor error",
                            processor=proc_name,
                            error=str(exc),
                            _rate_limit_key="process",
                        )
                    except Exception:
                        pass
                # Preserve original view when processor fails
                current_view = base_view
                continue

        if current_view is base_view:
            return view
        try:
            return SerializedView(data=current_view.tobytes())
        except Exception:
            return view

    async def _try_serialize(
        self, entry: dict[str, Any]
    ) -> tuple[SerializedView | None, bool]:
        """Serialize entry to envelope format.

        After Story 1.28 (v1.1 schema alignment), this should succeed for all
        valid log entries from build_envelope() + enrichers. Failures indicate
        actual issues (non-JSON-serializable objects) not schema mismatch.

        Returns:
            Tuple of (SerializedView or None, should_drop).
            - (view, False): Serialization succeeded
            - (None, True): Serialization failed in strict mode, drop event
            - (view, False): Serialization failed, fallback succeeded
            - (None, False): Both failed, let dict-path handle it
        """
        try:
            return serialize_envelope(entry), False
        except Exception as exc:
            # After Story 1.28: This exception path is now truly exceptional.
            # With v1.1 schema alignment, serialize_envelope() only fails for
            # non-JSON-serializable objects, not schema mismatch.
            strict_mode = False
            try:
                strict_mode = bool(self._strict_envelope_mode_provider())
            except Exception:
                strict_mode = False
            try:
                warn(
                    "sink",
                    "serialization error (non-serializable data)",
                    mode="strict" if strict_mode else "best-effort",
                    reason=type(exc).__name__,
                    detail=str(exc),
                )
            except Exception:
                pass
            if strict_mode:
                return None, True
            # Best-effort fallback for edge cases
            try:
                return serialize_mapping_to_json_bytes(entry), False
            except Exception:
                return None, False

    async def _record_sink_error(self) -> None:
        if self._metrics is None:
            return
        sink_name = None
        try:
            target = getattr(self._sink_write, "__self__", None)
            if target is not None:
                sink_name = type(target).__name__
        except Exception:
            sink_name = None
        try:
            await self._metrics.record_sink_error(sink=sink_name)
        except Exception:
            pass

    def _emit_sink_flush_error(self, exc: Exception) -> None:
        try:
            warn(
                "sink",
                "flush error",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        except Exception:
            pass

    async def _record_flush_metrics(
        self, batch_size: int, latency_seconds: float
    ) -> None:
        if self._metrics is None:
            return
        try:
            await self._metrics.record_flush(
                batch_size=batch_size,
                latency_seconds=latency_seconds,
            )
        except Exception:
            pass

    def _emit_worker_error(self, exc: Exception) -> None:
        try:
            warn(
                "worker",
                "worker_main error",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        except Exception:
            pass
