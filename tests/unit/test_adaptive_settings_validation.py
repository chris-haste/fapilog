"""Tests for AdaptiveSettings threshold validation (Story 10.57 AC6)."""

import pytest
from pydantic import ValidationError

from fapilog.core.settings import AdaptiveSettings


class TestDefaultThresholds:
    """Default thresholds must be valid."""

    def test_default_thresholds_are_valid(self) -> None:
        """Default AdaptiveSettings creates without error."""
        settings = AdaptiveSettings()
        assert settings.escalate_to_elevated == 0.60
        assert settings.escalate_to_high == 0.80
        assert settings.escalate_to_critical == 0.92

    def test_default_deescalation_below_escalation(self) -> None:
        """Default de-escalation thresholds are below corresponding escalation."""
        settings = AdaptiveSettings()
        assert settings.deescalate_from_elevated < settings.escalate_to_elevated
        assert settings.deescalate_from_high < settings.escalate_to_high
        assert settings.deescalate_from_critical < settings.escalate_to_critical


class TestEscalationAscending:
    """Escalation thresholds must be ascending: elevated < high < critical."""

    def test_valid_ascending_escalation(self) -> None:
        """Custom ascending thresholds are accepted."""
        settings = AdaptiveSettings(
            escalate_to_elevated=0.50,
            escalate_to_high=0.70,
            escalate_to_critical=0.90,
            deescalate_from_elevated=0.30,
            deescalate_from_high=0.50,
            deescalate_from_critical=0.60,
        )
        assert settings.escalate_to_elevated == 0.50

    def test_elevated_not_less_than_high_raises(self) -> None:
        """Escalation elevated >= high raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="escalate_to_elevated.*must be less than.*escalate_to_high",
        ):
            AdaptiveSettings(
                escalate_to_elevated=0.85,
                escalate_to_high=0.80,
                escalate_to_critical=0.92,
            )

    def test_high_not_less_than_critical_raises(self) -> None:
        """Escalation high >= critical raises ValidationError."""
        with pytest.raises(
            ValidationError,
            match="escalate_to_high.*must be less than.*escalate_to_critical",
        ):
            AdaptiveSettings(
                escalate_to_elevated=0.50,
                escalate_to_high=0.95,
                escalate_to_critical=0.90,
            )

    def test_equal_escalation_thresholds_raises(self) -> None:
        """Equal escalation thresholds raise ValidationError."""
        with pytest.raises(ValidationError, match="must be less than"):
            AdaptiveSettings(
                escalate_to_elevated=0.80,
                escalate_to_high=0.80,
                escalate_to_critical=0.92,
            )


class TestDeescalationBelowEscalation:
    """De-escalation thresholds must be below corresponding escalation."""

    def test_deescalate_elevated_above_escalate_raises(self) -> None:
        """De-escalate from elevated >= escalate to elevated raises."""
        with pytest.raises(
            ValidationError,
            match="deescalate_from_elevated.*must be less than.*escalate_to_elevated",
        ):
            AdaptiveSettings(
                escalate_to_elevated=0.60,
                deescalate_from_elevated=0.65,
            )

    def test_deescalate_high_above_escalate_raises(self) -> None:
        """De-escalate from high >= escalate to high raises."""
        with pytest.raises(
            ValidationError,
            match="deescalate_from_high.*must be less than.*escalate_to_high",
        ):
            AdaptiveSettings(
                escalate_to_high=0.80,
                deescalate_from_high=0.85,
            )

    def test_deescalate_critical_above_escalate_raises(self) -> None:
        """De-escalate from critical >= escalate to critical raises."""
        with pytest.raises(
            ValidationError,
            match="deescalate_from_critical.*must be less than.*escalate_to_critical",
        ):
            AdaptiveSettings(
                escalate_to_critical=0.92,
                deescalate_from_critical=0.95,
            )

    def test_equal_deescalation_and_escalation_raises(self) -> None:
        """Equal de-escalation and escalation thresholds raise."""
        with pytest.raises(ValidationError, match="must be less than"):
            AdaptiveSettings(
                escalate_to_elevated=0.60,
                deescalate_from_elevated=0.60,
            )


class TestEnvVarOverride:
    """AC4: Environment variable configuration."""

    def test_env_var_sets_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FAPILOG_ADAPTIVE__ENABLED env var enables adaptive mode."""
        monkeypatch.setenv("FAPILOG_ADAPTIVE__ENABLED", "true")
        from fapilog.core.settings import Settings

        settings = Settings()
        assert settings.adaptive.enabled is True

    def test_env_var_sets_max_workers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FAPILOG_ADAPTIVE__MAX_WORKERS env var overrides max workers."""
        monkeypatch.setenv("FAPILOG_ADAPTIVE__MAX_WORKERS", "6")
        from fapilog.core.settings import Settings

        settings = Settings()
        assert settings.adaptive.max_workers == 6

    def test_env_var_sets_cooldown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FAPILOG_ADAPTIVE__COOLDOWN_SECONDS env var overrides cooldown."""
        monkeypatch.setenv("FAPILOG_ADAPTIVE__COOLDOWN_SECONDS", "3.0")
        from fapilog.core.settings import Settings

        settings = Settings()
        assert settings.adaptive.cooldown_seconds == 3.0
