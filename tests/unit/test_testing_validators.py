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
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

        result = validate_processor(ValidProcessor())
        assert result.valid
        assert result.plugin_type == "BaseProcessor"


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
