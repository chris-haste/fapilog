"""Integration tests for adaptive filter tightening (Story 1.45).

Tests that the filter ladder is built at startup when adaptive is enabled,
the pressure callback swaps filter snapshots, and de-escalation restores them.
"""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.core.pressure import PressureLevel, PressureMonitor
from fapilog.plugins.filters.adaptive_sampling import AdaptiveSamplingFilter
from fapilog.plugins.filters.level import LevelFilter, LevelFilterConfig


async def _noop_sink(entry: dict[str, Any]) -> None:
    pass


def _make_logger(**overrides: Any) -> SyncLoggerFacade:
    defaults: dict[str, Any] = {
        "name": "t-filter-tightening",
        "queue_capacity": 100,
        "batch_max_size": 8,
        "batch_timeout_seconds": 0.05,
        "backpressure_wait_ms": 10,
        "drop_on_full": True,
        "sink_write": _noop_sink,
    }
    defaults.update(overrides)
    return SyncLoggerFacade(**defaults)


class TestFilterLadderBuiltAtStartup:
    """AC1: Filter tuples pre-built at startup when adaptive enabled."""

    @pytest.mark.asyncio
    async def test_ladder_built_when_adaptive_enabled(self) -> None:
        """Logger builds _adaptive_filter_ladder dict on start()."""
        from fapilog.core.settings import AdaptiveSettings

        logger = _make_logger()
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()

        assert hasattr(logger, "_adaptive_filter_ladder")
        assert isinstance(logger._adaptive_filter_ladder, dict)
        assert set(logger._adaptive_filter_ladder.keys()) == {
            PressureLevel.NORMAL,
            PressureLevel.ELEVATED,
            PressureLevel.HIGH,
            PressureLevel.CRITICAL,
        }

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_ladder_not_built_when_adaptive_disabled(self) -> None:
        """Logger does not build ladder when adaptive is disabled."""
        logger = _make_logger()
        logger.start()

        assert (
            not hasattr(logger, "_adaptive_filter_ladder")
            or logger._adaptive_filter_ladder is None
        )

        await logger.stop_and_drain()


class TestFilterSwapOnPressureChange:
    """AC6: Filter swap via existing cache invalidation on level change."""

    @pytest.mark.asyncio
    async def test_callback_swaps_filters_snapshot(self) -> None:
        """Pressure change callback sets _filters_snapshot to the ladder entry."""
        from fapilog.core.settings import AdaptiveSettings

        user_filter = LevelFilter(config=LevelFilterConfig(min_level="INFO"))
        logger = _make_logger(filters=[user_filter])
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        original_snapshot = logger._filters_snapshot

        # Verify NORMAL snapshot matches user filters
        assert user_filter in original_snapshot

        # Simulate pressure escalation by calling the registered callback
        monitor = logger._pressure_monitor
        assert isinstance(monitor, PressureMonitor)
        assert len(monitor._callbacks) >= 1  # noqa: WA002

        # Fire the callback for NORMAL -> ELEVATED
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.ELEVATED)

        # Snapshot should now be the ELEVATED ladder entry
        elevated_snapshot = logger._filters_snapshot
        assert elevated_snapshot is not original_snapshot
        adaptive_filters = [
            f for f in elevated_snapshot if isinstance(f, AdaptiveSamplingFilter)
        ]
        assert len(adaptive_filters) == 1

        await logger.stop_and_drain()


class TestDeescalationRestoresFilters:
    """AC7: De-escalation restores previous filter set."""

    @pytest.mark.asyncio
    async def test_deescalation_restores_normal_filters(self) -> None:
        """ELEVATED -> NORMAL restores user-configured filters."""
        from fapilog.core.settings import AdaptiveSettings

        user_filter = LevelFilter(config=LevelFilterConfig(min_level="INFO"))
        logger = _make_logger(filters=[user_filter])
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        normal_snapshot = logger._filters_snapshot

        monitor = logger._pressure_monitor
        assert isinstance(monitor, PressureMonitor)

        # Escalate then de-escalate
        for cb in monitor._callbacks:
            cb(PressureLevel.NORMAL, PressureLevel.ELEVATED)
        assert logger._filters_snapshot is not normal_snapshot

        for cb in monitor._callbacks:
            cb(PressureLevel.ELEVATED, PressureLevel.NORMAL)
        restored = logger._filters_snapshot
        assert restored == normal_snapshot

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_critical_to_high_restores_high_filters(self) -> None:
        """CRITICAL -> HIGH restores HIGH-level filters."""
        from fapilog.core.settings import AdaptiveSettings

        logger = _make_logger()
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        ladder = logger._adaptive_filter_ladder

        monitor = logger._pressure_monitor
        assert isinstance(monitor, PressureMonitor)

        # Jump to CRITICAL
        for cb in monitor._callbacks:
            cb(PressureLevel.HIGH, PressureLevel.CRITICAL)
        assert logger._filters_snapshot == ladder[PressureLevel.CRITICAL]

        # De-escalate to HIGH
        for cb in monitor._callbacks:
            cb(PressureLevel.CRITICAL, PressureLevel.HIGH)
        assert logger._filters_snapshot == ladder[PressureLevel.HIGH]

        await logger.stop_and_drain()


class TestDiagnosticOnFilterSwap:
    """AC8: Diagnostic emitted on filter swap."""

    @pytest.mark.asyncio
    async def test_diagnostic_emitted_on_swap(self) -> None:
        """Filter swap emits a diagnostic via diagnostics.warn()."""
        from fapilog.core.settings import AdaptiveSettings

        logger = _make_logger()
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        emitted: list[dict[str, Any]] = []
        original_warn = None

        import fapilog.core.diagnostics as diag_mod

        original_warn = diag_mod.warn

        def capture_warn(component: str, message: str, **fields: Any) -> None:
            emitted.append({"component": component, "message": message, **fields})

        diag_mod.warn = capture_warn  # type: ignore[assignment]
        try:
            logger.start()

            monitor = logger._pressure_monitor
            assert isinstance(monitor, PressureMonitor)

            for cb in monitor._callbacks:
                cb(PressureLevel.NORMAL, PressureLevel.ELEVATED)

            # Should have captured a diagnostic about filter tightening
            filter_diags = [
                d
                for d in emitted
                if "adaptive-controller" in d.get("component", "")
                and "filter" in d.get("message", "").lower()
            ]
            assert len(filter_diags) == 1
            assert filter_diags[0]["pressure_level"] == "elevated"
        finally:
            diag_mod.warn = original_warn  # type: ignore[assignment]

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_diagnostic_failure_does_not_break_swap(self) -> None:
        """If diagnostics.warn raises, filter swap still succeeds."""
        from fapilog.core.settings import AdaptiveSettings

        logger = _make_logger()
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        import fapilog.core.diagnostics as diag_mod

        original_warn = diag_mod.warn

        def broken_warn(component: str, message: str, **fields: Any) -> None:
            raise RuntimeError("boom")

        diag_mod.warn = broken_warn  # type: ignore[assignment]
        try:
            logger.start()
            ladder = logger._adaptive_filter_ladder

            monitor = logger._pressure_monitor
            assert isinstance(monitor, PressureMonitor)

            # Fire callback — diagnostic will fail but swap should succeed
            for cb in monitor._callbacks:
                cb(PressureLevel.NORMAL, PressureLevel.HIGH)

            assert logger._filters_snapshot == ladder[PressureLevel.HIGH]
        finally:
            diag_mod.warn = original_warn  # type: ignore[assignment]

        await logger.stop_and_drain()


class TestLadderBuildFailOpen:
    """Fail-open: ladder build failure doesn't block monitor startup."""

    @pytest.mark.asyncio
    async def test_ladder_failure_still_starts_monitor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If build_filter_ladder raises, monitor still starts."""
        from fapilog.core.settings import AdaptiveSettings

        logger = _make_logger()
        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        import fapilog.core.filter_ladder as fl_mod

        def broken_build(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("build failed")

        monkeypatch.setattr(fl_mod, "build_filter_ladder", broken_build)

        logger.start()

        # Monitor should still be running despite ladder failure
        assert isinstance(logger._pressure_monitor, PressureMonitor)
        # Ladder should be None since build failed
        assert logger._adaptive_filter_ladder is None

        await logger.stop_and_drain()
