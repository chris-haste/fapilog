"""Unit tests for AdaptiveSettings.max_queue_growth — Story 1.48."""

from __future__ import annotations

from fapilog.core.settings import AdaptiveSettings


class TestAdaptiveSettingsQueueGrowth:
    def test_default_max_queue_growth(self) -> None:
        settings = AdaptiveSettings()
        assert settings.max_queue_growth == 4.0

    def test_custom_max_queue_growth(self) -> None:
        settings = AdaptiveSettings(max_queue_growth=2.0)
        assert settings.max_queue_growth == 2.0

    def test_max_queue_growth_minimum_is_one(self) -> None:
        """Growth multiplier below 1.0 is invalid — no shrinking."""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            AdaptiveSettings(max_queue_growth=0.5)
