"""Integration tests for adaptive queue capacity growth (Story 1.48).

Tests that the capacity growth callback is registered at startup,
grows capacity on pressure escalation, respects ceiling, and does
not shrink on de-escalation.
"""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.concurrency import PriorityAwareQueue
from fapilog.core.pressure import PressureLevel, PressureMonitor
from fapilog.core.settings import AdaptiveSettings


async def _noop_sink(entry: dict[str, Any]) -> None:
    pass


def _make_logger(**overrides: Any) -> Any:
    from fapilog.core.logger import SyncLoggerFacade

    defaults: dict[str, Any] = {
        "name": "t-queue-growth",
        "queue_capacity": 100,
        "batch_max_size": 8,
        "batch_timeout_seconds": 0.05,
        "backpressure_wait_ms": 10,
        "drop_on_full": True,
        "sink_write": _noop_sink,
    }
    defaults.update(overrides)
    return SyncLoggerFacade(**defaults)


class TestCapacityGrowthCallbackRegistered:
    """Verify that the capacity growth callback is wired at startup."""

    @pytest.mark.asyncio
    async def test_callback_registered_when_adaptive_enabled(self) -> None:
        logger = _make_logger()
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()

        monitor = logger._pressure_monitor
        assert isinstance(monitor, PressureMonitor)
        # At least 3 callbacks: filter, scaling, capacity growth
        assert len(monitor._callbacks) >= 3

        await logger.stop_and_drain()


class TestCapacityGrowsOnEscalation:
    """AC4: Controller grows capacity proportionally to pressure level."""

    @pytest.mark.asyncio
    async def test_capacity_grows_on_elevated(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        queue = logger._queue
        assert isinstance(queue, PriorityAwareQueue)
        assert queue.capacity == 100

        monitor = logger._pressure_monitor
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.ELEVATED)

        # ELEVATED = 1.0 + (4.0-1.0)*0.25 = 1.75x initial → 175
        assert queue.capacity == 175

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_capacity_grows_on_high(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        queue = logger._queue

        monitor = logger._pressure_monitor
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.HIGH)

        # HIGH = 1.0 + (4.0-1.0)*0.50 = 2.5x initial → 250
        assert queue.capacity == 250

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_capacity_grows_on_critical(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        queue = logger._queue

        monitor = logger._pressure_monitor
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.CRITICAL)

        # CRITICAL = max_queue_growth = 4.0x initial → 400
        assert queue.capacity == 400

        await logger.stop_and_drain()


class TestCapacityCeiling:
    """AC5: Capacity never exceeds initial * max_queue_growth."""

    @pytest.mark.asyncio
    async def test_capacity_capped_at_ceiling(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
            max_queue_growth=1.5,  # Ceiling = 150
        )

        logger.start()
        queue = logger._queue

        monitor = logger._pressure_monitor
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.CRITICAL)

        # CRITICAL wants 2.0x = 200, but ceiling is 1.5x = 150
        assert queue.capacity == 150

        await logger.stop_and_drain()


class TestGrowthAbove2xIsEffective:
    """AC3: max_queue_growth > 2.0 produces proportionally higher capacity."""

    @pytest.mark.asyncio
    async def test_growth_above_2x_is_effective(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
            max_queue_growth=6.0,
        )

        logger.start()
        queue = logger._queue

        monitor = logger._pressure_monitor
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.CRITICAL)

        # CRITICAL = max_queue_growth = 6.0x → 600
        assert queue.capacity == 600

        await logger.stop_and_drain()


class TestBackwardCompatibleAt2x:
    """AC5: max_queue_growth=2.0 reproduces old hardcoded multipliers."""

    @pytest.mark.asyncio
    async def test_backward_compatible_at_2x(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
            max_queue_growth=2.0,
        )

        logger.start()
        queue = logger._queue
        assert isinstance(queue, PriorityAwareQueue)

        monitor = logger._pressure_monitor

        # ELEVATED = 1.0 + (2.0-1.0)*0.25 = 1.25 → 125
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.ELEVATED)
        assert queue.capacity == 125

        # HIGH = 1.0 + (2.0-1.0)*0.50 = 1.5 → 150
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.HIGH)
        assert queue.capacity == 150

        # CRITICAL = 2.0 → 200
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.CRITICAL)
        assert queue.capacity == 200

        await logger.stop_and_drain()


class TestCapacityDoesNotShrinkOnDeescalation:
    """AC6: Capacity stays at grown size when pressure drops."""

    @pytest.mark.asyncio
    async def test_no_shrink_on_deescalation(self) -> None:
        logger = _make_logger(queue_capacity=100)
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        queue = logger._queue

        monitor = logger._pressure_monitor
        # Escalate to CRITICAL → 400 (4.0x default)
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.CRITICAL)
        assert queue.capacity == 400

        # De-escalate to NORMAL → capacity stays at 400 (grow-only)
        for cb in monitor._callbacks:
            cb(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        assert queue.capacity == 400

        await logger.stop_and_drain()


class TestCapacityGrowthDiagnostic:
    """Verify diagnostic is emitted on capacity growth."""

    @pytest.mark.asyncio
    async def test_diagnostic_emitted_on_growth(self) -> None:
        diagnostics: list[tuple[str, str]] = []

        original_warn = None

        def _capture_warn(component: str, message: str, **kwargs: Any) -> None:
            diagnostics.append((component, message))
            if original_warn is not None:
                original_warn(component, message, **kwargs)

        import fapilog.core.diagnostics as diag_mod

        original_warn = diag_mod.warn
        diag_mod.warn = _capture_warn

        try:
            logger = _make_logger(queue_capacity=100)
            logger._cached_adaptive_enabled = True
            logger._cached_adaptive_settings = AdaptiveSettings(
                enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
            )

            logger.start()
            monitor = logger._pressure_monitor
            for cb in monitor._callbacks:
                cb(PressureLevel.NORMAL, PressureLevel.ELEVATED)

            growth_diags = [
                (c, m)
                for c, m in diagnostics
                if c == "adaptive-controller" and "capacity" in m
            ]
            assert len(growth_diags) == 1
            assert growth_diags[0][1] == "queue capacity grown"

            await logger.stop_and_drain()
        finally:
            diag_mod.warn = original_warn
