"""Test preset definitions and validation."""

import pytest

from fapilog.core.presets import get_preset, list_presets, validate_preset
from fapilog.core.settings import Settings


class TestPresetDefinitions:
    """Test preset configuration dictionaries."""

    def test_dev_preset_has_debug_log_level(self):
        """Dev preset sets log level to DEBUG."""
        config = get_preset("dev")
        assert config["core"]["log_level"] == "DEBUG"

    def test_dev_preset_enables_internal_logging(self):
        """Dev preset enables internal diagnostics."""
        config = get_preset("dev")
        assert config["core"]["internal_logging_enabled"] is True

    def test_dev_preset_has_batch_size_one(self):
        """Dev preset uses batch size 1 for immediate flushing."""
        config = get_preset("dev")
        assert config["core"]["batch_max_size"] == 1

    def test_dev_preset_uses_stdout_pretty_sink(self):
        """Dev preset uses stdout_pretty sink."""
        config = get_preset("dev")
        assert config["core"]["sinks"] == ["stdout_pretty"]

    def test_production_preset_has_info_log_level(self):
        """Production preset sets log level to INFO."""
        config = get_preset("production")
        assert config["core"]["log_level"] == "INFO"

    def test_production_preset_configures_file_rotation(self):
        """Production preset configures 50MB file rotation."""
        config = get_preset("production")
        assert config["sink_config"]["rotating_file"]["max_bytes"] == 52_428_800
        assert config["sink_config"]["rotating_file"]["max_files"] == 10
        assert config["sink_config"]["rotating_file"]["compress_rotated"] is True

    def test_production_preset_enables_redaction(self):
        """Production preset enables field mask redactor."""
        config = get_preset("production")
        assert config["redactor_config"]["field_mask"]["fields_to_mask"] == [
            "metadata.password",
            "metadata.api_key",
            "metadata.token",
            "metadata.secret",
            "metadata.authorization",
            "metadata.api_secret",
            "metadata.private_key",
            "metadata.ssn",
            "metadata.credit_card",
        ]

    def test_production_preset_has_batch_size_100(self):
        """Production preset uses batch size 100 for throughput."""
        config = get_preset("production")
        assert config["core"]["batch_max_size"] == 100

    def test_production_preset_disables_drop_on_full(self):
        """Production preset does not drop logs under pressure."""
        config = get_preset("production")
        assert config["core"]["drop_on_full"] is False

    def test_production_preset_uses_stdout_and_file_sinks(self):
        """Production preset uses stdout_json and rotating_file sinks."""
        config = get_preset("production")
        assert config["core"]["sinks"] == ["stdout_json", "rotating_file"]

    def test_fastapi_preset_has_info_log_level(self):
        """FastAPI preset sets log level to INFO."""
        config = get_preset("fastapi")
        assert config["core"]["log_level"] == "INFO"

    def test_fastapi_preset_has_batch_size_50(self):
        """FastAPI preset uses batch size 50."""
        config = get_preset("fastapi")
        assert config["core"]["batch_max_size"] == 50

    def test_fastapi_preset_enables_context_vars(self):
        """FastAPI preset enables context_vars enricher."""
        config = get_preset("fastapi")
        assert "context_vars" in config["core"]["enrichers"]

    def test_fastapi_preset_enables_redactors(self):
        """FastAPI preset enables redactors for security by default.

        Story 10.21 AC1: FastAPI preset enables same redactors as production.
        """
        config = get_preset("fastapi")
        assert config["core"]["redactors"] == [
            "field_mask",
            "regex_mask",
            "url_credentials",
        ]

    def test_fastapi_preset_has_redactor_config(self):
        """FastAPI preset has redactor_config section.

        Story 10.21 AC1: Redactor config must be present.
        """
        config = get_preset("fastapi")
        assert "redactor_config" in config
        assert "field_mask" in config["redactor_config"]
        assert "regex_mask" in config["redactor_config"]
        assert "url_credentials" in config["redactor_config"]

    def test_fastapi_preset_redactor_config_matches_production(self):
        """FastAPI preset redactor_config matches production preset.

        Story 10.21 AC1: FastAPI redactor config should match production.
        """
        fastapi_config = get_preset("fastapi")
        production_config = get_preset("production")
        assert fastapi_config["redactor_config"] == production_config["redactor_config"]

    def test_minimal_preset_opts_out_of_redaction(self):
        """Minimal preset explicitly opts out of redaction for minimal overhead.

        Story 3.7: Presets must explicitly set redactors=[] to opt-out.
        """
        config = get_preset("minimal")
        assert config == {"core": {"redactors": []}}


class TestPresetValidation:
    """Test preset name validation."""

    @pytest.mark.parametrize("name", ["dev", "production", "fastapi", "minimal"])
    def test_valid_presets_accepted(self, name: str):
        """All valid preset names are accepted without raising."""
        validate_preset(name)

    def test_invalid_preset_raises_value_error(self):
        """Invalid preset name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid preset 'foobar'"):
            validate_preset("foobar")

    def test_case_sensitive_rejects_uppercase(self):
        """Preset names are case-sensitive - Dev is rejected."""
        with pytest.raises(ValueError):
            validate_preset("Dev")

    def test_case_sensitive_rejects_all_caps(self):
        """Preset names are case-sensitive - PRODUCTION is rejected."""
        with pytest.raises(ValueError):
            validate_preset("PRODUCTION")

    def test_error_message_lists_valid_presets(self):
        """Error message includes list of valid presets."""
        with pytest.raises(
            ValueError, match="Valid presets: dev, fastapi, minimal, production"
        ):
            validate_preset("invalid")


class TestPresetToSettings:
    """Test converting presets to Settings objects."""

    def test_dev_preset_creates_valid_settings(self):
        """Dev preset can be converted to Settings."""
        config = get_preset("dev")
        settings = Settings(**config)
        assert settings.core.log_level == "DEBUG"
        assert settings.core.internal_logging_enabled is True

    def test_production_preset_creates_valid_settings(self):
        """Production preset can be converted to Settings."""
        config = get_preset("production")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"
        assert settings.sink_config.rotating_file.compress_rotated is True

    def test_fastapi_preset_creates_valid_settings(self):
        """FastAPI preset can be converted to Settings."""
        config = get_preset("fastapi")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"
        assert settings.core.batch_max_size == 50

    def test_minimal_preset_creates_valid_settings(self):
        """Minimal preset produces valid Settings with defaults."""
        config = get_preset("minimal")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"  # Default

    @pytest.mark.parametrize("name", ["dev", "production", "fastapi", "minimal"])
    def test_all_presets_create_valid_settings(self, name: str):
        """All presets produce valid Settings objects with core config."""
        config = get_preset(name)
        settings = Settings(**config)
        assert hasattr(settings, "core")


class TestPresetList:
    """Test preset listing."""

    def test_list_presets_returns_all_four(self):
        """list_presets returns all four preset names."""
        presets = list_presets()
        assert set(presets) == {"dev", "production", "fastapi", "minimal"}

    def test_list_presets_is_sorted(self):
        """list_presets returns sorted list."""
        presets = list_presets()
        assert presets == sorted(presets)

    def test_list_presets_returns_list(self):
        """list_presets returns a list, not a view."""
        presets = list_presets()
        assert isinstance(presets, list)


class TestPresetImmutability:
    """Test that get_preset returns copies, not references."""

    def test_get_preset_returns_copy(self):
        """get_preset returns a copy, not the original dict."""
        config1 = get_preset("dev")
        config2 = get_preset("dev")
        config1["core"]["log_level"] = "ERROR"
        assert config2["core"]["log_level"] == "DEBUG"
