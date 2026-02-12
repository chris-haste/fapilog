"""Tests for adaptive preset definition (Story 10.57 AC1, AC5, AC7)."""

from fapilog.core.presets import get_preset, list_presets, validate_preset
from fapilog.core.settings import Settings


class TestAdaptivePresetExists:
    """AC7: Adaptive preset is discoverable."""

    def test_adaptive_preset_exists(self) -> None:
        """get_preset('adaptive') returns a config dict."""
        config = get_preset("adaptive")
        assert "core" in config

    def test_adaptive_preset_in_list_presets(self) -> None:
        """list_presets() includes 'adaptive'."""
        presets = list_presets()
        assert "adaptive" in presets

    def test_adaptive_preset_validates(self) -> None:
        """validate_preset('adaptive') does not raise."""
        validate_preset("adaptive")


class TestAdaptivePresetContent:
    """AC1: Adaptive preset enables all adaptive features."""

    def test_adaptive_preset_has_info_log_level(self) -> None:
        """Adaptive preset sets log level to INFO."""
        config = get_preset("adaptive")
        assert config["core"]["log_level"] == "INFO"

    def test_adaptive_preset_has_two_workers(self) -> None:
        """Adaptive preset sets worker_count to 2."""
        config = get_preset("adaptive")
        assert config["core"]["worker_count"] == 2

    def test_adaptive_preset_enables_adaptive(self) -> None:
        """Adaptive preset enables adaptive.enabled."""
        config = get_preset("adaptive")
        assert config["adaptive"]["enabled"] is True

    def test_adaptive_preset_disables_batch_sizing_by_default(self) -> None:
        """Adaptive preset disables batch_sizing (only useful for batch-aware sinks)."""
        config = get_preset("adaptive")
        assert config["adaptive"]["batch_sizing"] is False

    def test_adaptive_preset_sets_max_workers(self) -> None:
        """Adaptive preset sets max_workers to 8."""
        config = get_preset("adaptive")
        assert config["adaptive"]["max_workers"] == 8

    def test_adaptive_preset_sets_max_queue_growth(self) -> None:
        """Adaptive preset sets max_queue_growth to 4.0."""
        config = get_preset("adaptive")
        assert config["adaptive"]["max_queue_growth"] == 4.0

    def test_adaptive_preset_sets_circuit_pressure_boost(self) -> None:
        """Adaptive preset sets circuit_pressure_boost to 0.20."""
        config = get_preset("adaptive")
        assert config["adaptive"]["circuit_pressure_boost"] == 0.20

    def test_adaptive_preset_enables_drop_on_full(self) -> None:
        """Adaptive preset enables drop_on_full for latency."""
        config = get_preset("adaptive")
        assert config["core"]["drop_on_full"] is True


class TestAdaptivePresetCircuitBreaker:
    """AC1: Adaptive preset includes circuit breaker."""

    def test_adaptive_preset_enables_circuit_breaker(self) -> None:
        """Adaptive preset enables circuit breaker."""
        config = get_preset("adaptive")
        assert config["core"]["sink_circuit_breaker_enabled"] is True

    def test_adaptive_preset_circuit_breaker_fallback_to_file(self) -> None:
        """Adaptive preset routes circuit breaker fallback to rotating_file."""
        config = get_preset("adaptive")
        assert config["core"]["sink_circuit_breaker_fallback_sink"] == "rotating_file"


class TestAdaptivePresetSinks:
    """AC5: Rotating file sink included for fallback."""

    def test_adaptive_preset_includes_rotating_file_sink(self) -> None:
        """Adaptive preset includes rotating_file in sinks list."""
        config = get_preset("adaptive")
        assert "rotating_file" in config["core"]["sinks"]

    def test_adaptive_preset_includes_stdout_json_sink(self) -> None:
        """Adaptive preset includes stdout_json in sinks list."""
        config = get_preset("adaptive")
        assert "stdout_json" in config["core"]["sinks"]

    def test_adaptive_preset_has_file_rotation_config(self) -> None:
        """Adaptive preset configures rotating file sink like production."""
        config = get_preset("adaptive")
        rf = config["sink_config"]["rotating_file"]
        assert rf["directory"] == "./logs"
        assert rf["max_bytes"] == 52_428_800
        assert rf["max_files"] == 10
        assert rf["compress_rotated"] is True


class TestAdaptivePresetRedaction:
    """Adaptive preset has production-grade redaction."""

    def test_adaptive_preset_has_redactors(self) -> None:
        """Adaptive preset enables field_mask, regex_mask, url_credentials."""
        config = get_preset("adaptive")
        assert config["core"]["redactors"] == [
            "field_mask",
            "regex_mask",
            "url_credentials",
        ]

    def test_adaptive_preset_applies_credentials_preset(self) -> None:
        """Adaptive preset has marker for CREDENTIALS preset."""
        config = get_preset("adaptive")
        assert config.get("_apply_credentials_preset") is True


class TestAdaptivePresetProtectedLevels:
    """AC1: Protected levels configured."""

    def test_adaptive_preset_has_protected_levels(self) -> None:
        """Adaptive preset protects ERROR, CRITICAL, FATAL, AUDIT, SECURITY."""
        config = get_preset("adaptive")
        expected = ["ERROR", "CRITICAL", "FATAL", "AUDIT", "SECURITY"]
        assert config["core"]["protected_levels"] == expected


class TestAdaptivePresetToSettings:
    """Adaptive preset creates valid Settings."""

    def test_adaptive_preset_creates_valid_settings(self) -> None:
        """Adaptive preset can be converted to Settings."""
        config = get_preset("adaptive")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"
        assert settings.adaptive.enabled is True
        assert settings.adaptive.batch_sizing is False
        assert settings.adaptive.max_workers == 8

    def test_adaptive_preset_returns_deep_copy(self) -> None:
        """get_preset returns a copy, not the original dict."""
        config1 = get_preset("adaptive")
        config2 = get_preset("adaptive")
        config1["adaptive"]["max_workers"] = 99
        assert config2["adaptive"]["max_workers"] == 8


class TestPresetNameLiteralIncludesAdaptive:
    """PresetName Literal type includes 'adaptive'."""

    def test_preset_name_literal_matches_registry(self) -> None:
        """PresetName Literal values match PRESETS dict keys."""
        from typing import get_args

        from fapilog.core.presets import PRESETS, PresetName

        assert set(get_args(PresetName)) == set(PRESETS.keys())
