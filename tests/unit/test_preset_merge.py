"""Tests for production/adaptive preset merge (Story 1.53).

AC4: Production preset includes adaptive features
AC5: adaptive preset name is deprecated alias
"""

from __future__ import annotations

import warnings

from fapilog.core.presets import get_preset


class TestProductionPresetAdaptiveFeatures:
    """AC4: Production preset includes adaptive features."""

    def test_production_preset_has_large_queue(self) -> None:
        """Production preset sets max_queue_size=10000."""
        config = get_preset("production")
        assert config["core"]["max_queue_size"] == 10000

    def test_production_preset_has_protected_levels(self) -> None:
        """Production preset protects ERROR and CRITICAL."""
        config = get_preset("production")
        assert config["core"]["protected_levels"] == ["ERROR", "CRITICAL"]

    def test_production_preset_has_drop_on_full_false(self) -> None:
        """Production preset disables drop_on_full for backpressure."""
        config = get_preset("production")
        assert config["core"]["drop_on_full"] is False

    def test_production_preset_has_circuit_breaker(self) -> None:
        """Production preset enables circuit breaker."""
        config = get_preset("production")
        assert config["core"]["sink_circuit_breaker_enabled"] is True

    def test_production_preset_has_circuit_breaker_fallback(self) -> None:
        """Production preset routes circuit breaker fallback to rotating_file."""
        config = get_preset("production")
        assert config["core"]["sink_circuit_breaker_fallback_sink"] == "rotating_file"

    def test_production_preset_has_adaptive_enabled(self) -> None:
        """Production preset enables adaptive pipeline."""
        config = get_preset("production")
        assert config["adaptive"]["enabled"] is True

    def test_production_preset_adaptive_max_workers(self) -> None:
        """Production preset sets max_workers=4."""
        config = get_preset("production")
        assert config["adaptive"]["max_workers"] == 4

    def test_production_preset_adaptive_max_queue_growth(self) -> None:
        """Production preset sets max_queue_growth=3.0."""
        config = get_preset("production")
        assert config["adaptive"]["max_queue_growth"] == 3.0

    def test_production_preset_stdout_only_primary_sink(self) -> None:
        """Production preset uses only stdout_json as primary sink (PR #580)."""
        config = get_preset("production")
        assert config["core"]["sinks"] == ["stdout_json"]

    def test_production_preset_has_sink_concurrency(self) -> None:
        """Production preset sets sink_concurrency=8."""
        config = get_preset("production")
        assert config["core"]["sink_concurrency"] == 8

    def test_production_preset_has_batch_timeout(self) -> None:
        """Production preset sets batch_timeout_seconds=0.25."""
        config = get_preset("production")
        assert config["core"]["batch_timeout_seconds"] == 0.25


class TestAdaptiveDeprecationAlias:
    """AC5: adaptive preset name is deprecated alias."""

    def test_adaptive_alias_emits_deprecation_warning(self) -> None:
        """get_preset('adaptive') emits DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            get_preset("adaptive")
            dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) == 1
            msg = str(dep_warnings[0].message).lower()
            assert "deprecated" in msg
            assert "production" in msg

    def test_adaptive_alias_returns_production_config(self) -> None:
        """get_preset('adaptive') returns same config as production."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            adaptive_config = get_preset("adaptive")

        production_config = get_preset("production")
        assert adaptive_config == production_config

    def test_validate_preset_accepts_adaptive(self) -> None:
        """validate_preset('adaptive') does not raise."""
        from fapilog.core.presets import validate_preset

        validate_preset("adaptive")
