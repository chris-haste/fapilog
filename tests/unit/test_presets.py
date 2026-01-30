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
        """Production preset has redactor config structure (fields applied by builder)."""
        config = get_preset("production")
        # Production preset has redactor config, but actual fields come from
        # CREDENTIALS preset via with_preset("production") -> with_redaction(preset="CREDENTIALS")
        assert "field_mask" in config["redactor_config"]
        assert "regex_mask" in config["redactor_config"]
        assert "url_credentials" in config["redactor_config"]
        # Marker for automatic CREDENTIALS preset application
        assert config.get("_apply_credentials_preset") is True

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

    def test_production_preset_disables_postgres_create_table(self):
        """Production preset disables Postgres auto table creation.

        Story 10.32 AC2: In regulated environments, DDL execution at runtime
        may violate change management policies. Production preset sets
        create_table=False to require explicit table provisioning.
        """
        config = get_preset("production")
        postgres_config = config.get("sink_config", {}).get("postgres", {})
        assert postgres_config.get("create_table") is False

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

    # Story 10.30: Serverless Preset Tests

    def test_serverless_preset_exists(self):
        """Serverless preset is available via get_preset.

        Story 10.30 AC1: Preset available via get_logger(preset="serverless").
        """
        config = get_preset("serverless")
        assert "core" in config

    def test_serverless_preset_has_info_log_level(self):
        """Serverless preset sets log level to INFO."""
        config = get_preset("serverless")
        assert config["core"]["log_level"] == "INFO"

    def test_serverless_preset_uses_stdout_only(self):
        """Serverless preset uses only stdout_json, no file sinks.

        Story 10.30 AC2: Only stdout_json sink, no rotating_file.
        """
        config = get_preset("serverless")
        assert config["core"]["sinks"] == ["stdout_json"]
        assert "rotating_file" not in config["core"]["sinks"]

    def test_serverless_preset_enables_redactors(self):
        """Serverless preset enables same redactors as production.

        Story 10.30 AC3: Production-grade redaction enabled.
        """
        config = get_preset("serverless")
        assert config["core"]["redactors"] == [
            "field_mask",
            "regex_mask",
            "url_credentials",
        ]

    def test_serverless_preset_redactor_config_matches_production(self):
        """Serverless preset redactor_config matches production preset.

        Story 10.30 AC3: Same redactor configuration as production.
        """
        serverless_config = get_preset("serverless")
        production_config = get_preset("production")
        assert (
            serverless_config["redactor_config"] == production_config["redactor_config"]
        )

    def test_serverless_preset_has_small_batch_size(self):
        """Serverless preset uses smaller batch size for short-lived functions.

        Story 10.30 AC4: Batch size <= 25 for quick flushing.
        """
        config = get_preset("serverless")
        assert config["core"]["batch_max_size"] <= 25

    def test_serverless_preset_enables_drop_on_full(self):
        """Serverless preset enables drop_on_full to avoid blocking.

        Story 10.30: Don't block in time-constrained environments.
        """
        config = get_preset("serverless")
        assert config["core"]["drop_on_full"] is True

    def test_serverless_preset_has_enrichers(self):
        """Serverless preset enables runtime_info and context_vars enrichers."""
        config = get_preset("serverless")
        assert "runtime_info" in config["core"]["enrichers"]
        assert "context_vars" in config["core"]["enrichers"]

    # Story 3.10: Hardened Preset Tests

    def test_hardened_preset_exists(self):
        """Hardened preset is available via get_preset.

        Story 3.10 AC1: Preset available via get_logger(preset="hardened").
        """
        config = get_preset("hardened")
        assert "core" in config

    def test_hardened_preset_has_info_log_level(self):
        """Hardened preset sets log level to INFO."""
        config = get_preset("hardened")
        assert config["core"]["log_level"] == "INFO"

    def test_hardened_preset_fail_closed_redaction(self):
        """Hardened preset uses fail-closed redaction mode.

        Story 3.10 AC2: Drop events if redaction fails.
        """
        config = get_preset("hardened")
        assert config["core"]["redaction_fail_mode"] == "closed"

    def test_hardened_preset_strict_envelope_mode(self):
        """Hardened preset enables strict envelope mode.

        Story 3.10 AC3: Reject malformed envelopes.
        """
        config = get_preset("hardened")
        assert config["core"]["strict_envelope_mode"] is True

    def test_hardened_preset_fallback_inherit(self):
        """Hardened preset uses inherit mode for fallback redaction.

        Story 3.10 AC4: Full redaction on fallback sink output.
        """
        config = get_preset("hardened")
        assert config["core"]["fallback_redact_mode"] == "inherit"

    def test_hardened_preset_no_drop_on_full(self):
        """Hardened preset does not drop logs under pressure.

        Story 3.10 AC5: Never lose logs due to queue pressure.
        """
        config = get_preset("hardened")
        assert config["core"]["drop_on_full"] is False

    def test_hardened_preset_enables_fallback_scrub_raw(self):
        """Hardened preset scrubs raw fallback output."""
        config = get_preset("hardened")
        assert config["core"]["fallback_scrub_raw"] is True

    def test_hardened_preset_uses_stdout_and_file_sinks(self):
        """Hardened preset uses stdout_json and rotating_file sinks."""
        config = get_preset("hardened")
        assert config["core"]["sinks"] == ["stdout_json", "rotating_file"]

    def test_hardened_preset_has_redaction_presets_marker(self):
        """Hardened preset has marker for multiple redaction presets.

        Story 3.10 AC6: Apply HIPAA, PCI-DSS, and CREDENTIALS presets.
        """
        config = get_preset("hardened")
        # Legacy marker for CREDENTIALS
        assert config.get("_apply_credentials_preset") is True
        # New marker for additional presets
        assert "_apply_redaction_presets" in config
        assert "HIPAA_PHI" in config["_apply_redaction_presets"]
        assert "PCI_DSS" in config["_apply_redaction_presets"]

    def test_hardened_preset_configures_file_rotation(self):
        """Hardened preset configures file rotation like production."""
        config = get_preset("hardened")
        assert config["sink_config"]["rotating_file"]["max_bytes"] == 52_428_800
        assert config["sink_config"]["rotating_file"]["max_files"] == 10
        assert config["sink_config"]["rotating_file"]["compress_rotated"] is True

    def test_hardened_preset_disables_postgres_create_table(self):
        """Hardened preset disables Postgres auto table creation."""
        config = get_preset("hardened")
        postgres_config = config.get("sink_config", {}).get("postgres", {})
        assert postgres_config.get("create_table") is False

    def test_hardened_preset_creates_valid_settings(self):
        """Hardened preset can be converted to Settings."""
        config = get_preset("hardened")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"
        assert settings.core.redaction_fail_mode == "closed"
        assert settings.core.strict_envelope_mode is True
        assert settings.core.fallback_redact_mode == "inherit"
        assert settings.core.drop_on_full is False


class TestPresetValidation:
    """Test preset name validation."""

    @pytest.mark.parametrize(
        "name",
        [
            "dev",
            "production",
            "production-latency",
            "fastapi",
            "minimal",
            "serverless",
            "hardened",
        ],
    )
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
            ValueError,
            match="Valid presets: dev, fastapi, hardened, minimal, production, production-latency, serverless",
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

    def test_serverless_preset_creates_valid_settings(self):
        """Serverless preset can be converted to Settings."""
        config = get_preset("serverless")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"
        assert settings.core.drop_on_full is True

    @pytest.mark.parametrize(
        "name",
        [
            "dev",
            "production",
            "production-latency",
            "fastapi",
            "minimal",
            "serverless",
            "hardened",
        ],
    )
    def test_all_presets_create_valid_settings(self, name: str):
        """All presets produce valid Settings objects with core config."""
        config = get_preset(name)
        settings = Settings(**config)
        assert hasattr(settings, "core")


class TestPresetList:
    """Test preset listing."""

    def test_list_presets_returns_all_seven(self):
        """list_presets returns all seven preset names."""
        presets = list_presets()
        assert set(presets) == {
            "dev",
            "production",
            "production-latency",
            "fastapi",
            "minimal",
            "serverless",
            "hardened",
        }

    def test_list_presets_is_sorted(self):
        """list_presets returns sorted list."""
        presets = list_presets()
        assert presets == sorted(presets)

    def test_list_presets_returns_list(self):
        """list_presets returns a list, not a view."""
        presets = list_presets()
        assert isinstance(presets, list)


class TestPresetWorkerCount:
    """Test worker_count settings per Story 10.44.

    Performance testing showed worker_count=2 provides ~30x throughput
    improvement over the default of 1. Production-oriented presets should
    default to 2 workers for optimal out-of-box performance.
    """

    def test_production_preset_has_two_workers(self):
        """Production preset sets worker_count to 2 for optimal throughput.

        Story 10.44 AC1: production preset sets worker_count: 2.
        """
        config = get_preset("production")
        assert config["core"]["worker_count"] == 2

    def test_fastapi_preset_has_two_workers(self):
        """FastAPI preset sets worker_count to 2 for optimal throughput.

        Story 10.44 AC1: fastapi preset sets worker_count: 2.
        """
        config = get_preset("fastapi")
        assert config["core"]["worker_count"] == 2

    def test_serverless_preset_has_two_workers(self):
        """Serverless preset sets worker_count to 2 for optimal throughput.

        Story 10.44 AC1: serverless preset sets worker_count: 2.
        """
        config = get_preset("serverless")
        assert config["core"]["worker_count"] == 2

    def test_hardened_preset_has_two_workers(self):
        """Hardened preset sets worker_count to 2 for optimal throughput.

        Story 10.44 AC1: hardened preset sets worker_count: 2.
        """
        config = get_preset("hardened")
        assert config["core"]["worker_count"] == 2

    def test_production_latency_preset_has_two_workers(self):
        """Production-latency preset sets worker_count to 2 for throughput.

        Story 10.45 AC2: worker_count == 2 for multi-worker throughput.
        """
        config = get_preset("production-latency")
        assert config["core"]["worker_count"] == 2

    def test_dev_preset_has_one_worker(self):
        """Dev preset uses 1 worker for simpler debugging.

        Story 10.44 AC1: dev preset remains at default (1 worker).
        """
        config = get_preset("dev")
        assert config["core"].get("worker_count", 1) == 1

    def test_minimal_preset_uses_default_worker_count(self):
        """Minimal preset uses default worker_count (1).

        Story 10.44 AC1: minimal preset remains at default (1 worker).
        """
        config = get_preset("minimal")
        # Minimal preset only sets redactors=[], so worker_count is not present
        assert "worker_count" not in config.get("core", {})


class TestProductionLatencyPreset:
    """Test production-latency preset for low-latency production deployments.

    Story 10.45 AC2: A new `production-latency` preset is available that
    prioritizes throughput over durability.
    """

    def test_production_latency_preset_exists(self):
        """Production-latency preset is available via get_preset."""
        config = get_preset("production-latency")
        assert "core" in config

    def test_production_latency_preset_in_list_presets(self):
        """Production-latency preset appears in list_presets()."""
        presets = list_presets()
        assert "production-latency" in presets

    def test_production_latency_preset_has_info_log_level(self):
        """Production-latency preset sets log level to INFO."""
        config = get_preset("production-latency")
        assert config["core"]["log_level"] == "INFO"

    def test_production_latency_preset_enables_drop_on_full(self):
        """Production-latency preset enables drop_on_full for latency.

        Story 10.45 AC2: Key setting - accept drops for latency.
        """
        config = get_preset("production-latency")
        assert config["core"]["drop_on_full"] is True

    def test_production_latency_preset_has_two_workers(self):
        """Production-latency preset uses 2 workers for throughput."""
        config = get_preset("production-latency")
        assert config["core"]["worker_count"] == 2

    def test_production_latency_preset_has_batch_size_100(self):
        """Production-latency preset uses batch size >= 50."""
        config = get_preset("production-latency")
        assert config["core"]["batch_max_size"] >= 50

    def test_production_latency_preset_uses_stdout_only(self):
        """Production-latency preset uses stdout_json only, no file sink.

        No file sink for minimal I/O latency.
        """
        config = get_preset("production-latency")
        assert config["core"]["sinks"] == ["stdout_json"]

    def test_production_latency_preset_has_redactors(self):
        """Production-latency preset has production-grade redaction."""
        config = get_preset("production-latency")
        assert "field_mask" in config["core"]["redactors"]
        assert "regex_mask" in config["core"]["redactors"]
        assert "url_credentials" in config["core"]["redactors"]

    def test_production_latency_preset_applies_credentials_preset(self):
        """Production-latency preset applies CREDENTIALS preset."""
        config = get_preset("production-latency")
        assert config.get("_apply_credentials_preset") is True

    def test_production_latency_preset_has_enrichers(self):
        """Production-latency preset enables runtime_info and context_vars."""
        config = get_preset("production-latency")
        assert "runtime_info" in config["core"]["enrichers"]
        assert "context_vars" in config["core"]["enrichers"]

    def test_production_latency_preset_creates_valid_settings(self):
        """Production-latency preset can be converted to Settings."""
        config = get_preset("production-latency")
        settings = Settings(**config)
        assert settings.core.log_level == "INFO"
        assert settings.core.drop_on_full is True
        assert settings.core.worker_count == 2

    def test_production_latency_vs_production_difference(self):
        """Production-latency differs from production in key ways.

        Verify the distinguishing characteristics:
        - production: drop_on_full=False, has file sink
        - production-latency: drop_on_full=True, no file sink
        """
        prod = get_preset("production")
        prod_latency = get_preset("production-latency")

        # The key behavioral difference
        assert prod["core"]["drop_on_full"] is False
        assert prod_latency["core"]["drop_on_full"] is True

        # File sink difference
        assert "rotating_file" in prod["core"]["sinks"]
        assert "rotating_file" not in prod_latency["core"]["sinks"]


class TestPresetImmutability:
    """Test that get_preset returns copies, not references."""

    def test_get_preset_returns_copy(self):
        """get_preset returns a copy, not the original dict."""
        config1 = get_preset("dev")
        config2 = get_preset("dev")
        config1["core"]["log_level"] = "ERROR"
        assert config2["core"]["log_level"] == "DEBUG"


class TestPresetWithBuilderSinks:
    """Test that builder add_*() methods merge with preset sinks.

    Regression test for bug where add_file() with preset caused
    messages to be submitted but not processed (processed=0).
    """

    def test_production_preset_with_add_file_merges_sinks(self):
        """add_file() with production preset merges sinks, not replaces.

        Bug: preset sinks were completely replaced instead of merged,
        losing stdout_json when add_file() was called.
        """
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder().with_preset("production").add_file("/tmp/logs")

        # Access internal config to verify merge happened
        # Build creates the merged config internally, so we simulate
        import copy

        from fapilog.core.presets import get_preset

        config = copy.deepcopy(get_preset("production"))
        builder._deep_merge(config, builder._config)

        # Apply sink merging logic (what build() does)
        sink_names = [s["name"] for s in builder._sinks]
        existing_sinks = config.get("core", {}).get("sinks", [])
        merged_sinks = list(dict.fromkeys(existing_sinks + sink_names))

        # Should have both preset sinks preserved
        assert "stdout_json" in merged_sinks
        assert "rotating_file" in merged_sinks

    def test_dev_preset_with_add_file_merges_sinks(self):
        """add_file() with dev preset preserves stdout_pretty sink."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder().with_preset("dev").add_file("/tmp/logs")

        import copy

        from fapilog.core.presets import get_preset

        config = copy.deepcopy(get_preset("dev"))
        builder._deep_merge(config, builder._config)

        sink_names = [s["name"] for s in builder._sinks]
        existing_sinks = config.get("core", {}).get("sinks", [])
        merged_sinks = list(dict.fromkeys(existing_sinks + sink_names))

        # Should have both dev preset's stdout_pretty and new rotating_file
        assert "stdout_pretty" in merged_sinks
        assert "rotating_file" in merged_sinks

    def test_preset_sink_config_merged_not_replaced(self):
        """add_file() merges sink config with preset defaults.

        Bug: preset sink_config was completely replaced, losing
        filename_prefix and other defaults.
        """
        from fapilog.builder import LoggerBuilder

        builder = (
            LoggerBuilder()
            .with_preset("production")
            .add_file(
                "/custom/path",
                max_bytes="20 MB",
            )
        )

        import copy

        from fapilog.core.presets import get_preset

        config = copy.deepcopy(get_preset("production"))
        builder._deep_merge(config, builder._config)

        # Simulate sink config merging
        sink_config = config.setdefault("sink_config", {})
        for sink in builder._sinks:
            if "config" in sink:
                if sink["name"] in sink_config:
                    builder._deep_merge(sink_config[sink["name"]], sink["config"])
                else:
                    sink_config[sink["name"]] = sink["config"]

        # User's values should override
        assert sink_config["rotating_file"]["directory"] == "/custom/path"
        assert sink_config["rotating_file"]["max_bytes"] == "20 MB"
        # Preset defaults should be preserved
        assert sink_config["rotating_file"]["filename_prefix"] == "fapilog"
        assert sink_config["rotating_file"]["max_files"] == 10
        assert sink_config["rotating_file"]["compress_rotated"] is True
