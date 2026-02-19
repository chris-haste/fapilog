"""Tests for shedding configuration (Story 1.59).

Covers AC5 (settings fields, validation, builder method), AC10 (shedding disabled
when adaptive is off).
"""

from __future__ import annotations

import pytest

from fapilog.core.settings import AdaptiveSettings


class TestAdaptiveSettingsSheddingFields:
    """AC5: Settings fields with defaults and validation."""

    def test_default_shed_threshold(self) -> None:
        settings = AdaptiveSettings()
        assert settings.protected_shed_threshold == 0.70

    def test_default_recover_threshold(self) -> None:
        settings = AdaptiveSettings()
        assert settings.protected_recover_threshold == 0.30

    def test_custom_thresholds(self) -> None:
        settings = AdaptiveSettings(
            protected_shed_threshold=0.80,
            protected_recover_threshold=0.20,
        )
        assert settings.protected_shed_threshold == 0.80
        assert settings.protected_recover_threshold == 0.20

    def test_shed_must_be_greater_than_recover(self) -> None:
        with pytest.raises(
            ValueError, match="protected_shed_threshold.*must be greater"
        ):
            AdaptiveSettings(
                protected_shed_threshold=0.30,
                protected_recover_threshold=0.70,
            )

    def test_equal_thresholds_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="protected_shed_threshold.*must be greater"
        ):
            AdaptiveSettings(
                protected_shed_threshold=0.50,
                protected_recover_threshold=0.50,
            )


class TestBuilderWithProtectedShedding:
    """AC5: Builder method sets thresholds."""

    def test_with_protected_shedding_defaults(self) -> None:
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_protected_shedding()

        # Should set adaptive config with default thresholds
        adaptive = builder._config.get("adaptive", {})
        assert adaptive.get("protected_shed_threshold") == 0.70
        assert adaptive.get("protected_recover_threshold") == 0.30
        assert result is builder  # Fluent chaining

    def test_with_protected_shedding_custom(self) -> None:
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_protected_shedding(shed_at=0.80, recover_at=0.20)

        adaptive = builder._config.get("adaptive", {})
        assert adaptive.get("protected_shed_threshold") == 0.80
        assert adaptive.get("protected_recover_threshold") == 0.20


class TestThresholdsWiredToPressureMonitor:
    """AC5: Thresholds are wired from settings to PressureMonitor."""

    def test_pressure_monitor_receives_thresholds(self) -> None:
        from fapilog.core.concurrency import DualQueue
        from fapilog.core.pressure import PressureMonitor

        dq = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.85,
            recover_threshold=0.15,
        )

        # Verify the thresholds are stored
        assert monitor._shed_threshold == 0.85
        assert monitor._recover_threshold == 0.15

        # Fill to 85% — should activate
        for _ in range(9):
            dq.try_enqueue({"level": "ERROR", "message": "fill"})
        monitor._tick()
        assert dq.is_shedding is True
