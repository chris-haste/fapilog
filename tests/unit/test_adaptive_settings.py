"""Unit tests for AdaptiveSettings configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fapilog.core.settings import AdaptiveSettings, Settings


class TestAdaptiveSettings:
    def test_defaults(self) -> None:
        s = AdaptiveSettings()
        assert s.enabled is False
        assert s.check_interval_seconds == 0.25
        assert s.cooldown_seconds == 2.0
        assert s.escalate_to_elevated == 0.60
        assert s.escalate_to_high == 0.80
        assert s.escalate_to_critical == 0.92
        assert s.deescalate_from_critical == 0.75
        assert s.deescalate_from_high == 0.60
        assert s.deescalate_from_elevated == 0.40

    def test_custom_values(self) -> None:
        s = AdaptiveSettings(
            enabled=True,
            check_interval_seconds=0.5,
            cooldown_seconds=3.0,
            escalate_to_elevated=0.50,
            escalate_to_high=0.70,
            escalate_to_critical=0.85,
            deescalate_from_critical=0.65,
            deescalate_from_high=0.50,
            deescalate_from_elevated=0.30,
        )
        assert s.enabled is True
        assert s.check_interval_seconds == 0.5
        assert s.escalate_to_elevated == 0.50

    def test_validation_interval_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="check_interval_seconds"):
            AdaptiveSettings(check_interval_seconds=0.0)

    def test_validation_thresholds_bounded(self) -> None:
        with pytest.raises(ValidationError, match="escalate_to_elevated"):
            AdaptiveSettings(escalate_to_elevated=1.5)  # > 1.0

    def test_settings_has_adaptive_field(self) -> None:
        s = Settings()
        assert hasattr(s, "adaptive")
        assert isinstance(s.adaptive, AdaptiveSettings)
        assert s.adaptive.enabled is False

    def test_settings_adaptive_from_dict(self) -> None:
        s = Settings(adaptive={"enabled": True, "cooldown_seconds": 5.0})
        assert s.adaptive.enabled is True
        assert s.adaptive.cooldown_seconds == 5.0

    def test_max_workers_default(self) -> None:
        s = AdaptiveSettings()
        assert s.max_workers == 8

    def test_max_workers_custom(self) -> None:
        s = AdaptiveSettings(max_workers=16)
        assert s.max_workers == 16

    def test_max_workers_must_be_at_least_one(self) -> None:
        with pytest.raises(ValidationError, match="max_workers"):
            AdaptiveSettings(max_workers=0)

    def test_batch_sizing_default_false(self) -> None:
        s = AdaptiveSettings()
        assert s.batch_sizing is False

    def test_batch_sizing_enabled(self) -> None:
        s = AdaptiveSettings(batch_sizing=True)
        assert s.batch_sizing is True

    def test_settings_adaptive_batch_sizing_from_dict(self) -> None:
        s = Settings(adaptive={"batch_sizing": True})
        assert s.adaptive.batch_sizing is True
