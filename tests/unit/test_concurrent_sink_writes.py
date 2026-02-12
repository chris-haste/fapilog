"""Tests for concurrent sink writes within a batch (Story 1.49)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from pydantic import ValidationError

from fapilog.core.settings import CoreSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(
    *,
    sink_write: Any,
    sink_write_serialized: Any | None = None,
    sink_concurrency: int = 1,
    serialize_in_flush: bool = False,
    filters: list[Any] | None = None,
    redactors: list[Any] | None = None,
    enrichers: list[Any] | None = None,
    processors: list[Any] | None = None,
    counters: dict[str, int] | None = None,
) -> Any:
    """Build a minimal LoggerWorker for testing."""
    from fapilog.core.concurrency import NonBlockingRingQueue
    from fapilog.core.worker import LoggerWorker

    q: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
    if counters is None:
        counters = {"processed": 0, "dropped": 0}
    return LoggerWorker(
        queue=q,
        batch_max_size=256,
        batch_timeout_seconds=0.25,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        enrichers_getter=lambda: enrichers or [],
        redactors_getter=lambda: redactors or [],
        filters_getter=lambda: filters or [],
        processors_getter=lambda: processors or [],
        metrics=None,
        serialize_in_flush=serialize_in_flush,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: False,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters=counters,
        sink_concurrency=sink_concurrency,
    )


# ---------------------------------------------------------------------------
# AC7: Settings validation
# ---------------------------------------------------------------------------


class TestSinkConcurrencySettingValidation:
    """AC7: sink_concurrency setting in CoreSettings."""

    def test_default_is_one(self) -> None:
        """Default sink_concurrency is 1 (serial behavior)."""
        settings = CoreSettings()
        assert settings.sink_concurrency == 1

    def test_accepts_valid_value(self) -> None:
        """sink_concurrency accepts values >= 1."""
        settings = CoreSettings(sink_concurrency=8)
        assert settings.sink_concurrency == 8

    def test_rejects_zero(self) -> None:
        """sink_concurrency rejects 0."""
        with pytest.raises(ValidationError):
            CoreSettings(sink_concurrency=0)

    def test_rejects_negative(self) -> None:
        """sink_concurrency rejects negative values."""
        with pytest.raises(ValidationError):
            CoreSettings(sink_concurrency=-1)


# ---------------------------------------------------------------------------
# AC1: Concurrent sink writes within a batch
# ---------------------------------------------------------------------------


class TestConcurrentWritesOverlap:
    """AC1: When sink_concurrency > 1, sink writes overlap."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_overlap(self) -> None:
        """4 events with 300ms sink and concurrency=4 finish in ~300ms, not 1200ms."""
        call_times: list[float] = []

        async def slow_sink(entry: dict[str, Any]) -> None:
            call_times.append(time.perf_counter())
            await asyncio.sleep(0.3)

        worker = _make_worker(sink_write=slow_sink, sink_concurrency=4)
        batch = [{"level": "INFO", "message": f"msg{i}"} for i in range(4)]

        start = time.perf_counter()
        await worker.flush_batch(batch)
        elapsed = time.perf_counter() - start

        # All 4 should start concurrently — total ~300ms not ~1200ms
        assert len(call_times) == 4
        spread = call_times[-1] - call_times[0]
        assert spread < 0.1  # All started within 100ms of each other
        assert elapsed < 0.6  # Much less than 4 * 0.3s = 1.2s


# ---------------------------------------------------------------------------
# AC2: Semaphore bounds in-flight writes
# ---------------------------------------------------------------------------


class TestSemaphoreBoundsConcurrency:
    """AC2: No more than sink_concurrency writes execute simultaneously."""

    @pytest.mark.asyncio
    async def test_semaphore_bounds_concurrency(self) -> None:
        """With concurrency=4 and 20 events, max concurrent writes <= 4."""
        max_concurrent = 0
        current = 0
        lock = asyncio.Lock()

        async def tracking_sink(entry: dict[str, Any]) -> None:
            nonlocal max_concurrent, current
            async with lock:
                current += 1
                max_concurrent = max(max_concurrent, current)
            await asyncio.sleep(0.05)
            async with lock:
                current -= 1

        worker = _make_worker(sink_write=tracking_sink, sink_concurrency=4)
        batch = [{"level": "INFO", "message": f"msg{i}"} for i in range(20)]

        await worker.flush_batch(batch)

        assert max_concurrent <= 4
        assert max_concurrent > 1  # Verify concurrency actually happened


# ---------------------------------------------------------------------------
# AC3: Default preserves serial behavior
# ---------------------------------------------------------------------------


class TestDefaultSerialBehavior:
    """AC3: sink_concurrency=1 preserves serial behavior."""

    @pytest.mark.asyncio
    async def test_default_serial_behavior(self) -> None:
        """With concurrency=1 and 3 events with 100ms sink, total ~300ms."""
        write_count = 0

        async def slow_sink(entry: dict[str, Any]) -> None:
            nonlocal write_count
            await asyncio.sleep(0.1)
            write_count += 1

        worker = _make_worker(sink_write=slow_sink, sink_concurrency=1)
        batch = [{"level": "INFO", "message": f"msg{i}"} for i in range(3)]

        start = time.perf_counter()
        await worker.flush_batch(batch)
        elapsed = time.perf_counter() - start

        assert write_count == 3
        assert elapsed >= 0.25  # ~300ms serial


# ---------------------------------------------------------------------------
# AC4: Per-event error isolation
# ---------------------------------------------------------------------------


class TestPerEventErrorIsolation:
    """AC4: A failed write does not prevent other events from being written."""

    @pytest.mark.asyncio
    async def test_single_write_error_does_not_abort_batch(self) -> None:
        """Batch [ok, fail, ok, ok] — 3 written, 1 dropped."""
        results: list[dict[str, Any]] = []

        async def flaky_sink(entry: dict[str, Any]) -> None:
            if entry.get("fail"):
                raise RuntimeError("sink error")
            results.append(entry)

        counters: dict[str, int] = {"processed": 0, "dropped": 0}
        worker = _make_worker(
            sink_write=flaky_sink, sink_concurrency=4, counters=counters
        )
        batch = [
            {"level": "INFO", "message": "ok1"},
            {"level": "INFO", "message": "fail1", "fail": True},
            {"level": "INFO", "message": "ok2"},
            {"level": "INFO", "message": "ok3"},
        ]

        await worker.flush_batch(batch)

        assert len(results) == 3
        assert counters["processed"] == 3
        assert counters["dropped"] == 1


# ---------------------------------------------------------------------------
# AC5: Counters are accurate
# ---------------------------------------------------------------------------


class TestCounterAccuracy:
    """AC5: processed and dropped counters reflect actual outcomes."""

    @pytest.mark.asyncio
    async def test_processed_dropped_counters_accurate(self) -> None:
        """Batch of 10: 2 filtered, 1 sink error, 7 written."""
        results: list[dict[str, Any]] = []
        call_count = 0

        async def flaky_sink(entry: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Fail the 3rd write
                raise RuntimeError("sink error")
            results.append(entry)

        # A filter that drops entries with "skip" in message
        class SkipFilter:
            name = "skip_filter"

            async def filter(self, event: dict[str, Any]) -> dict[str, Any] | None:
                if "skip" in event.get("message", ""):
                    return None
                return event

        counters: dict[str, int] = {"processed": 0, "dropped": 0}
        worker = _make_worker(
            sink_write=flaky_sink,
            sink_concurrency=4,
            counters=counters,
            filters=[SkipFilter()],
        )
        batch = [
            {"level": "INFO", "message": "skip1"},  # filtered
            {"level": "INFO", "message": "ok1"},
            {"level": "INFO", "message": "ok2"},
            {"level": "INFO", "message": "ok3"},  # 3rd write → error
            {"level": "INFO", "message": "ok4"},
            {"level": "INFO", "message": "skip2"},  # filtered
            {"level": "INFO", "message": "ok5"},
            {"level": "INFO", "message": "ok6"},
            {"level": "INFO", "message": "ok7"},
            {"level": "INFO", "message": "ok8"},
        ]

        await worker.flush_batch(batch)

        assert counters["processed"] == 7
        assert counters["dropped"] == 1


# ---------------------------------------------------------------------------
# AC6: Serialized path supports concurrency
# ---------------------------------------------------------------------------


class TestSerializedPathConcurrent:
    """AC6: sink_write_serialized path also runs concurrently."""

    @pytest.mark.asyncio
    async def test_serialized_path_concurrent(self) -> None:
        """4 serialized events with concurrency=4 — total ~1x sink latency."""
        from fapilog.core.envelope import build_envelope

        call_times: list[float] = []

        async def slow_serialized_sink(view: Any) -> None:
            call_times.append(time.perf_counter())
            await asyncio.sleep(0.2)

        async def slow_dict_sink(entry: dict[str, Any]) -> None:
            call_times.append(time.perf_counter())
            await asyncio.sleep(0.2)

        worker = _make_worker(
            sink_write=slow_dict_sink,
            sink_write_serialized=slow_serialized_sink,
            sink_concurrency=4,
            serialize_in_flush=True,
        )
        batch = [build_envelope(level="INFO", message=f"msg{i}") for i in range(4)]

        start = time.perf_counter()
        await worker.flush_batch(batch)
        elapsed = time.perf_counter() - start

        assert len(call_times) == 4
        assert elapsed < 0.5  # ~200ms not ~800ms


# ---------------------------------------------------------------------------
# AC8: Adaptive batch sizer feedback is unchanged
# ---------------------------------------------------------------------------


class TestBatchSizerFeedback:
    """AC8: ms_per_item formula is preserved under concurrent writes."""

    @pytest.mark.asyncio
    async def test_batch_sizer_feedback_with_concurrency(self) -> None:
        """Batch of 8 with concurrent writes — ms_per_item reflects wall clock."""
        from fapilog.core.adaptive import AdaptiveBatchSizer, AdaptiveController

        recorded_samples: list[float] = []
        real_controller = AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=1, max_batch=1024, target_latency_ms=5.0
            ),
        )
        # Monkey-patch to capture the latency samples
        orig_record = real_controller.record_latency_sample

        def capturing_record(ms_per_item: float) -> None:
            recorded_samples.append(ms_per_item)
            orig_record(ms_per_item)

        real_controller.record_latency_sample = capturing_record  # type: ignore[assignment]

        async def fast_sink(entry: dict[str, Any]) -> None:
            await asyncio.sleep(0.01)

        from fapilog.core.concurrency import NonBlockingRingQueue
        from fapilog.core.worker import LoggerWorker

        q: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
        counters: dict[str, int] = {"processed": 0, "dropped": 0}
        worker = LoggerWorker(
            queue=q,
            batch_max_size=256,
            batch_timeout_seconds=0.25,
            sink_write=fast_sink,
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [],
            filters_getter=lambda: [],
            processors_getter=lambda: [],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=lambda: False,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters=counters,
            sink_concurrency=8,
            adaptive_controller=real_controller,
        )

        batch = [{"level": "INFO", "message": f"msg{i}"} for i in range(8)]
        await worker.flush_batch(batch)

        # Should have recorded exactly 1 sample
        assert len(recorded_samples) == 1
        # ms_per_item = wall_clock_ms / batch_size
        # With concurrency=8 and 10ms sleep, wall clock ~10ms, so ~1.25 ms/item
        assert recorded_samples[0] < 50  # Much less than serial 10ms/item


# ---------------------------------------------------------------------------
# Serialized fallback to default on error
# ---------------------------------------------------------------------------


class TestSerializedFallbackToDefault:
    """Serialized sink error falls back to default dict path."""

    @pytest.mark.asyncio
    async def test_serialized_fallback_to_default_on_error(self) -> None:
        """When serialized write fails, falls back to dict write."""
        from fapilog.core.envelope import build_envelope

        dict_writes: list[dict[str, Any]] = []

        async def failing_serialized_sink(view: Any) -> None:
            raise RuntimeError("serialized sink error")

        async def dict_sink(entry: dict[str, Any]) -> None:
            dict_writes.append(entry)

        counters: dict[str, int] = {"processed": 0, "dropped": 0}
        worker = _make_worker(
            sink_write=dict_sink,
            sink_write_serialized=failing_serialized_sink,
            sink_concurrency=2,
            serialize_in_flush=True,
            counters=counters,
        )
        batch = [build_envelope(level="INFO", message=f"msg{i}") for i in range(3)]

        await worker.flush_batch(batch)

        # All 3 should fall back to dict path
        assert len(dict_writes) == 3
        assert counters["processed"] == 3
        assert counters["dropped"] == 0


# ---------------------------------------------------------------------------
# Contract test
# ---------------------------------------------------------------------------


class TestConcurrentFlushWithRealPipeline:
    """Contract test: real pipeline with concurrent writes."""

    @pytest.mark.asyncio
    async def test_concurrent_flush_with_real_pipeline(self) -> None:
        """build_envelope → flush with concurrent writes processes all events."""
        from fapilog.core.envelope import build_envelope

        written: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            written.append(entry)

        worker = _make_worker(sink_write=sink_write, sink_concurrency=4)
        batch = [build_envelope(level="INFO", message=f"event {i}") for i in range(10)]

        counters_ref = {"processed": 0, "dropped": 0}
        worker._counters = counters_ref  # type: ignore[attr-defined]
        await worker.flush_batch(batch)

        assert len(written) == 10
        assert counters_ref["processed"] == 10
        assert counters_ref["dropped"] == 0
