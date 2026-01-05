"""
Verify all protocols require name attribute.

Story 4.30: Plugin API Standardization and Testing Documentation
"""

from __future__ import annotations

from fapilog.plugins import (
    BaseEnricher,
    BaseFilter,
    BaseProcessor,
    BaseRedactor,
    BaseSink,
)


class TestProtocolsHaveNameAttribute:
    """Test that all plugin protocols require a name attribute."""

    def test_base_sink_has_name_in_annotations(self) -> None:
        """BaseSink protocol should require name attribute."""
        assert "name" in getattr(BaseSink, "__annotations__", {})

    def test_base_enricher_has_name_in_annotations(self) -> None:
        """BaseEnricher protocol should require name attribute."""
        assert "name" in getattr(BaseEnricher, "__annotations__", {})

    def test_base_processor_has_name_in_annotations(self) -> None:
        """BaseProcessor protocol should require name attribute."""
        assert "name" in getattr(BaseProcessor, "__annotations__", {})

    def test_base_redactor_has_name_in_annotations(self) -> None:
        """BaseRedactor protocol should require name attribute (already had it)."""
        assert "name" in getattr(BaseRedactor, "__annotations__", {})


class TestIsinstanceChecksWithName:
    """Test that isinstance checks work correctly with/without name."""

    def test_sink_with_name_satisfies_protocol(self) -> None:
        """Plugin with name should satisfy BaseSink protocol."""

        class _SinkWithName:
            name = "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        sink = _SinkWithName()
        assert isinstance(sink, BaseSink)

    def test_sink_without_name_fails_protocol(self) -> None:
        """Plugin without name should NOT satisfy BaseSink protocol."""

        class _SinkWithoutName:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def write(self, entry: dict) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        sink = _SinkWithoutName()
        assert not isinstance(sink, BaseSink)

    def test_enricher_with_name_satisfies_protocol(self) -> None:
        """Plugin with name should satisfy BaseEnricher protocol."""

        class _EnricherWithName:
            name = "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict) -> dict:
                return {}

            async def health_check(self) -> bool:
                return True

        enricher = _EnricherWithName()
        assert isinstance(enricher, BaseEnricher)

    def test_enricher_without_name_fails_protocol(self) -> None:
        """Plugin without name should NOT satisfy BaseEnricher protocol."""

        class _EnricherWithoutName:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict) -> dict:
                return {}

            async def health_check(self) -> bool:
                return True

        enricher = _EnricherWithoutName()
        assert not isinstance(enricher, BaseEnricher)

    def test_processor_with_name_satisfies_protocol(self) -> None:
        """Plugin with name should satisfy BaseProcessor protocol."""

        class _ProcessorWithName:
            name = "test"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

            async def process_many(self, views):
                return []

            async def health_check(self) -> bool:
                return True

        processor = _ProcessorWithName()
        assert isinstance(processor, BaseProcessor)

    def test_processor_without_name_fails_protocol(self) -> None:
        """Plugin without name should NOT satisfy BaseProcessor protocol."""

        class _ProcessorWithoutName:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def process(self, view: memoryview) -> memoryview:
                return view

            async def process_many(self, views):
                return []

            async def health_check(self) -> bool:
                return True

        processor = _ProcessorWithoutName()
        assert not isinstance(processor, BaseProcessor)

    def test_filter_with_name_satisfies_protocol(self) -> None:
        """Filter with name should satisfy BaseFilter protocol."""

        class _FilterWithName:
            name = "filter"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def filter(self, event: dict) -> dict | None:
                return event

            async def health_check(self) -> bool:
                return True

        f = _FilterWithName()
        assert isinstance(f, BaseFilter)

    def test_filter_without_name_fails_protocol(self) -> None:
        """Filter without name should NOT satisfy BaseFilter protocol."""

        class _FilterWithoutName:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def filter(self, event: dict) -> dict | None:
                return event

            async def health_check(self) -> bool:
                return True

        f = _FilterWithoutName()
        assert not isinstance(f, BaseFilter)
