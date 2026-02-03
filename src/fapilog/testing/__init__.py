"""
Testing utilities for fapilog plugins.

This module provides mocks, fixtures, and validators for testing
custom plugins.

Basic utilities (mocks, validators, factories, benchmarks) are always available.
Pytest fixtures require the testing extra: `pip install fapilog[testing]`

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
    # Validators
    "validate_sink",
    "validate_enricher",
    "validate_redactor",
    "validate_filter",
    "validate_processor",
    "validate_plugin_lifecycle",
    "ValidationResult",
    "ProtocolViolationError",
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

# Pytest fixtures require the testing extra
# These are conditionally exported only when pytest is available
try:
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

    __all__ += [
        # Fixtures (require pytest)
        "mock_sink",
        "mock_enricher",
        "mock_redactor",
        "mock_processor",
        "mock_filter",
        "started_mock_sink",
        "assert_valid_sink",
        "assert_valid_enricher",
        "assert_valid_redactor",
        "assert_valid_filter",
        "assert_valid_processor",
    ]
except ImportError:  # pragma: no cover - can't test without pytest
    # pytest not installed - fixtures unavailable
    # Provide helpful error if someone tries to access them
    from typing import Any, Callable

    def _pytest_required(name: str) -> Callable[..., Any]:
        def _raise(*args: Any, **kwargs: Any) -> Any:
            raise ImportError(
                f"'{name}' requires pytest. Install with: pip install fapilog[testing]"
            )

        return _raise

    mock_sink = _pytest_required("mock_sink")  # type: ignore[assignment]
    mock_enricher = _pytest_required("mock_enricher")  # type: ignore[assignment]
    mock_redactor = _pytest_required("mock_redactor")  # type: ignore[assignment]
    mock_processor = _pytest_required("mock_processor")  # type: ignore[assignment]
    mock_filter = _pytest_required("mock_filter")  # type: ignore[assignment]
    started_mock_sink = _pytest_required("started_mock_sink")  # type: ignore[assignment]
    assert_valid_sink = _pytest_required("assert_valid_sink")
    assert_valid_enricher = _pytest_required("assert_valid_enricher")
    assert_valid_redactor = _pytest_required("assert_valid_redactor")
    assert_valid_filter = _pytest_required("assert_valid_filter")
    assert_valid_processor = _pytest_required("assert_valid_processor")
