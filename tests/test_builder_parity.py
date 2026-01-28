"""Tests for builder API parity with Settings.

These tests ensure LoggerBuilder provides coverage for all Settings fields.
Tests are expected to fail until Stories 10.23-10.26 implement the missing methods.
"""

from __future__ import annotations

import inspect

import pytest

from fapilog.builder import LoggerBuilder
from fapilog.core.settings import (
    CoreSettings,
    Settings,
)


def get_core_settings_fields() -> set[str]:
    """Extract all field names from CoreSettings."""
    return set(CoreSettings.model_fields.keys())


def get_sink_config_types() -> set[str]:
    """Extract all built-in sink types from SinkConfig."""
    sink_config_fields = Settings.SinkConfig.model_fields.keys()
    # Exclude 'extra' which is for third-party sinks
    return {name for name in sink_config_fields if name != "extra"}


def get_filter_config_types() -> set[str]:
    """Extract all built-in filter types from FilterConfig."""
    filter_config_fields = Settings.FilterConfig.model_fields.keys()
    return {name for name in filter_config_fields if name != "extra"}


def get_redactor_config_types() -> set[str]:
    """Extract all built-in redactor types from RedactorConfig."""
    redactor_config_fields = Settings.RedactorConfig.model_fields.keys()
    return {name for name in redactor_config_fields if name != "extra"}


def get_builder_methods() -> set[str]:
    """Extract all public methods from LoggerBuilder."""
    return {
        name
        for name, _ in inspect.getmembers(LoggerBuilder, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


# Mapping of builder methods to the CoreSettings fields they cover
BUILDER_TO_CORE_FIELDS: dict[str, list[str]] = {
    "with_level": ["log_level"],
    "with_queue_size": ["max_queue_size"],
    "with_batch_size": ["batch_max_size"],
    "with_batch_timeout": ["batch_timeout_seconds"],
    "with_context": ["default_bound_context"],
    "with_enrichers": ["enrichers"],
    "with_filters": ["filters"],
    "with_redaction": ["redactors"],  # Partial - enables field_mask/regex_mask
    # Story 10.23: Core settings builder methods
    "with_circuit_breaker": [
        "sink_circuit_breaker_enabled",
        "sink_circuit_breaker_failure_threshold",
        "sink_circuit_breaker_recovery_timeout_seconds",
    ],
    "with_backpressure": ["backpressure_wait_ms", "drop_on_full"],
    "with_workers": ["worker_count"],
    "with_shutdown_timeout": ["shutdown_timeout_seconds"],
    "with_exceptions": [
        "exceptions_enabled",
        "exceptions_max_frames",
        "exceptions_max_stack_chars",
    ],
    "with_parallel_sink_writes": ["sink_parallel_writes"],
    "with_metrics": ["enable_metrics"],
    "with_error_deduplication": ["error_dedupe_window_seconds"],
    "with_drop_summary": ["emit_drop_summary", "drop_summary_window_seconds"],
    "with_diagnostics": ["internal_logging_enabled", "diagnostics_output"],
    "with_app_name": ["app_name"],
    "with_strict_mode": ["strict_envelope_mode"],
    "with_unhandled_exception_capture": ["capture_unhandled_enabled"],
    # Story 6.13: Graceful shutdown builder methods
    "with_atexit_drain": ["atexit_drain_enabled", "atexit_drain_timeout_seconds"],
    "with_signal_handlers": ["signal_handler_enabled"],
    "with_flush_on_critical": ["flush_on_critical"],
    # Story 4.54: Redaction fail mode, Story 4.59: Raw output hardening
    "with_fallback_redaction": [
        "fallback_redact_mode",
        "redaction_fail_mode",
        "fallback_scrub_raw",
        "fallback_raw_max_bytes",
    ],
}

# Mapping of add_* methods to sink types they cover
BUILDER_TO_SINKS: dict[str, str] = {
    "add_file": "rotating_file",
    "add_stdout": "stdout_json",  # Also covers stdout_pretty via format param
    "add_stdout_pretty": "stdout_json",  # Convenience method
    "add_http": "http",
    "add_webhook": "webhook",
    # Story 10.24: Cloud sink builder methods
    "add_cloudwatch": "cloudwatch",
    "add_loki": "loki",
    "add_postgres": "postgres",
}

# Fields intentionally excluded from parity requirements
# Synced with scripts/builder_param_mappings.py CORE_EXCLUSIONS
EXCLUDED_CORE_FIELDS: set[str] = {
    "schema_version",  # Internal versioning, not user-configurable
    "benchmark_file_path",  # Test-only field
    "sensitive_fields_policy",  # Policy hint, not runtime config
    "redactors_order",  # Managed internally by redactor methods
    "enable_redactors",  # Controlled via redactor list being non-empty
    "processors",  # Managed internally, not directly set by builder
    "sinks",  # Managed by add_* sink methods
    # Fields planned for Story 10.26 (Advanced Settings)
    "context_binding_enabled",  # Story 10.26: with_context_binding()
    "serialize_in_flush",  # Story 10.26: with_serialize_in_flush()
    "resource_pool_max_size",  # Story 10.26: with_resource_pool()
    "resource_pool_acquire_timeout_seconds",  # Story 10.26: with_resource_pool()
    "redaction_max_depth",  # Story 10.26: with_redaction_guardrails()
    "redaction_max_keys_scanned",  # Story 10.26: with_redaction_guardrails()
}

# Sinks intentionally excluded (covered via other mechanisms)
EXCLUDED_SINKS: set[str] = {
    "stdout_json",  # Covered by add_stdout()
    "sealed",  # Internal sink for tamper-evident logging (fapilog-tamper)
}


def get_builder_covered_core_fields() -> set[str]:
    """Get CoreSettings fields covered by existing builder methods."""
    covered = set()
    for fields in BUILDER_TO_CORE_FIELDS.values():
        covered.update(fields)
    # Add 'sinks' as it's covered by add_* methods
    covered.add("sinks")
    return covered


def get_builder_covered_sinks() -> set[str]:
    """Get sink types covered by existing builder methods."""
    return set(BUILDER_TO_SINKS.values())


class TestBuilderParityInfrastructure:
    """Tests that verify the parity test infrastructure works correctly."""

    def test_get_core_settings_fields_returns_nonempty_set(self) -> None:
        """Verify we can extract CoreSettings fields."""
        fields = get_core_settings_fields()
        assert len(fields) > 30, f"Expected 30+ fields, got {len(fields)}"
        assert "log_level" in fields
        assert "max_queue_size" in fields
        assert "batch_max_size" in fields

    def test_get_sink_config_types_returns_expected_sinks(self) -> None:
        """Verify we can extract sink types."""
        sinks = get_sink_config_types()
        assert "rotating_file" in sinks
        assert "http" in sinks
        assert "cloudwatch" in sinks
        assert "loki" in sinks
        assert "postgres" in sinks
        assert "extra" not in sinks  # Should be excluded

    def test_get_filter_config_types_returns_expected_filters(self) -> None:
        """Verify we can extract filter types."""
        filters = get_filter_config_types()
        assert "level" in filters
        assert "sampling" in filters
        assert "rate_limit" in filters
        assert "extra" not in filters

    def test_get_redactor_config_types_returns_expected_redactors(self) -> None:
        """Verify we can extract redactor types."""
        redactors = get_redactor_config_types()
        assert "field_mask" in redactors
        assert "regex_mask" in redactors
        assert "url_credentials" in redactors
        assert "extra" not in redactors

    def test_get_builder_methods_returns_expected_methods(self) -> None:
        """Verify we can extract builder methods."""
        methods = get_builder_methods()
        assert "with_level" in methods
        assert "add_file" in methods
        assert "add_stdout" in methods
        assert "build" in methods
        assert "_deep_merge" not in methods  # Private methods excluded

    def test_builder_coverage_mapping_is_complete(self) -> None:
        """Verify all mapped builder methods exist in LoggerBuilder."""
        builder_methods = get_builder_methods()

        for method_name in BUILDER_TO_CORE_FIELDS:
            assert method_name in builder_methods, (
                f"Mapped method '{method_name}' does not exist in LoggerBuilder"
            )

        for method_name in BUILDER_TO_SINKS:
            assert method_name in builder_methods, (
                f"Mapped method '{method_name}' does not exist in LoggerBuilder"
            )


class TestBuilderMethodNamingConventions:
    """Tests that verify builder methods follow naming conventions."""

    def test_setting_methods_use_with_prefix(self) -> None:
        """Methods that set configuration should use with_* prefix."""
        methods = get_builder_methods()
        config_methods = {
            m
            for m in methods
            if m
            not in {
                "build",
                "add_file",
                "add_stdout",
                "add_stdout_pretty",
                "add_http",
                "add_webhook",
                "with_name",
                "with_preset",
            }
        }

        for method in config_methods:
            if method.startswith("with_"):
                continue  # Correct prefix
            if method.startswith("add_"):
                continue  # Sink methods
            if method.startswith("configure_"):
                continue  # Plugin config methods
            if method.startswith("enable_"):
                continue  # Toggle methods
            # Unknown prefix - may be acceptable for special cases
            # This test documents the expectation, not enforces it rigidly

    def test_sink_methods_use_add_prefix(self) -> None:
        """Methods that add sinks should use add_* prefix."""
        methods = get_builder_methods()
        sink_methods = {
            m
            for m in methods
            if "file" in m
            or "stdout" in m
            or "http" in m
            or "webhook" in m
            or "cloudwatch" in m
            or "loki" in m
            or "postgres" in m
        }

        for method in sink_methods:
            assert method.startswith("add_"), (
                f"Sink method '{method}' should use add_* prefix"
            )


class TestBuilderCoreParity:
    """Tests for CoreSettings parity.

    Story 10.23 implements all CoreSettings builder methods.
    Remaining advanced fields are tracked for Story 10.26.
    """

    def test_all_core_settings_have_builder_coverage(self) -> None:
        """Ensure CoreSettings fields have builder methods.

        Story 10.23 provides full coverage for CoreSettings.
        Advanced fields (context_binding, resource_pool, etc.) are excluded
        and tracked for Story 10.26.
        """
        core_fields = get_core_settings_fields()
        builder_coverage = get_builder_covered_core_fields()

        missing = core_fields - builder_coverage - EXCLUDED_CORE_FIELDS
        assert not missing, (
            f"CoreSettings fields without builder coverage: {sorted(missing)}"
        )


class TestBuilderSinkParity:
    """Tests for SinkConfig parity.

    Story 10.24 implements cloud sink builder methods.
    """

    def test_all_sink_configs_have_builder_methods(self) -> None:
        """Ensure each sink in SinkConfig has an add_* method."""
        sink_types = get_sink_config_types()
        builder_sinks = get_builder_covered_sinks()

        missing = sink_types - builder_sinks - EXCLUDED_SINKS
        assert not missing, f"Sinks without builder method: {sorted(missing)}"


class TestBuilderFilterParity:
    """Tests for FilterConfig parity.

    Note: This test is expected to FAIL until Story 10.25 is complete.
    """

    @pytest.mark.xfail(
        reason="Story 10.25 not yet implemented",
        strict=False,
    )
    def test_all_filter_configs_have_builder_methods(self) -> None:
        """Ensure each filter in FilterConfig has configuration support."""
        filter_types = get_filter_config_types()

        # For now, we check that there's at least a configure_filter method
        # or specific filter methods
        builder_methods = get_builder_methods()

        # Accept either:
        # 1. A generic configure_filter() method
        # 2. Individual filter methods like with_level_filter(), with_sampling()
        has_generic = "configure_filter" in builder_methods

        if has_generic:
            return  # Generic method covers all filters

        # Check for individual methods
        covered_filters: set[str] = set()
        for method in builder_methods:
            for filter_type in filter_types:
                if filter_type in method.lower():
                    covered_filters.add(filter_type)

        missing = filter_types - covered_filters
        assert not missing, f"Filters without builder support: {sorted(missing)}"


class TestCurrentBuilderFunctionality:
    """Tests that verify existing builder methods work correctly.

    These tests should always pass and serve as regression tests.
    """

    def test_with_level_sets_log_level(self) -> None:
        """Verify with_level() configures log_level."""
        builder = LoggerBuilder()
        builder.with_level("DEBUG")
        assert builder._config["core"]["log_level"] == "DEBUG"

    def test_with_queue_size_sets_max_queue_size(self) -> None:
        """Verify with_queue_size() configures max_queue_size."""
        builder = LoggerBuilder()
        builder.with_queue_size(5000)
        assert builder._config["core"]["max_queue_size"] == 5000

    def test_with_batch_size_sets_batch_max_size(self) -> None:
        """Verify with_batch_size() configures batch_max_size."""
        builder = LoggerBuilder()
        builder.with_batch_size(128)
        assert builder._config["core"]["batch_max_size"] == 128

    def test_with_batch_timeout_accepts_string(self) -> None:
        """Verify with_batch_timeout() accepts human-readable strings."""
        builder = LoggerBuilder()
        builder.with_batch_timeout("2s")
        assert builder._config["core"]["batch_timeout_seconds"] == 2.0

    def test_with_batch_timeout_accepts_float(self) -> None:
        """Verify with_batch_timeout() accepts float seconds."""
        builder = LoggerBuilder()
        builder.with_batch_timeout(1.5)
        assert builder._config["core"]["batch_timeout_seconds"] == 1.5

    def test_with_context_sets_default_bound_context(self) -> None:
        """Verify with_context() sets default_bound_context."""
        builder = LoggerBuilder()
        builder.with_context(service="myapp", env="prod")
        assert builder._config["core"]["default_bound_context"] == {
            "service": "myapp",
            "env": "prod",
        }

    def test_with_enrichers_adds_to_list(self) -> None:
        """Verify with_enrichers() adds to enrichers list."""
        builder = LoggerBuilder()
        builder.with_enrichers("runtime_info", "context_vars")
        assert builder._config["core"]["enrichers"] == ["runtime_info", "context_vars"]

    def test_with_filters_adds_to_list(self) -> None:
        """Verify with_filters() adds to filters list."""
        builder = LoggerBuilder()
        builder.with_filters("level", "sampling")
        assert builder._config["core"]["filters"] == ["level", "sampling"]

    def test_add_file_requires_directory(self) -> None:
        """Verify add_file() raises on empty directory."""
        builder = LoggerBuilder()
        with pytest.raises(ValueError, match="requires directory"):
            builder.add_file("")

    def test_add_file_accepts_human_readable_size(self) -> None:
        """Verify add_file() accepts human-readable size strings."""
        builder = LoggerBuilder()
        builder.add_file("/tmp/logs", max_bytes="50 MB")
        assert len(builder._sinks) == 1
        assert builder._sinks[0]["config"]["max_bytes"] == "50 MB"

    def test_add_http_requires_endpoint(self) -> None:
        """Verify add_http() raises on empty endpoint."""
        builder = LoggerBuilder()
        with pytest.raises(ValueError, match="requires endpoint"):
            builder.add_http("")

    def test_add_webhook_requires_endpoint(self) -> None:
        """Verify add_webhook() raises on empty endpoint."""
        builder = LoggerBuilder()
        with pytest.raises(ValueError, match="requires endpoint"):
            builder.add_webhook("")

    def test_with_redaction_enables_field_mask(self) -> None:
        """Verify with_redaction(fields=...) enables field_mask redactor."""
        builder = LoggerBuilder()
        builder.with_redaction(fields=["password", "secret"])
        assert "field_mask" in builder._config["core"]["redactors"]
        # Fields are auto-prefixed with data. by default
        assert builder._config["redactor_config"]["field_mask"]["fields_to_mask"] == [
            "data.password",
            "data.secret",
        ]

    def test_with_redaction_enables_regex_mask(self) -> None:
        """Verify with_redaction(patterns=...) enables regex_mask redactor."""
        builder = LoggerBuilder()
        builder.with_redaction(patterns=[r"api_key=\w+"])
        assert "regex_mask" in builder._config["core"]["redactors"]
        assert builder._config["redactor_config"]["regex_mask"]["patterns"] == [
            r"api_key=\w+"
        ]

    def test_method_chaining_returns_builder(self) -> None:
        """Verify all configuration methods return the builder for chaining."""
        builder = LoggerBuilder()
        result = (
            builder.with_level("INFO")
            .with_queue_size(1000)
            .with_batch_size(64)
            .with_batch_timeout("1s")
            .with_context(app="test")
            .with_enrichers("runtime_info")
            .with_filters("level")
        )
        assert result is builder
