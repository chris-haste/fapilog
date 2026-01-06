"""
TDD tests for Story 4.27: Plugin Testing Utilities - Validators.

Tests for validate_sink, validate_enricher, validate_redactor, validate_processor.
"""

from __future__ import annotations

import pytest


class TestValidateSink:
    """Tests for validate_sink validator."""

    def test_validate_sink_valid(self) -> None:
        """Valid sink should pass validation."""
        from fapilog.testing import validate_sink

        class ValidSink:
            name = "valid"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(ValidSink())
        assert result.valid
        assert result.plugin_type == "BaseSink"
        assert len(result.errors) == 0
        assert isinstance(result.warnings, list)

    def test_validate_sink_warns_without_write_serialized(self) -> None:
        """Sink without write_serialized should emit informational warning."""
        from fapilog.testing import validate_sink

        class NoFastPath:
            name = "no-fast-path"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(NoFastPath())
        assert result.valid
        assert any("write_serialized" in w for w in result.warnings)

    def test_validate_sink_missing_method(self) -> None:
        """Sink missing required method should fail."""
        from fapilog.testing import validate_sink

        class MissingWrite:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        result = validate_sink(MissingWrite())
        assert not result.valid
        assert "Missing required method: write" in result.errors

    def test_validate_sink_sync_method(self) -> None:
        """Sink with sync method should fail."""
        from fapilog.testing import validate_sink

        class SyncWrite:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            def write(self, entry: dict) -> None:  # Not async!
                pass

        result = validate_sink(SyncWrite())
        assert not result.valid
        assert "write must be async" in result.errors

    def test_validate_sink_raise_if_invalid(self) -> None:
        """ValidationResult.raise_if_invalid should raise on errors."""
        from fapilog.testing import ProtocolViolationError, validate_sink

        class Invalid:
            pass

        result = validate_sink(Invalid())
        with pytest.raises(ProtocolViolationError, match="BaseSink protocol"):
            result.raise_if_invalid()


class TestValidateEnricher:
    """Tests for validate_enricher validator."""

    def test_validate_enricher_valid(self) -> None:
        """Valid enricher should pass validation."""
        from fapilog.testing import validate_enricher

        class ValidEnricher:
            name = "valid"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict) -> dict:
                return {}

        result = validate_enricher(ValidEnricher())
        assert result.valid
        assert result.plugin_type == "BaseEnricher"

    def test_validate_enricher_missing_method(self) -> None:
        """Enricher missing enrich method should fail."""
        from fapilog.testing import validate_enricher

        class MissingEnrich:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        result = validate_enricher(MissingEnrich())
        assert not result.valid
        assert "Missing required method: enrich" in result.errors


class TestValidateRedactor:
    """Tests for validate_redactor validator."""

    def test_validate_redactor_valid(self) -> None:
        """Valid redactor should pass validation."""
        from fapilog.testing import validate_redactor

        class ValidRedactor:
            name = "valid"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def redact(self, event: dict) -> dict:
                return event

        result = validate_redactor(ValidRedactor())
        assert result.valid
        assert result.plugin_type == "BaseRedactor"

    def test_validate_redactor_missing_name(self) -> None:
        """Redactor without name should fail."""
        from fapilog.testing import validate_redactor

        class NoName:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def redact(self, event: dict) -> dict:
                return event

        result = validate_redactor(NoName())
        assert not result.valid
        assert "Redactor must have 'name' attribute" in result.errors


class TestValidateProcessor:
    """Tests for validate_processor validator."""

    def test_validate_processor_valid(self) -> None:
        """Valid processor should pass validation."""
        from fapilog.testing import validate_processor

        class ValidProcessor:
            name = "valid"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

        result = validate_processor(ValidProcessor())
        assert result.valid
        assert result.plugin_type == "BaseProcessor"


class TestValidateFilter:
    """Tests for validate_filter validator."""

    def test_validate_filter_valid(self) -> None:
        """Valid filter should pass validation."""
        from fapilog.testing import validate_filter

        class ValidFilter:
            name = "valid"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def filter(self, event: dict) -> dict | None:
                return event

            async def health_check(self) -> bool:
                return True

        result = validate_filter(ValidFilter())
        assert result.valid
        assert result.plugin_type == "BaseFilter"
        assert not result.errors

    def test_validate_filter_missing_method(self) -> None:
        """Filter missing required methods should fail validation."""
        from fapilog.testing import validate_filter

        class MissingFilter:
            name = "incomplete"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        result = validate_filter(MissingFilter())
        assert not result.valid
        assert "Missing required method: filter" in result.errors

    def test_validate_filter_bad_signature(self) -> None:
        """Filter must accept event parameter."""
        from fapilog.testing import validate_filter

        class NoEventArg:
            name = "bad-sig"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def filter(self) -> dict | None:  # type: ignore[override]
                return {}

            async def health_check(self) -> bool:
                return True

        result = validate_filter(NoEventArg())
        assert not result.valid
        assert any("event parameter" in error for error in result.errors)


class TestOptionalMethodsValidation:
    """Tests for Story 5.18: Optional lifecycle and health_check methods.

    Verifies that all validators treat start, stop, and health_check as optional,
    and that sync optional methods generate warnings (not errors).
    """

    # --- Sink ---

    def test_minimal_sink_is_valid(self) -> None:
        """A sink with only required methods (name + write) should be valid."""
        from fapilog.testing import validate_sink

        class MinimalSink:
            name = "minimal"

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(MinimalSink())
        assert result.valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        # Should have warnings about missing health_check and write_serialized
        assert any("health_check" in w for w in result.warnings)

    def test_sink_with_sync_lifecycle_warns(self) -> None:
        """Sync lifecycle methods should generate warnings, not errors."""
        from fapilog.testing import validate_sink

        class SyncLifecycleSink:
            name = "sync-lifecycle"

            def start(self) -> None:  # Not async!
                pass

            def stop(self) -> None:  # Not async!
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(SyncLifecycleSink())
        assert result.valid  # Should still be valid
        assert any("start should be async" in w for w in result.warnings)
        assert any("stop should be async" in w for w in result.warnings)

    # --- Enricher ---

    def test_minimal_enricher_is_valid(self) -> None:
        """An enricher with only required methods (name + enrich) should be valid."""
        from fapilog.testing import validate_enricher

        class MinimalEnricher:
            name = "minimal"

            async def enrich(self, event: dict) -> dict:
                return {}

        result = validate_enricher(MinimalEnricher())
        assert result.valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        assert any("health_check" in w for w in result.warnings)

    def test_enricher_with_sync_health_check_warns(self) -> None:
        """Sync health_check should generate warning, not error."""
        from fapilog.testing import validate_enricher

        class SyncHealthEnricher:
            name = "sync-health"

            async def enrich(self, event: dict) -> dict:
                return {}

            def health_check(self) -> bool:  # Not async!
                return True

        result = validate_enricher(SyncHealthEnricher())
        assert result.valid  # Should still be valid
        assert any("health_check should be async" in w for w in result.warnings)

    # --- Redactor ---

    def test_minimal_redactor_is_valid(self) -> None:
        """A redactor with only required methods (name + redact) should be valid."""
        from fapilog.testing import validate_redactor

        class MinimalRedactor:
            name = "minimal"

            async def redact(self, event: dict) -> dict:
                return event

        result = validate_redactor(MinimalRedactor())
        assert result.valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        assert any("health_check" in w for w in result.warnings)

    # --- Processor ---

    def test_minimal_processor_is_valid(self) -> None:
        """A processor with only required methods (name + process) should be valid."""
        from fapilog.testing import validate_processor

        class MinimalProcessor:
            name = "minimal"

            async def process(self, view: memoryview) -> memoryview:
                return view

        result = validate_processor(MinimalProcessor())
        assert result.valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        assert any("health_check" in w for w in result.warnings)

    # --- Filter ---

    def test_minimal_filter_is_valid(self) -> None:
        """A filter with only required methods (name + filter) should be valid."""
        from fapilog.testing import validate_filter

        class MinimalFilter:
            name = "minimal"

            async def filter(self, event: dict) -> dict | None:
                return event

        result = validate_filter(MinimalFilter())
        assert result.valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        # Should have warning about missing health_check
        assert any("health_check" in w for w in result.warnings)

    def test_filter_without_health_check_is_valid(self) -> None:
        """Missing health_check should not cause validation failure."""
        from fapilog.testing import validate_filter

        class NoHealthCheck:
            name = "no_health"

            async def filter(self, event: dict) -> dict | None:
                return event

        result = validate_filter(NoHealthCheck())
        assert result.valid
        # No error about missing health_check
        assert not any("health_check" in e for e in result.errors)
        # But should have warning
        assert any("health_check" in w for w in result.warnings)

    def test_filter_with_sync_health_check_warns(self) -> None:
        """Sync health_check should generate warning, not error."""
        from fapilog.testing import validate_filter

        class SyncHealthCheck:
            name = "sync_health"

            async def filter(self, event: dict) -> dict | None:
                return event

            def health_check(self) -> bool:  # Not async!
                return True

        result = validate_filter(SyncHealthCheck())
        assert result.valid  # Should still be valid
        assert any("health_check should be async" in w for w in result.warnings)

    def test_full_filter_is_valid(self) -> None:
        """A filter with all methods should be valid with no health_check warning."""
        from fapilog.testing import validate_filter

        class FullFilter:
            name = "full"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def filter(self, event: dict) -> dict | None:
                return event

            async def health_check(self) -> bool:
                return True

        result = validate_filter(FullFilter())
        assert result.valid, f"Errors: {result.errors}"
        assert len(result.errors) == 0
        # Should NOT have warning about missing health_check
        assert not any("health_check not implemented" in w for w in result.warnings)


class TestValidatePluginLifecycle:
    """Tests for validate_plugin_lifecycle validator."""

    @pytest.mark.asyncio
    async def test_validate_lifecycle_valid(self) -> None:
        """Plugin with working lifecycle should pass."""
        from fapilog.testing import validate_plugin_lifecycle

        class GoodPlugin:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = await validate_plugin_lifecycle(GoodPlugin())
        assert result.valid
        assert result.plugin_type == "sink"

    @pytest.mark.asyncio
    async def test_validate_lifecycle_start_raises(self) -> None:
        """Plugin with failing start should fail validation."""
        from fapilog.testing import validate_plugin_lifecycle

        class BadStart:
            async def start(self) -> None:
                raise RuntimeError("Start failed")

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = await validate_plugin_lifecycle(BadStart())
        assert not result.valid
        assert any("start() raised" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_validate_lifecycle_stop_not_idempotent(self) -> None:
        """Non-idempotent stop should generate warning."""
        from fapilog.testing import validate_plugin_lifecycle

        class NonIdempotentStop:
            _stopped = False

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                if self._stopped:
                    raise RuntimeError("Already stopped")
                self._stopped = True

            async def write(self, entry: dict) -> None:
                pass

        result = await validate_plugin_lifecycle(NonIdempotentStop())
        # Still valid, but has warning
        assert result.valid
        assert any("not idempotent" in w for w in result.warnings)
