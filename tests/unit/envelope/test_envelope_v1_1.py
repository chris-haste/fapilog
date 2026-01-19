"""Tests for canonical log schema v1.1.

Story 1.26: Validates that build_envelope() produces the v1.1 schema
with semantic field groupings (context, diagnostics, data).
"""

from __future__ import annotations

import re

from fapilog.core.envelope import build_envelope

RFC3339_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class TestBuildEnvelopeProducesV11Schema:
    """Tests that build_envelope() produces the canonical v1.1 schema structure."""

    def test_envelope_has_all_required_top_level_fields(self) -> None:
        """Envelope must contain timestamp, level, message, logger, context, diagnostics, data."""
        envelope = build_envelope(level="INFO", message="Test message")

        assert "timestamp" in envelope
        assert "level" in envelope
        assert "message" in envelope
        assert "logger" in envelope
        assert "context" in envelope
        assert "diagnostics" in envelope
        assert "data" in envelope

    def test_timestamp_is_rfc3339_utc_string(self) -> None:
        """Timestamp must be RFC3339 UTC format with Z suffix and millisecond precision."""
        envelope = build_envelope(level="INFO", message="Test")

        assert isinstance(envelope["timestamp"], str)
        assert envelope["timestamp"].endswith("Z")
        assert RFC3339_UTC_PATTERN.match(envelope["timestamp"]), (
            "Timestamp must match RFC3339 format"
        )

    def test_level_is_preserved(self) -> None:
        """Level field should match input."""
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            envelope = build_envelope(level=level, message="Test")
            assert envelope["level"] == level

    def test_message_is_preserved(self) -> None:
        """Message field should match input."""
        envelope = build_envelope(level="INFO", message="Hello, world!")
        assert envelope["message"] == "Hello, world!"

    def test_logger_is_preserved(self) -> None:
        """Logger field should match logger_name input."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            logger_name="myapp.service",
        )
        assert envelope["logger"] == "myapp.service"

    def test_logger_defaults_to_root(self) -> None:
        """Logger should default to 'root' when not specified."""
        envelope = build_envelope(level="INFO", message="Test")
        assert envelope["logger"] == "root"


class TestContextFieldSemantics:
    """Tests for the context field containing request/trace identifiers."""

    def test_context_is_dict(self) -> None:
        """Context must be a dictionary."""
        envelope = build_envelope(level="INFO", message="Test")
        assert isinstance(envelope["context"], dict)

    def test_correlation_id_in_context(self) -> None:
        """correlation_id should be inside context, not top-level."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            correlation_id="corr-123",
        )

        # correlation_id in context
        assert envelope["context"]["correlation_id"] == "corr-123"
        # NOT at top level
        assert "correlation_id" not in envelope

    def test_correlation_id_auto_generated_when_not_provided(self) -> None:
        """correlation_id should be auto-generated UUID when not provided."""
        envelope = build_envelope(level="INFO", message="Test")

        corr_id = envelope["context"]["correlation_id"]
        assert isinstance(corr_id, str), "correlation_id must be a string"
        # UUID format check (8-4-4-4-12)
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            corr_id,
        )

    def test_trace_context_fields_from_bound_context(self) -> None:
        """Trace context fields should be routed from bound_context to context."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            bound_context={
                "request_id": "req-123",
                "user_id": "user-456",
                "tenant_id": "tenant-789",
                "trace_id": "trace-abc",
                "span_id": "span-def",
            },
        )

        context = envelope["context"]
        assert context["request_id"] == "req-123"
        assert context["user_id"] == "user-456"
        assert context["tenant_id"] == "tenant-789"
        assert context["trace_id"] == "trace-abc"
        assert context["span_id"] == "span-def"


class TestDiagnosticsFieldSemantics:
    """Tests for the diagnostics field containing runtime/operational context."""

    def test_diagnostics_is_dict(self) -> None:
        """Diagnostics must be a dictionary."""
        envelope = build_envelope(level="INFO", message="Test")
        assert isinstance(envelope["diagnostics"], dict)

    def test_exception_data_in_diagnostics(self) -> None:
        """Exception data should be nested under diagnostics.exception."""
        try:
            raise ValueError("test error")
        except ValueError:
            envelope = build_envelope(
                level="ERROR",
                message="Caught error",
                exc_info=True,
            )

        assert "exception" in envelope["diagnostics"]
        exc_data = envelope["diagnostics"]["exception"]
        assert exc_data["error.type"] == "ValueError"
        assert exc_data["error.message"] == "test error"

    def test_exception_not_present_when_no_error(self) -> None:
        """diagnostics.exception should not be present when no exception."""
        envelope = build_envelope(level="INFO", message="Test")

        # exception key should not exist at all
        assert "exception" not in envelope["diagnostics"]


class TestDataFieldSemantics:
    """Tests for the data field containing user-provided structured data."""

    def test_data_is_dict(self) -> None:
        """Data must be a dictionary."""
        envelope = build_envelope(level="INFO", message="Test")
        assert isinstance(envelope["data"], dict)

    def test_extra_fields_in_data(self) -> None:
        """Extra fields from extra param should go into data."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            extra={"user_action": "login", "duration_ms": 150},
        )

        assert envelope["data"]["user_action"] == "login"
        assert envelope["data"]["duration_ms"] == 150

    def test_non_context_bound_fields_in_data(self) -> None:
        """Non-context fields from bound_context should go into data."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            bound_context={
                "request_id": "req-123",  # goes to context
                "custom_field": "custom_value",  # goes to data
                "another_field": 42,  # goes to data
            },
        )

        # request_id should be in context, not data
        assert "request_id" in envelope["context"]
        assert "request_id" not in envelope["data"]

        # custom fields should be in data
        assert envelope["data"]["custom_field"] == "custom_value"
        assert envelope["data"]["another_field"] == 42

    def test_extra_overrides_bound_context_in_data(self) -> None:
        """Extra params should override bound_context for non-context data fields."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            bound_context={"custom_key": "from_bound"},
            extra={"custom_key": "from_extra"},
        )

        assert envelope["data"]["custom_key"] == "from_extra"

    def test_metadata_field_removed(self) -> None:
        """The old 'metadata' field should not exist in v1.1 schema."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            extra={"some": "data"},
        )

        assert "metadata" not in envelope


class TestBackwardIncompatibleChanges:
    """Tests verifying that v1.0 patterns are removed."""

    def test_no_top_level_correlation_id(self) -> None:
        """correlation_id must NOT be at top level (v1.0 pattern)."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            correlation_id="corr-123",
        )

        assert "correlation_id" not in envelope

    def test_no_metadata_field(self) -> None:
        """metadata field must NOT exist (v1.0 pattern)."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            extra={"key": "value"},
            bound_context={"ctx_key": "ctx_value"},
        )

        assert "metadata" not in envelope

    def test_timestamp_is_string_not_float(self) -> None:
        """timestamp must be RFC3339 string, not float seconds (v1.0 pattern)."""
        envelope = build_envelope(level="INFO", message="Test")

        assert isinstance(envelope["timestamp"], str)
        assert not isinstance(envelope["timestamp"], float)
