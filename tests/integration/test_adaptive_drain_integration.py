"""Integration tests for AdaptiveDrainSummary through DrainResult."""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from fapilog.core.logger import AdaptiveDrainSummary, DrainResult, SyncLoggerFacade
from fapilog.core.pressure import PressureLevel, PressureMonitor


async def _noop_sink(entry: dict[str, Any]) -> None:
    pass


async def _slow_sink(entry: dict[str, Any]) -> None:
    await asyncio.sleep(100.0)


class TestContractSnapshotToDrainResult:
    """AC8: PressureMonitor.snapshot() output is valid DrainResult.adaptive input."""

    def test_snapshot_feeds_drain_result(self) -> None:
        queue = MagicMock()
        queue.qsize.return_value = 0
        queue.capacity = 100
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        monitor._tick()
        snapshot = monitor.snapshot()
        result = DrainResult(
            submitted=0,
            processed=0,
            dropped=0,
            retried=0,
            queue_depth_high_watermark=0,
            flush_latency_seconds=0.0,
            adaptive=snapshot,
        )
        assert result.adaptive is snapshot
        assert isinstance(result.adaptive, AdaptiveDrainSummary)

    def test_snapshot_after_transitions_feeds_drain_result(self) -> None:
        queue = MagicMock()
        queue.capacity = 100
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        # NORMAL → ELEVATED
        queue.qsize.return_value = 70
        monitor._tick()
        monitor.record_filter_swap()
        monitor.record_worker_scaling(4)
        snapshot = monitor.snapshot()
        result = DrainResult(
            submitted=10,
            processed=8,
            dropped=2,
            retried=0,
            queue_depth_high_watermark=70,
            flush_latency_seconds=0.5,
            adaptive=snapshot,
        )
        assert result.adaptive.peak_pressure_level == PressureLevel.ELEVATED
        assert result.adaptive.escalation_count == 1
        assert result.adaptive.filters_swapped == 1
        assert result.adaptive.peak_workers == 4


class TestDrainResultAdaptiveNoneWhenDisabled:
    """AC2: DrainResult.adaptive is None when adaptive is disabled."""

    @pytest.mark.asyncio
    async def test_drain_result_adaptive_none_when_disabled(self) -> None:
        logger = SyncLoggerFacade(
            name="t-no-adaptive-summary",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        logger.start()
        logger.info("hello")
        result = await logger.stop_and_drain()
        assert result.adaptive is None
        assert result.submitted == 1
        assert result.processed == 1


class TestDrainResultAdaptivePopulatedWhenEnabled:
    """AC3: DrainResult.adaptive is populated when adaptive is enabled."""

    @pytest.mark.asyncio
    async def test_drain_result_adaptive_populated_when_enabled(self) -> None:
        logger = SyncLoggerFacade(
            name="t-adaptive-summary",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        logger.info("test-adaptive")
        result = await logger.stop_and_drain()

        assert isinstance(result.adaptive, AdaptiveDrainSummary)
        # No load applied, so should stay at NORMAL with zero escalations
        assert result.adaptive.peak_pressure_level == PressureLevel.NORMAL
        assert result.adaptive.escalation_count == 0
        assert result.adaptive.deescalation_count == 0
        assert result.adaptive.time_at_level[PressureLevel.NORMAL] > 0


class TestAdaptiveSummaryReflectsTransitions:
    """AC4/AC5: Summary reflects actual transitions and time-at-level."""

    @pytest.mark.asyncio
    async def test_adaptive_summary_reflects_actual_transitions(self) -> None:
        logger = SyncLoggerFacade(
            name="t-transition",
            queue_capacity=100,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_slow_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        # Fill queue to trigger escalation (slow sink blocks processing)
        for i in range(70):
            logger.info("fill", idx=i)

        # Give monitor time to detect pressure
        await asyncio.sleep(0.15)

        assert isinstance(logger._pressure_monitor, PressureMonitor)
        # Capture snapshot before cleanup — 70% fill triggers at least ELEVATED
        snapshot = logger._pressure_monitor.snapshot()
        assert snapshot.escalation_count >= 1  # noqa: WA002 — async timing makes exact count non-deterministic
        assert snapshot.peak_pressure_level in (
            PressureLevel.ELEVATED,
            PressureLevel.HIGH,
            PressureLevel.CRITICAL,
        )

        # Clean up
        logger._pressure_monitor.stop()
        if logger._pressure_monitor_task is not None:
            logger._pressure_monitor_task.cancel()
            try:
                await logger._pressure_monitor_task
            except asyncio.CancelledError:
                pass
        for task in logger._worker_tasks:
            task.cancel()
        await asyncio.gather(*logger._worker_tasks, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_time_at_level_sums_to_approximate_lifetime(self) -> None:
        logger = SyncLoggerFacade(
            name="t-time-sum",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        await asyncio.sleep(0.1)
        result = await logger.stop_and_drain()

        assert isinstance(result.adaptive, AdaptiveDrainSummary)
        total = sum(result.adaptive.time_at_level.values())
        # Total should approximate elapsed time (at least 50ms of the 100ms sleep)
        assert total >= 0.05


class TestThreadModeDrainCapturesSummary:
    """AC7: snapshot() called before monitor stop in thread mode drain path."""

    def test_thread_mode_drain_captures_adaptive_summary(self) -> None:
        logger = SyncLoggerFacade(
            name="t-thread-summary",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        def start_in_thread() -> None:
            logger.start()

        t = threading.Thread(target=start_in_thread)
        t.start()
        t.join(timeout=3.0)

        assert isinstance(logger._pressure_monitor, PressureMonitor)

        result = logger._drain_thread_mode(warn_on_timeout=False)
        assert isinstance(result.adaptive, AdaptiveDrainSummary)
        # No load applied, so should be NORMAL with time > 0
        assert result.adaptive.peak_pressure_level == PressureLevel.NORMAL
        assert result.adaptive.time_at_level[PressureLevel.NORMAL] > 0
