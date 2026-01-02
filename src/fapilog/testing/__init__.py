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

from .factories import (
    create_batch_events,
    create_log_event,
    create_sensitive_event,
    generate_correlation_id,
)
from .mocks import (
    MockEnricher,
    MockEnricherConfig,
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
    # Validators
    "validate_sink",
    "validate_enricher",
    "validate_redactor",
    "validate_processor",
    "validate_plugin_lifecycle",
    "ValidationResult",
    "ProtocolViolationError",
    # Factories
    "create_log_event",
    "create_batch_events",
    "create_sensitive_event",
    "generate_correlation_id",
]
