"""
Verify validators check for name attribute.

Story 4.30: Plugin API Standardization and Testing Documentation
"""

from __future__ import annotations

from fapilog.testing import validate_enricher, validate_processor, validate_sink


class TestValidateSinkChecksName:
    """Test that validate_sink() checks for name attribute."""

    def test_validate_sink_rejects_nameless(self) -> None:
        """Sink without name should fail validation."""

        class _NamelessSink:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(_NamelessSink())
        assert not result.valid
        assert any("name" in e.lower() for e in result.errors)

    def test_validate_sink_accepts_named(self) -> None:
        """Sink with name should pass validation."""

        class _NamedSink:
            name = "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(_NamedSink())
        assert result.valid

    def test_validate_sink_rejects_non_string_name(self) -> None:
        """Sink with non-string name should fail validation."""

        class _BadNameSink:
            name = 123  # Invalid: should be string

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

        result = validate_sink(_BadNameSink())
        assert not result.valid
        assert any("name" in e.lower() and "string" in e.lower() for e in result.errors)


class TestValidateEnricherChecksName:
    """Test that validate_enricher() checks for name attribute."""

    def test_validate_enricher_rejects_nameless(self) -> None:
        """Enricher without name should fail validation."""

        class _NamelessEnricher:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict) -> dict:
                return {}

        result = validate_enricher(_NamelessEnricher())
        assert not result.valid
        assert any("name" in e.lower() for e in result.errors)

    def test_validate_enricher_accepts_named(self) -> None:
        """Enricher with name should pass validation."""

        class _NamedEnricher:
            name = "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict) -> dict:
                return {}

        result = validate_enricher(_NamedEnricher())
        assert result.valid

    def test_validate_enricher_rejects_non_string_name(self) -> None:
        """Enricher with non-string name should fail validation."""

        class _BadNameEnricher:
            name = None  # Invalid: should be string

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict) -> dict:
                return {}

        result = validate_enricher(_BadNameEnricher())
        assert not result.valid


class TestValidateProcessorChecksName:
    """Test that validate_processor() checks for name attribute."""

    def test_validate_processor_rejects_nameless(self) -> None:
        """Processor without name should fail validation."""

        class _NamelessProcessor:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

        result = validate_processor(_NamelessProcessor())
        assert not result.valid
        assert any("name" in e.lower() for e in result.errors)

    def test_validate_processor_accepts_named(self) -> None:
        """Processor with name should pass validation."""

        class _NamedProcessor:
            name = "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

        result = validate_processor(_NamedProcessor())
        assert result.valid

    def test_validate_processor_rejects_non_string_name(self) -> None:
        """Processor with non-string name should fail validation."""

        class _BadNameProcessor:
            name = []  # Invalid: should be string

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

        result = validate_processor(_BadNameProcessor())
        assert not result.valid
