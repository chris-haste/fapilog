"""Tests for builder parameter mappings registry.

These tests ensure the mapping registry is complete and consistent with
the actual Settings classes and builder methods.
"""

from __future__ import annotations


class TestCoreCoverageMapping:
    """Tests for CORE_COVERAGE mapping completeness."""

    def test_core_coverage_import_succeeds(self) -> None:
        """Verify the CORE_COVERAGE mapping can be imported."""
        from scripts.builder_param_mappings import CORE_COVERAGE

        assert isinstance(CORE_COVERAGE, dict)
        assert len(CORE_COVERAGE) > 0

    def test_core_coverage_contains_expected_methods(self) -> None:
        """Verify CORE_COVERAGE maps expected builder methods."""
        from scripts.builder_param_mappings import CORE_COVERAGE

        expected_methods = [
            "with_level",
            "with_queue_size",
            "with_batch_size",
            "with_batch_timeout",
            "with_context",
            "with_enrichers",
            "with_filters",
            "with_redaction",
        ]
        for method in expected_methods:
            assert method in CORE_COVERAGE, f"Missing method mapping: {method}"

    def test_core_coverage_values_are_lists(self) -> None:
        """Verify all CORE_COVERAGE values are lists of field names."""
        from scripts.builder_param_mappings import CORE_COVERAGE

        for method, fields in CORE_COVERAGE.items():
            assert isinstance(fields, list), f"{method} should map to a list"
            for field in fields:
                assert isinstance(field, str), f"{method} fields should be strings"


class TestSinkParamMappings:
    """Tests for SINK_PARAM_MAPPINGS completeness."""

    def test_sink_param_mappings_import_succeeds(self) -> None:
        """Verify the SINK_PARAM_MAPPINGS can be imported."""
        from scripts.builder_param_mappings import SINK_PARAM_MAPPINGS

        assert isinstance(SINK_PARAM_MAPPINGS, dict)

    def test_sink_param_mappings_contains_cloud_sinks(self) -> None:
        """Verify SINK_PARAM_MAPPINGS covers all cloud sinks."""
        from scripts.builder_param_mappings import SINK_PARAM_MAPPINGS

        expected_sinks = ["add_cloudwatch", "add_loki", "add_postgres"]
        for sink in expected_sinks:
            assert sink in SINK_PARAM_MAPPINGS, f"Missing sink mapping: {sink}"

    def test_sink_mappings_have_param_to_field_dicts(self) -> None:
        """Verify sink mappings contain param->field dictionaries."""
        from scripts.builder_param_mappings import SINK_PARAM_MAPPINGS

        for sink_method, mappings in SINK_PARAM_MAPPINGS.items():
            assert isinstance(mappings, dict), f"{sink_method} should map to a dict"
            for param, field in mappings.items():
                assert isinstance(param, str), f"{sink_method} params should be strings"
                assert isinstance(field, str), f"{sink_method} fields should be strings"


class TestFilterCoverageMapping:
    """Tests for FILTER_COVERAGE mapping."""

    def test_filter_coverage_import_succeeds(self) -> None:
        """Verify the FILTER_COVERAGE mapping can be imported."""
        from scripts.builder_param_mappings import FILTER_COVERAGE

        assert isinstance(FILTER_COVERAGE, dict)

    def test_filter_coverage_contains_expected_filters(self) -> None:
        """Verify FILTER_COVERAGE covers all expected filters."""
        from scripts.builder_param_mappings import FILTER_COVERAGE

        expected_filters = [
            "sampling",
            "rate_limit",
            "adaptive_sampling",
            "trace_sampling",
            "first_occurrence",
        ]
        for filter_type in expected_filters:
            assert filter_type in FILTER_COVERAGE, f"Missing filter: {filter_type}"


class TestProcessorCoverageMapping:
    """Tests for PROCESSOR_COVERAGE mapping."""

    def test_processor_coverage_import_succeeds(self) -> None:
        """Verify the PROCESSOR_COVERAGE mapping can be imported."""
        from scripts.builder_param_mappings import PROCESSOR_COVERAGE

        assert isinstance(PROCESSOR_COVERAGE, dict)

    def test_processor_coverage_contains_size_guard(self) -> None:
        """Verify PROCESSOR_COVERAGE covers size_guard."""
        from scripts.builder_param_mappings import PROCESSOR_COVERAGE

        assert "size_guard" in PROCESSOR_COVERAGE
        assert isinstance(PROCESSOR_COVERAGE["size_guard"], dict)


class TestAdvancedCoverageMapping:
    """Tests for ADVANCED_COVERAGE mapping."""

    def test_advanced_coverage_import_succeeds(self) -> None:
        """Verify the ADVANCED_COVERAGE mapping can be imported."""
        from scripts.builder_param_mappings import ADVANCED_COVERAGE

        assert isinstance(ADVANCED_COVERAGE, dict)

    def test_advanced_coverage_contains_expected_methods(self) -> None:
        """Verify ADVANCED_COVERAGE covers routing, redactors, and plugins."""
        from scripts.builder_param_mappings import ADVANCED_COVERAGE

        expected_methods = [
            "with_routing",
            "with_redaction",  # Unified API replaces field_mask, regex_mask, etc.
            "with_plugins",
        ]
        for method in expected_methods:
            assert method in ADVANCED_COVERAGE, f"Missing method: {method}"


class TestExclusionLists:
    """Tests for exclusion lists."""

    def test_core_exclusions_import_succeeds(self) -> None:
        """Verify CORE_EXCLUSIONS can be imported."""
        from scripts.builder_param_mappings import CORE_EXCLUSIONS

        assert isinstance(CORE_EXCLUSIONS, set)

    def test_core_exclusions_contains_expected_fields(self) -> None:
        """Verify CORE_EXCLUSIONS contains intentionally excluded fields."""
        from scripts.builder_param_mappings import CORE_EXCLUSIONS

        expected = ["schema_version", "benchmark_file_path"]
        for field in expected:
            assert field in CORE_EXCLUSIONS, f"Missing exclusion: {field}"

    def test_sink_exclusions_import_succeeds(self) -> None:
        """Verify SINK_EXCLUSIONS can be imported."""
        from scripts.builder_param_mappings import SINK_EXCLUSIONS

        assert isinstance(SINK_EXCLUSIONS, set)
