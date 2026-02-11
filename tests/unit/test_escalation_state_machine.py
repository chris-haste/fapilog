"""Unit tests for EscalationStateMachine and PressureLevel."""

from __future__ import annotations

import time
from unittest.mock import patch

from fapilog.core.pressure import EscalationStateMachine, PressureLevel


class TestPressureLevel:
    def test_level_values(self) -> None:
        assert PressureLevel.NORMAL == "normal"
        assert PressureLevel.ELEVATED == "elevated"
        assert PressureLevel.HIGH == "high"
        assert PressureLevel.CRITICAL == "critical"

    def test_ordering_via_int_index(self) -> None:
        levels = list(PressureLevel)
        assert levels == [
            PressureLevel.NORMAL,
            PressureLevel.ELEVATED,
            PressureLevel.HIGH,
            PressureLevel.CRITICAL,
        ]


class TestEscalationStateMachine:
    def test_starts_at_normal(self) -> None:
        sm = EscalationStateMachine()
        assert sm.current_level == PressureLevel.NORMAL

    def test_escalates_to_elevated_at_threshold(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        result = sm.evaluate(0.65)
        assert result == PressureLevel.ELEVATED

    def test_no_escalation_below_threshold(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        result = sm.evaluate(0.55)
        assert result == PressureLevel.NORMAL

    def test_escalates_to_high_at_threshold(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        sm.evaluate(0.65)  # NORMAL -> ELEVATED
        result = sm.evaluate(0.85)
        assert result == PressureLevel.HIGH

    def test_escalates_to_critical_at_threshold(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        sm.evaluate(0.65)  # NORMAL -> ELEVATED
        sm.evaluate(0.85)  # ELEVATED -> HIGH
        result = sm.evaluate(0.95)
        assert result == PressureLevel.CRITICAL

    def test_deescalates_with_lower_thresholds(self) -> None:
        """Hysteresis: de-escalation thresholds are lower than escalation."""
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        sm.evaluate(0.65)  # -> ELEVATED
        sm.evaluate(0.85)  # -> HIGH
        sm.evaluate(0.95)  # -> CRITICAL

        # De-escalate: CRITICAL -> HIGH at < 75%
        result = sm.evaluate(0.70)
        assert result == PressureLevel.HIGH

        # De-escalate: HIGH -> ELEVATED at < 60%
        result = sm.evaluate(0.55)
        assert result == PressureLevel.ELEVATED

        # De-escalate: ELEVATED -> NORMAL at < 40%
        result = sm.evaluate(0.35)
        assert result == PressureLevel.NORMAL

    def test_no_oscillation_in_hysteresis_band(self) -> None:
        """Queue at 55% should stay ELEVATED (de-escalation needs < 40%)."""
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        sm.evaluate(0.65)  # -> ELEVATED
        # Still in hysteresis band (55% > 40% de-escalation threshold)
        result = sm.evaluate(0.55)
        assert result == PressureLevel.ELEVATED

    def test_cooldown_prevents_rapid_transitions(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=10.0)
        # First transition is always allowed (no prior transition)
        result = sm.evaluate(0.65)
        assert result == PressureLevel.ELEVATED

        # Second transition blocked by cooldown
        result = sm.evaluate(0.85)
        assert result == PressureLevel.ELEVATED  # Stuck due to cooldown

    def test_cooldown_allows_transition_after_expiry(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.5)
        sm.evaluate(0.65)  # -> ELEVATED

        # Mock time to advance past cooldown
        with patch("fapilog.core.pressure.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 1.0
            result = sm.evaluate(0.85)
            assert result == PressureLevel.HIGH

    def test_one_level_per_evaluation(self) -> None:
        """Even at 95% fill, should only go from NORMAL to ELEVATED (one step)."""
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        result = sm.evaluate(0.95)
        assert result == PressureLevel.ELEVATED  # Not CRITICAL

        result = sm.evaluate(0.95)
        assert result == PressureLevel.HIGH  # Next step

        result = sm.evaluate(0.95)
        assert result == PressureLevel.CRITICAL  # Final step

    def test_custom_thresholds(self) -> None:
        sm = EscalationStateMachine(
            cooldown_seconds=0.0,
            escalate_to_elevated=0.50,
            escalate_to_high=0.70,
            escalate_to_critical=0.85,
            deescalate_from_critical=0.65,
            deescalate_from_high=0.45,
            deescalate_from_elevated=0.30,
        )
        result = sm.evaluate(0.55)
        assert result == PressureLevel.ELEVATED

    def test_exact_escalation_threshold_triggers(self) -> None:
        """Fill ratio exactly at threshold should trigger escalation."""
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        result = sm.evaluate(0.60)
        assert result == PressureLevel.ELEVATED

    def test_exact_deescalation_threshold_does_not_trigger(self) -> None:
        """Fill ratio exactly at de-escalation threshold should NOT de-escalate.

        De-escalation requires fill < threshold (strictly less than).
        """
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        sm.evaluate(0.65)  # -> ELEVATED
        # Exactly at de-escalation threshold of 0.40
        result = sm.evaluate(0.40)
        assert result == PressureLevel.ELEVATED  # Still elevated

    def test_zero_fill_ratio(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        sm.evaluate(0.65)  # -> ELEVATED
        result = sm.evaluate(0.0)
        assert result == PressureLevel.NORMAL

    def test_full_escalation_ladder_up_and_down(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)

        # Up
        assert sm.evaluate(0.65) == PressureLevel.ELEVATED
        assert sm.evaluate(0.85) == PressureLevel.HIGH
        assert sm.evaluate(0.95) == PressureLevel.CRITICAL

        # Down
        assert sm.evaluate(0.70) == PressureLevel.HIGH
        assert sm.evaluate(0.55) == PressureLevel.ELEVATED
        assert sm.evaluate(0.35) == PressureLevel.NORMAL

    def test_no_change_returns_current_level(self) -> None:
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        result = sm.evaluate(0.50)
        assert result == PressureLevel.NORMAL  # No threshold crossed

    def test_evaluate_returns_new_level(self) -> None:
        """evaluate() returns the new level and updates current_level."""
        sm = EscalationStateMachine(cooldown_seconds=0.0)
        new = sm.evaluate(0.65)
        assert new == PressureLevel.ELEVATED
        assert sm.current_level == PressureLevel.ELEVATED
