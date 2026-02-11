"""Integration tests for dynamic worker scaling (Story 1.46).

Tests the full integration of WorkerPool with the logger and
PressureMonitor to verify dynamic scaling under pressure changes.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.core.pressure import PressureLevel, PressureMonitor
from fapilog.core.settings import AdaptiveSettings
from fapilog.core.worker_pool import WorkerPool


async def _noop_sink(entry: dict[str, Any]) -> None:
    pass


async def _slow_sink(entry: dict[str, Any]) -> None:
    await asyncio.sleep(100.0)


def _make_adaptive_logger(
    *,
    sink: Any = None,
    num_workers: int = 2,
    max_workers: int = 6,
    queue_capacity: int = 100,
) -> SyncLoggerFacade:
    """Create a logger with adaptive scaling enabled."""
    logger = SyncLoggerFacade(
        name="t-dynamic-scaling",
        queue_capacity=queue_capacity,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=sink or _noop_sink,
        num_workers=num_workers,
    )
    logger._cached_adaptive_enabled = True
    logger._cached_adaptive_settings = AdaptiveSettings(
        enabled=True,
        check_interval_seconds=0.01,
        cooldown_seconds=0.0,
        max_workers=max_workers,
    )
    return logger


class TestScaleUpOnPressure:
    @pytest.mark.asyncio
    async def test_worker_pool_created_when_adaptive_enabled(self) -> None:
        logger = _make_adaptive_logger()
        logger.start()
        assert isinstance(logger._worker_pool, WorkerPool)
        assert logger._worker_pool.current_count == 2
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_scale_up_on_high_pressure(self) -> None:
        """Workers scale up when pressure reaches HIGH via pool callback."""
        logger = _make_adaptive_logger(
            sink=_noop_sink,
            num_workers=2,
            max_workers=6,
        )
        logger.start()
        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        # Directly simulate what the monitor callback does:
        # target_for_level(HIGH) on initial_count=2 → ceil(2 * 1.5) = 3
        target = pool.target_for_level(PressureLevel.HIGH)
        pool.scale_to(target)
        assert pool.current_count == 3
        assert pool.dynamic_count == 1

        # Scale further for CRITICAL
        target = pool.target_for_level(PressureLevel.CRITICAL)
        pool.scale_to(target)
        assert pool.current_count == 4
        assert pool.dynamic_count == 2

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_scale_down_on_normal_pressure(self) -> None:
        """Workers scale back down when pressure returns to NORMAL."""
        logger = _make_adaptive_logger(num_workers=2, max_workers=6)
        logger.start()
        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        # Directly scale up then down via pool
        pool.scale_to(4)
        assert pool.current_count == 4
        assert pool.dynamic_count == 2

        pool.scale_to(2)
        assert pool.current_count == 2
        assert pool.dynamic_count == 0

        await logger.stop_and_drain()


class TestDrainWithDynamicWorkers:
    @pytest.mark.asyncio
    async def test_drain_handles_dynamic_workers(self) -> None:
        """Logger drain waits for both initial and dynamic workers."""
        collected: list[dict[str, Any]] = []

        async def collecting_sink(entry: dict[str, Any]) -> None:
            collected.append(dict(entry))

        logger = _make_adaptive_logger(
            sink=collecting_sink,
            num_workers=2,
            max_workers=6,
        )
        logger.start()
        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        # Scale up
        pool.scale_to(4)
        assert pool.current_count == 4

        # Enqueue some events
        for i in range(5):
            logger.info(f"msg-{i}")

        # Drain should complete without orphaned tasks
        result = await logger.stop_and_drain()
        assert result.submitted == 5
        assert result.processed == 5
        assert result.dropped == 0

    @pytest.mark.asyncio
    async def test_no_events_lost_during_scale_down(self) -> None:
        """Events in flight are not lost when workers are retired."""
        collected: list[dict[str, Any]] = []

        async def collecting_sink(entry: dict[str, Any]) -> None:
            collected.append(dict(entry))

        logger = _make_adaptive_logger(
            sink=collecting_sink,
            num_workers=2,
            max_workers=6,
        )
        logger.start()
        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        # Enqueue events with scaled-up workers
        pool.scale_to(4)
        for i in range(10):
            logger.info(f"msg-{i}")
        await asyncio.sleep(0.1)

        # Scale down while events may be processing
        pool.scale_to(2)

        # Drain to ensure all events processed
        result = await logger.stop_and_drain()
        assert result.submitted == 10
        assert result.processed == 10
        assert result.dropped == 0


class TestWorkerPoolNotCreatedWhenDisabled:
    @pytest.mark.asyncio
    async def test_no_pool_when_adaptive_disabled(self) -> None:
        logger = SyncLoggerFacade(
            name="t-no-pool",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        logger.start()
        assert logger._worker_pool is None
        await logger.stop_and_drain()


class TestScalingCallbackIntegration:
    @pytest.mark.asyncio
    async def test_monitor_callback_triggers_scaling(self) -> None:
        """Pressure monitor callback fires _on_scaling_change which scales pool."""
        logger = _make_adaptive_logger(num_workers=2, max_workers=6)
        logger.start()

        monitor = logger._pressure_monitor
        pool = logger._worker_pool
        assert isinstance(monitor, PressureMonitor)
        assert isinstance(pool, WorkerPool)

        # Fire callbacks directly as monitor would
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.HIGH)

        # Pool should have scaled to ceil(2 * 1.5) = 3
        assert pool.current_count == 3
        assert pool.dynamic_count == 1

        # Scale back down
        for cb in monitor._callbacks:
            cb(PressureLevel.HIGH, PressureLevel.NORMAL)

        assert pool.current_count == 2
        assert pool.dynamic_count == 0

        await logger.stop_and_drain()


class TestFailOpenBehavior:
    @pytest.mark.asyncio
    async def test_pool_creation_failure_does_not_break_startup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If WorkerPool import/init fails, logger still starts."""
        import fapilog.core.logger as logger_mod

        def _broken_pool(self_: Any, monitor: Any, loop: Any, adaptive: Any) -> None:
            raise RuntimeError("simulated pool failure")

        monkeypatch.setattr(
            logger_mod._LoggerMixin, "_maybe_start_worker_pool", _broken_pool
        )
        logger = _make_adaptive_logger()
        logger.start()
        # Logger should still work despite pool failure
        assert logger._worker_pool is None
        logger.info("still works")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_scaling_callback_error_does_not_crash(self) -> None:
        """If scale_to fails inside callback, it's contained."""
        logger = _make_adaptive_logger(num_workers=2, max_workers=6)
        logger.start()

        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        # Break the pool's scale_to to trigger the inner except
        original_scale = pool.scale_to
        pool.scale_to = lambda t: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[assignment]

        monitor = logger._pressure_monitor
        assert isinstance(monitor, PressureMonitor)

        # Fire callbacks — should not raise
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.HIGH)

        # Restore and cleanup
        pool.scale_to = original_scale  # type: ignore[assignment]
        await logger.stop_and_drain()


class TestBoundsEnforced:
    @pytest.mark.asyncio
    async def test_max_workers_cap(self) -> None:
        logger = _make_adaptive_logger(
            num_workers=2,
            max_workers=4,
        )
        logger.start()
        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        pool.scale_to(10)
        assert pool.current_count == 4  # Capped

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_min_workers_floor(self) -> None:
        logger = _make_adaptive_logger(num_workers=2)
        logger.start()
        pool = logger._worker_pool
        assert isinstance(pool, WorkerPool)

        pool.scale_to(1)
        assert pool.current_count == 2  # Floor at initial

        await logger.stop_and_drain()
