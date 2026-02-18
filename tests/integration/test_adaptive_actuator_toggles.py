"""Integration tests for per-actuator adaptive toggles (Story 1.51)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.core.pressure import PressureLevel
from fapilog.core.settings import AdaptiveSettings


async def _noop_sink(entry: dict[str, Any]) -> None:
    pass


async def _slow_sink(entry: dict[str, Any]) -> None:
    await asyncio.sleep(100.0)


def _make_logger_with_adaptive(settings: AdaptiveSettings) -> SyncLoggerFacade:
    """Create a logger with pre-cached adaptive settings."""
    logger = SyncLoggerFacade(
        name="t-toggle",
        queue_capacity=100,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_noop_sink,
    )
    logger._cached_adaptive_enabled = True
    logger._cached_adaptive_settings = settings
    return logger


class TestDefaultsBackwardCompatible:
    """AC6: All three toggles default to True."""

    def test_filter_tightening_defaults_true(self) -> None:
        settings = AdaptiveSettings(enabled=True)
        assert settings.filter_tightening is True

    def test_worker_scaling_defaults_true(self) -> None:
        settings = AdaptiveSettings(enabled=True)
        assert settings.worker_scaling is True


class TestWorkerScalingToggle:
    """AC1: worker_scaling=False prevents WorkerPool creation."""

    @pytest.mark.asyncio
    async def test_worker_scaling_disabled_no_pool(self) -> None:
        settings = AdaptiveSettings(
            enabled=True,
            worker_scaling=False,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )
        logger = _make_logger_with_adaptive(settings)
        logger.start()

        # Monitor should exist but WorkerPool should not
        assert logger._pressure_monitor is not None  # noqa: WA003
        assert logger._worker_pool is None

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_worker_scaling_enabled_creates_pool(self) -> None:
        settings = AdaptiveSettings(
            enabled=True,
            worker_scaling=True,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )
        logger = _make_logger_with_adaptive(settings)
        logger.start()

        assert logger._pressure_monitor is not None  # noqa: WA003
        assert logger._worker_pool is not None  # noqa: WA003

        await logger.stop_and_drain()


class TestFilterTighteningToggle:
    """AC3: filter_tightening=False prevents filter ladder construction."""

    @pytest.mark.asyncio
    async def test_filter_tightening_disabled_no_ladder(self) -> None:
        settings = AdaptiveSettings(
            enabled=True,
            filter_tightening=False,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )
        logger = _make_logger_with_adaptive(settings)
        logger.start()

        assert logger._pressure_monitor is not None  # noqa: WA003
        assert logger._adaptive_filter_ladder is None

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_filter_tightening_enabled_builds_ladder(self) -> None:
        settings = AdaptiveSettings(
            enabled=True,
            filter_tightening=True,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )
        logger = _make_logger_with_adaptive(settings)
        logger.start()

        assert logger._pressure_monitor is not None  # noqa: WA003
        assert logger._adaptive_filter_ladder is not None  # noqa: WA003

        await logger.stop_and_drain()


class TestFilterTighteningWithOthersDisabled:
    """AC4: Filter tightening works when scaling is disabled."""

    @pytest.mark.asyncio
    async def test_filter_tightening_works_with_scaling_disabled(
        self,
    ) -> None:
        settings = AdaptiveSettings(
            enabled=True,
            filter_tightening=True,
            worker_scaling=False,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )
        logger = _make_logger_with_adaptive(settings)
        logger.start()

        # Filter ladder should exist (filter tightening is enabled)
        assert logger._adaptive_filter_ladder is not None  # noqa: WA003
        ladder = logger._adaptive_filter_ladder
        assert PressureLevel.NORMAL in ladder
        assert PressureLevel.ELEVATED in ladder
        assert PressureLevel.HIGH in ladder
        assert PressureLevel.CRITICAL in ladder

        # Worker pool should NOT exist (worker scaling disabled)
        assert logger._worker_pool is None

        initial_capacity = logger._queue.capacity

        # Fill queue to trigger escalation
        for _ in range(95):
            logger._queue.try_enqueue({"level": "INFO", "message": "fill"})
        await asyncio.sleep(0.05)

        # Queue capacity should NOT have grown (growth disabled)
        assert logger._queue.capacity == initial_capacity

        await logger.stop_and_drain()
