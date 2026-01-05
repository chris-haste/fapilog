"""
Shared logger worker logic for SyncLoggerFacade and AsyncLoggerFacade.

Extracted to reduce duplication of batch flushing and worker loops.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable

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

    async def run(self, *, in_thread_mode: bool = False) -> None:
        batch: list[dict[str, Any]] = []
        next_flush_deadline: float | None = None
        try:
            while True:
                if self._stop_flag():
                    self._drain_queue(batch)
                    await self._flush_batch(batch)
                    if in_thread_mode:
                        loop = asyncio.get_running_loop()
                        loop.stop()
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

                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - defensive catch
            self._emit_worker_error(exc)
            return

    async def flush_batch(self, batch: list[dict[str, Any]]) -> None:
        await self._flush_batch(batch)

    async def _flush_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        start = time.perf_counter()
        try:
            for entry in batch:
                filtered = await self._apply_filters(entry)
                if filtered is None:
                    continue
                entry = await self._apply_enrichers(filtered)
                entry = await self._apply_redactors(entry)
                if self._serialize_in_flush and self._sink_write_serialized is not None:
                    view, drop_entry = await self._try_serialize(entry)
                    if drop_entry:
                        continue
                    if view is not None:
                        view = await self._apply_processors(view)
                        try:
                            await self._sink_write_serialized(view)
                            self._counters["processed"] += 1
                            continue
                        except Exception:
                            # Fall back to default path on serialized sink errors
                            pass
                await self._sink_write(entry)
                self._counters["processed"] += 1
        except Exception as exc:
            self._counters["dropped"] += len(batch)
            if self._metrics is not None:
                await self._record_sink_error()
            self._emit_sink_flush_error(exc)
        finally:
            await self._record_flush_metrics(len(batch), time.perf_counter() - start)
            batch.clear()

    def _drain_queue(self, batch: list[dict[str, Any]]) -> None:
        while True:
            ok, item = self._queue.try_dequeue()
            if not ok or item is None:
                break
            batch.append(item)

    async def _apply_enrichers(self, entry: dict[str, Any]) -> dict[str, Any]:
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

    async def _apply_redactors(self, entry: dict[str, Any]) -> dict[str, Any]:
        redactors = self._redactors_getter()
        if not redactors:
            return entry
        try:
            return await redact_in_order(entry, redactors, metrics=self._metrics)
        except Exception:
            if self._emit_redactor_diagnostics:
                try:
                    warn("redactor", "redaction error", _rate_limit_key="redact")
                except Exception:
                    pass
            return entry

    async def _apply_processors(self, view: SerializedView) -> SerializedView:
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
        try:
            return serialize_envelope(entry), False
        except Exception as exc:
            strict_mode = False
            try:
                strict_mode = bool(self._strict_envelope_mode_provider())
            except Exception:
                strict_mode = False
            try:
                warn(
                    "sink",
                    "envelope serialization error",
                    mode="strict" if strict_mode else "best-effort",
                    reason=type(exc).__name__,
                    detail=str(exc),
                )
            except Exception:
                pass
            if strict_mode:
                return None, True
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
