"""
TDD tests for Story 4.27: Plugin Testing Utilities - Mock implementations.

Tests for MockSink, MockEnricher, MockRedactor, MockProcessor.
"""

from __future__ import annotations

import pytest


class TestMockSink:
    """Tests for MockSink test utility."""

    @pytest.mark.asyncio
    async def test_mock_sink_captures_events(self) -> None:
        """MockSink should capture all written events."""
        from fapilog.testing import MockSink

        sink = MockSink()
        await sink.start()

        await sink.write({"level": "INFO", "message": "test1"})
        await sink.write({"level": "ERROR", "message": "test2"})

        assert len(sink.events) == 2
        assert sink.events[0]["message"] == "test1"
        assert sink.events[1]["message"] == "test2"
        assert sink.write_count == 2

    @pytest.mark.asyncio
    async def test_mock_sink_tracks_lifecycle(self) -> None:
        """MockSink should track start/stop calls."""
        from fapilog.testing import MockSink

        sink = MockSink()
        assert not sink.start_called
        assert not sink.stop_called

        await sink.start()
        assert sink.start_called

        await sink.stop()
        assert sink.stop_called

    @pytest.mark.asyncio
    async def test_mock_sink_fails_after_configured(self) -> None:
        """MockSink should fail after configured number of writes."""
        from fapilog.testing import MockSink, MockSinkConfig

        sink = MockSink(MockSinkConfig(fail_after=2))

        await sink.write({"n": 1})
        await sink.write({"n": 2})

        with pytest.raises(RuntimeError, match="Mock failure"):
            await sink.write({"n": 3})

    @pytest.mark.asyncio
    async def test_mock_sink_fails_with_custom_exception(self) -> None:
        """MockSink should raise configured exception."""
        from fapilog.testing import MockSink, MockSinkConfig

        sink = MockSink(
            MockSinkConfig(fail_after=0, fail_with=ConnectionError("Timeout"))
        )

        with pytest.raises(ConnectionError, match="Timeout"):
            await sink.write({"n": 1})

    @pytest.mark.asyncio
    async def test_mock_sink_simulates_latency(self) -> None:
        """MockSink should add configured latency."""
        import time

        from fapilog.testing import MockSink, MockSinkConfig

        sink = MockSink(MockSinkConfig(latency_seconds=0.05))

        start = time.monotonic()
        await sink.write({"test": True})
        elapsed = time.monotonic() - start

        assert elapsed >= 0.05

    @pytest.mark.asyncio
    async def test_mock_sink_health_check(self) -> None:
        """MockSink should return configured health status."""
        from fapilog.testing import MockSink, MockSinkConfig

        healthy_sink = MockSink(MockSinkConfig(health_status=True))
        unhealthy_sink = MockSink(MockSinkConfig(health_status=False))

        assert await healthy_sink.health_check() is True
        assert await unhealthy_sink.health_check() is False
        assert healthy_sink.health_check_count == 1

    @pytest.mark.asyncio
    async def test_mock_sink_reset(self) -> None:
        """MockSink.reset() should clear all state."""
        from fapilog.testing import MockSink

        sink = MockSink()
        await sink.start()
        await sink.write({"test": True})
        await sink.health_check()

        sink.reset()

        assert len(sink.events) == 0
        assert sink.write_count == 0
        assert not sink.start_called
        assert sink.health_check_count == 0

    def test_mock_sink_has_name(self) -> None:
        """MockSink should have name attribute."""
        from fapilog.testing import MockSink

        assert MockSink.name == "mock"

    def test_mock_sink_assert_event_count(self) -> None:
        """MockSink.assert_event_count should verify event count."""
        from fapilog.testing import MockSink

        sink = MockSink()
        sink.events = [{"a": 1}, {"b": 2}]

        sink.assert_event_count(2)  # Should pass

        with pytest.raises(AssertionError, match="Expected 5 events"):
            sink.assert_event_count(5)

    def test_mock_sink_assert_event_contains(self) -> None:
        """MockSink.assert_event_contains should verify event fields."""
        from fapilog.testing import MockSink

        sink = MockSink()
        sink.events = [{"level": "INFO", "message": "test"}]

        sink.assert_event_contains(0, level="INFO")  # Should pass

        with pytest.raises(AssertionError, match="expected 'ERROR'"):
            sink.assert_event_contains(0, level="ERROR")

        with pytest.raises(AssertionError, match="No event at index"):
            sink.assert_event_contains(5, level="INFO")


class TestMockEnricher:
    """Tests for MockEnricher test utility."""

    @pytest.mark.asyncio
    async def test_mock_enricher_adds_fields(self) -> None:
        """MockEnricher should return configured fields."""
        from fapilog.testing import MockEnricher, MockEnricherConfig

        enricher = MockEnricher(
            MockEnricherConfig(fields_to_add={"env": "test", "service": "app"})
        )

        event = {"level": "INFO"}
        result = await enricher.enrich(event)

        assert result == {"env": "test", "service": "app"}
        assert len(enricher.enriched_events) == 1
        assert enricher.call_count == 1

    @pytest.mark.asyncio
    async def test_mock_enricher_tracks_lifecycle(self) -> None:
        """MockEnricher should track start/stop."""
        from fapilog.testing import MockEnricher

        enricher = MockEnricher()
        assert not enricher.start_called

        await enricher.start()
        assert enricher.start_called

        await enricher.stop()
        assert enricher.stop_called

    @pytest.mark.asyncio
    async def test_mock_enricher_fails_on_call(self) -> None:
        """MockEnricher should fail on configured call number."""
        from fapilog.testing import MockEnricher, MockEnricherConfig

        enricher = MockEnricher(MockEnricherConfig(fail_on_call=2))

        await enricher.enrich({})  # Call 1 - OK
        with pytest.raises(RuntimeError, match="Mock enricher failure"):
            await enricher.enrich({})  # Call 2 - Fail

    @pytest.mark.asyncio
    async def test_mock_enricher_reset(self) -> None:
        """MockEnricher.reset() should clear state."""
        from fapilog.testing import MockEnricher

        enricher = MockEnricher()
        await enricher.start()
        await enricher.enrich({})

        enricher.reset()

        assert len(enricher.enriched_events) == 0
        assert enricher.call_count == 0
        assert not enricher.start_called


class TestMockRedactor:
    """Tests for MockRedactor test utility."""

    @pytest.mark.asyncio
    async def test_mock_redactor_masks_fields(self) -> None:
        """MockRedactor should mask configured fields."""
        from fapilog.testing import MockRedactor, MockRedactorConfig

        redactor = MockRedactor(MockRedactorConfig(fields_to_mask=["password"]))

        event = {"user": "alice", "password": "secret123"}
        result = await redactor.redact(event)

        assert result["user"] == "alice"
        assert result["password"] == "***MOCK***"

    @pytest.mark.asyncio
    async def test_mock_redactor_masks_nested_fields(self) -> None:
        """MockRedactor should mask nested fields using dot notation."""
        from fapilog.testing import MockRedactor, MockRedactorConfig

        redactor = MockRedactor(MockRedactorConfig(fields_to_mask=["user.password"]))

        event = {"user": {"name": "alice", "password": "secret"}}
        result = await redactor.redact(event)

        assert result["user"]["name"] == "alice"
        assert result["user"]["password"] == "***MOCK***"

    @pytest.mark.asyncio
    async def test_mock_redactor_custom_mask(self) -> None:
        """MockRedactor should use custom mask string."""
        from fapilog.testing import MockRedactor, MockRedactorConfig

        redactor = MockRedactor(
            MockRedactorConfig(fields_to_mask=["secret"], mask_string="[REDACTED]")
        )

        result = await redactor.redact({"secret": "value"})
        assert result["secret"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_mock_redactor_tracks_calls(self) -> None:
        """MockRedactor should track call count."""
        from fapilog.testing import MockRedactor

        redactor = MockRedactor()
        await redactor.redact({})
        await redactor.redact({})

        assert redactor.call_count == 2
        assert len(redactor.redacted_events) == 2


class TestMockProcessor:
    """Tests for MockProcessor test utility."""

    @pytest.mark.asyncio
    async def test_mock_processor_returns_view(self) -> None:
        """MockProcessor should return the same memoryview."""
        from fapilog.testing import MockProcessor

        processor = MockProcessor()
        data = b"test data"
        view = memoryview(data)

        result = await processor.process(view)

        assert result is view
        assert processor.call_count == 1
        assert len(processor.processed_views) == 1

    @pytest.mark.asyncio
    async def test_mock_processor_tracks_lifecycle(self) -> None:
        """MockProcessor should implement start/stop."""
        from fapilog.testing import MockProcessor

        processor = MockProcessor()
        await processor.start()
        await processor.stop()
        # Should not raise

    @pytest.mark.asyncio
    async def test_mock_processor_health_check(self) -> None:
        """MockProcessor should return True for health check."""
        from fapilog.testing import MockProcessor

        processor = MockProcessor()
        assert await processor.health_check() is True


class TestMockFilter:
    """Tests for MockFilter test utility."""

    @pytest.mark.asyncio
    async def test_mock_filter_passes_events(self) -> None:
        """MockFilter should return events it allows."""
        from fapilog.testing import MockFilter

        filter_plugin = MockFilter()
        event = {"level": "INFO", "message": "ok"}

        result = await filter_plugin.filter(event)

        assert result == event
        assert filter_plugin.filtered_events[0]["message"] == "ok"
        assert filter_plugin.call_count == 1

    @pytest.mark.asyncio
    async def test_mock_filter_drops_by_level(self) -> None:
        """MockFilter should drop events matching configured levels."""
        from fapilog.testing import MockFilter, MockFilterConfig

        filter_plugin = MockFilter(MockFilterConfig(drop_levels=["ERROR"]))

        result = await filter_plugin.filter({"level": "ERROR", "message": "nope"})

        assert result is None
        assert len(filter_plugin.dropped_events) == 1
        assert filter_plugin.call_count == 1

    @pytest.mark.asyncio
    async def test_mock_filter_drops_by_rate(self) -> None:
        """MockFilter should drop events based on drop_rate."""
        from fapilog.testing import MockFilter, MockFilterConfig

        filter_plugin = MockFilter(MockFilterConfig(drop_rate=1.0))

        result = await filter_plugin.filter({"level": "INFO", "message": "sometimes"})

        assert result is None
        assert len(filter_plugin.dropped_events) == 1

    @pytest.mark.asyncio
    async def test_mock_filter_injects_failure(self) -> None:
        """MockFilter should raise on configured call number."""
        from fapilog.testing import MockFilter, MockFilterConfig

        filter_plugin = MockFilter(MockFilterConfig(fail_on_call=2))

        await filter_plugin.filter({"n": 1})
        with pytest.raises(RuntimeError, match="Mock filter failure"):
            await filter_plugin.filter({"n": 2})

    @pytest.mark.asyncio
    async def test_mock_filter_tracks_lifecycle_and_reset(self) -> None:
        """MockFilter should track lifecycle calls and reset state."""
        from fapilog.testing import MockFilter

        filter_plugin = MockFilter()
        assert not filter_plugin.start_called
        assert not filter_plugin.stop_called

        await filter_plugin.start()
        await filter_plugin.filter({"level": "INFO"})
        await filter_plugin.stop()

        assert filter_plugin.start_called is True
        assert filter_plugin.stop_called is True
        assert filter_plugin.call_count == 1

        filter_plugin.reset()
        assert filter_plugin.call_count == 0
        assert not filter_plugin.start_called
        assert not filter_plugin.stop_called
