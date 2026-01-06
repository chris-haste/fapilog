"""
TDD tests for Story 5.4: Plugin Testing Fixtures and helpers.
"""

from __future__ import annotations

import pytest

from fapilog.testing import (
    MockEnricher,
    MockFilter,
    MockProcessor,
    MockRedactor,
    MockSink,
    ProtocolViolationError,
)
from fapilog.testing.fixtures import (
    assert_valid_enricher,
    assert_valid_filter,
    assert_valid_processor,
    assert_valid_redactor,
    assert_valid_sink,
)


def test_mock_fixtures_create_fresh_instances(
    mock_sink: MockSink,
    mock_enricher: MockEnricher,
    mock_redactor: MockRedactor,
    mock_processor: MockProcessor,
    mock_filter: MockFilter,
) -> None:
    """Mock fixtures should yield ready-to-use instances."""
    assert isinstance(mock_sink, MockSink)
    assert isinstance(mock_enricher, MockEnricher)
    assert isinstance(mock_redactor, MockRedactor)
    assert isinstance(mock_processor, MockProcessor)
    assert isinstance(mock_filter, MockFilter)
    assert mock_sink.events == []
    assert mock_filter.call_count == 0


@pytest.mark.asyncio
async def test_started_mock_sink_lifecycle(started_mock_sink: MockSink) -> None:
    """started_mock_sink fixture should manage lifecycle."""
    assert started_mock_sink.start_called is True
    assert started_mock_sink.stop_called is False


def test_assert_valid_helpers(
    mock_sink: MockSink,
    mock_enricher: MockEnricher,
    mock_redactor: MockRedactor,
    mock_processor: MockProcessor,
    mock_filter: MockFilter,
) -> None:
    """assert_valid_* helpers should raise on invalid plugins."""

    class InvalidSink:
        async def start(self) -> None:
            pass

    class InvalidFilter:
        name = "bad"

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

        # Missing required filter() method

    assert_valid_sink(mock_sink)
    assert_valid_enricher(mock_enricher)
    assert_valid_redactor(mock_redactor)
    assert_valid_processor(mock_processor)
    assert_valid_filter(mock_filter)

    with pytest.raises(ProtocolViolationError):
        assert_valid_sink(InvalidSink())

    with pytest.raises(ProtocolViolationError):
        assert_valid_filter(InvalidFilter())  # Missing required filter method
