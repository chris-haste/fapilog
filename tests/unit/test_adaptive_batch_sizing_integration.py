"""Unit tests for adaptive batch sizing integration (Story 1.47).

Tests that LoggerWorker adjusts batch size based on AdaptiveController
feedback after each flush, and that the logger creates the controller
when the setting is enabled.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

from fapilog.core.adaptive import AdaptiveBatchSizer, AdaptiveController
from fapilog.core.worker import LoggerWorker


def _make_worker(
    *,
    queue: Any,
    adaptive_controller: AdaptiveController | None = None,
    batch_max_size: int = 256,
    sink_write: Any | None = None,
) -> LoggerWorker:
    """Helper to build a LoggerWorker with minimal required params."""
    return LoggerWorker(
        queue=queue,
        batch_max_size=batch_max_size,
        batch_timeout_seconds=0.25,
        sink_write=sink_write or AsyncMock(),
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=lambda: False,
        stop_flag=lambda: False,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=False,
        emit_redactor_diagnostics=False,
        counters={"processed": 0, "dropped": 0},
        adaptive_controller=adaptive_controller,
    )


class TestAdaptiveBatchSizingDisabledByDefault:
    """AC5: Static batch_max_size used when no controller provided."""

    async def test_disabled_by_default_uses_static_size(self) -> None:
        """When adaptive_controller is None, _current_batch_max equals batch_max_size."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
        worker = _make_worker(queue=queue, batch_max_size=128)
        assert worker._current_batch_max == 128


class TestAdaptiveBatchSizingEnabled:
    """AC1-AC4, AC6: Worker uses AdaptiveController for dynamic batch sizing."""

    async def test_enabled_uses_adaptive_size(self) -> None:
        """When controller is provided, worker starts with batch_max_size but adapts."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=100)
        controller = AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=1, max_batch=1024, target_latency_ms=5.0
            )
        )
        worker = _make_worker(
            queue=queue, adaptive_controller=controller, batch_max_size=100
        )
        assert worker._current_batch_max == 100
        assert worker._adaptive_controller is controller

    async def test_batch_grows_when_sink_is_fast(self) -> None:
        """AC3: When sink latency is below target, batch size increases."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        fast_sink = AsyncMock()
        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=200)

        controller = AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=1,
                max_batch=1024,
                target_latency_ms=5.0,
                aggressiveness=0.5,
            )
        )
        worker = _make_worker(
            queue=queue,
            adaptive_controller=controller,
            batch_max_size=50,
            sink_write=fast_sink,
        )

        # Enqueue 50 events and flush — sink is fast (nearly instant)
        batch = [{"level": "INFO", "message": f"event-{i}"} for i in range(50)]
        await worker.flush_batch(batch)

        # Batch should grow since mock sink completes instantly (~0 latency)
        assert worker._current_batch_max > 50

    async def test_batch_shrinks_when_sink_is_slow(self) -> None:
        """AC2: When sink latency increases, batch size decreases."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        async def slow_sink(entry: dict[str, Any]) -> None:
            await asyncio.sleep(0.02)  # 20ms per event

        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=200)

        controller = AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=1,
                max_batch=1024,
                target_latency_ms=0.5,  # Low target to ensure shrink
                aggressiveness=0.5,
            )
        )
        worker = _make_worker(
            queue=queue,
            adaptive_controller=controller,
            batch_max_size=100,
            sink_write=slow_sink,
        )

        # Flush 10 events through slow sink
        batch = [{"level": "INFO", "message": f"event-{i}"} for i in range(10)]
        await worker.flush_batch(batch)

        # Batch should shrink since latency exceeds target
        assert worker._current_batch_max < 100

    async def test_batch_bounded_by_min_max(self) -> None:
        """AC4: Batch size never drops below min or exceeds max."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=200)

        controller = AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=10,
                max_batch=200,
                target_latency_ms=5.0,
            )
        )
        worker = _make_worker(
            queue=queue,
            adaptive_controller=controller,
            batch_max_size=100,
            sink_write=AsyncMock(),
        )

        # Flush multiple times with instant sink to push toward max
        for _ in range(20):
            batch = [{"level": "INFO", "message": "fast"} for _ in range(50)]
            await worker.flush_batch(batch)

        assert worker._current_batch_max <= 200
        assert worker._current_batch_max >= 10

    async def test_ewma_smoothing_absorbs_spikes(self) -> None:
        """AC6: EWMA smoothing prevents batch size oscillation from spikes."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        call_count = 0

        async def variable_sink(entry: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            # One spike at call 50-60, otherwise fast
            if 50 <= call_count <= 60:
                await asyncio.sleep(0.05)  # 50ms spike

        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=500)
        controller = AdaptiveController(
            batch_sizer=AdaptiveBatchSizer(
                min_batch=1,
                max_batch=500,
                target_latency_ms=5.0,
                aggressiveness=0.5,
            ),
            latency_ewma_alpha=0.3,
        )
        worker = _make_worker(
            queue=queue,
            adaptive_controller=controller,
            batch_max_size=100,
            sink_write=variable_sink,
        )

        # Several fast flushes to establish baseline
        sizes_before_spike: list[int] = []
        for _ in range(5):
            batch = [{"level": "INFO", "message": "steady"} for _ in range(10)]
            await worker.flush_batch(batch)
            sizes_before_spike.append(worker._current_batch_max)

        # One flush during spike
        batch = [{"level": "INFO", "message": "spike"} for _ in range(10)]
        await worker.flush_batch(batch)
        size_after_spike = worker._current_batch_max

        # Batch should not collapse to near min — EWMA absorbs the spike
        # It may decrease but shouldn't crash to min_batch (1)
        assert size_after_spike >= 10, (
            f"Batch size collapsed to {size_after_spike} after spike; "
            "EWMA should absorb transient spikes"
        )


class TestLoggerCreatesController:
    """Tests that _make_worker passes AdaptiveController when batch_sizing=True."""

    async def test_make_worker_no_controller_when_disabled(self) -> None:
        """Default: _make_worker creates worker without adaptive controller."""
        from fapilog.core.logger import SyncLoggerFacade

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=64,
            batch_timeout_seconds=0.25,
            backpressure_wait_ms=50,
            drop_on_full=True,
            sink_write=AsyncMock(),
        )
        worker = logger._make_worker()
        assert worker._adaptive_controller is None
        assert worker._current_batch_max == 64

    async def test_make_worker_with_controller_when_enabled(self) -> None:
        """When adaptive.batch_sizing=True, _make_worker passes a controller."""
        from fapilog.core.logger import SyncLoggerFacade

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=64,
            batch_timeout_seconds=0.25,
            backpressure_wait_ms=50,
            drop_on_full=True,
            sink_write=AsyncMock(),
        )
        # Simulate batch_sizing=True in cached settings
        logger._cached_adaptive_batch_sizing = True

        worker = logger._make_worker()
        assert isinstance(worker._adaptive_controller, AdaptiveController)
        assert worker._current_batch_max == 64
