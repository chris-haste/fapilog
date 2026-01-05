"""
Testing utilities for fapilog plugins.

This module provides mocks, fixtures, and validators for testing
custom plugins.

Example:
    from fapilog.testing import MockSink, validate_sink

    def test_my_sink():
        sink = MockSink()
        result = validate_sink(sink)
        assert result.valid
"""

from .benchmarks import (
    BenchmarkResult,
    benchmark_async,
    benchmark_enricher,
    benchmark_filter,
    benchmark_sink,
)
from .factories import (
    create_batch_events,
    create_log_event,
    create_sensitive_event,
    generate_correlation_id,
)
from .fixtures import (
    assert_valid_enricher,
    assert_valid_filter,
    assert_valid_processor,
    assert_valid_redactor,
    assert_valid_sink,
    mock_enricher,
    mock_filter,
    mock_processor,
    mock_redactor,
    mock_sink,
    started_mock_sink,
)
from .mocks import (
    MockEnricher,
    MockEnricherConfig,
    MockFilter,
    MockFilterConfig,
    MockProcessor,
    MockRedactor,
    MockRedactorConfig,
    MockSink,
    MockSinkConfig,
)
from .validators import (
    ProtocolViolationError,
    ValidationResult,
    validate_enricher,
    validate_filter,
    validate_plugin_lifecycle,
    validate_processor,
    validate_redactor,
    validate_sink,
)

__all__ = [
    # Mocks
    "MockSink",
    "MockSinkConfig",
    "MockEnricher",
    "MockEnricherConfig",
    "MockRedactor",
    "MockRedactorConfig",
    "MockProcessor",
    "MockFilter",
    "MockFilterConfig",
    # Fixtures
    "mock_sink",
    "mock_enricher",
    "mock_redactor",
    "mock_processor",
    "mock_filter",
    "started_mock_sink",
    # Validators
    "validate_sink",
    "validate_enricher",
    "validate_redactor",
    "validate_filter",
    "validate_processor",
    "validate_plugin_lifecycle",
    "ValidationResult",
    "ProtocolViolationError",
    "assert_valid_sink",
    "assert_valid_enricher",
    "assert_valid_redactor",
    "assert_valid_filter",
    "assert_valid_processor",
    # Benchmarks
    "BenchmarkResult",
    "benchmark_async",
    "benchmark_sink",
    "benchmark_enricher",
    "benchmark_filter",
    # Factories
    "create_log_event",
    "create_batch_events",
    "create_sensitive_event",
    "generate_correlation_id",
]
