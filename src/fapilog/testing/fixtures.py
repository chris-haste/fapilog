"""
Pytest fixtures and assertion helpers for plugin testing.

These fixtures provide ready-to-use mock plugins and helpers to validate
custom implementations in tests.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from .mocks import (
    MockEnricher,
    MockFilter,
    MockProcessor,
    MockRedactor,
    MockSink,
)
from .validators import (
    ValidationResult,
    validate_enricher,
    validate_filter,
    validate_processor,
    validate_redactor,
    validate_sink,
)


@pytest.fixture
def mock_sink() -> MockSink:
    """Provide a fresh MockSink for testing sinks."""
    return MockSink()


@pytest.fixture
def mock_enricher() -> MockEnricher:
    """Provide a fresh MockEnricher for testing enrichers."""
    return MockEnricher()


@pytest.fixture
def mock_redactor() -> MockRedactor:
    """Provide a fresh MockRedactor for testing redactors."""
    return MockRedactor()


@pytest.fixture
def mock_processor() -> MockProcessor:
    """Provide a fresh MockProcessor for testing processors."""
    return MockProcessor()


@pytest.fixture
def mock_filter() -> MockFilter:
    """Provide a fresh MockFilter for testing filters."""
    return MockFilter()


@pytest.fixture
async def started_mock_sink() -> AsyncIterator[MockSink]:
    """Provide a started MockSink with automatic cleanup."""
    sink = MockSink()
    await sink.start()
    try:
        yield sink
    finally:
        await sink.stop()


def assert_valid_sink(sink: Any) -> ValidationResult:
    """Validate sink and raise ProtocolViolationError on failure."""
    result = validate_sink(sink)
    result.raise_if_invalid()
    return result


def assert_valid_enricher(enricher: Any) -> ValidationResult:
    """Validate enricher and raise ProtocolViolationError on failure."""
    result = validate_enricher(enricher)
    result.raise_if_invalid()
    return result


def assert_valid_redactor(redactor: Any) -> ValidationResult:
    """Validate redactor and raise ProtocolViolationError on failure."""
    result = validate_redactor(redactor)
    result.raise_if_invalid()
    return result


def assert_valid_processor(processor: Any) -> ValidationResult:
    """Validate processor and raise ProtocolViolationError on failure."""
    result = validate_processor(processor)
    result.raise_if_invalid()
    return result


def assert_valid_filter(filter_plugin: Any) -> ValidationResult:
    """Validate filter and raise ProtocolViolationError on failure."""
    result = validate_filter(filter_plugin)
    result.raise_if_invalid()
    return result
