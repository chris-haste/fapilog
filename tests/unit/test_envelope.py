"""Unit tests for envelope building module.

Tests for the v1.1 canonical schema with semantic field groupings:
- context: Request/trace identifiers
- diagnostics: Runtime/operational data
- data: User-provided structured data
"""

from __future__ import annotations

import re

from fapilog.core.envelope import build_envelope

RFC3339_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class TestBuildEnvelopeBasic:
    """Test basic envelope construction."""

    def test_returns_dict_with_required_fields(self) -> None:
        """Envelope contains all v1.1 required fields."""
        envelope = build_envelope(level="INFO", message="test message")

        assert isinstance(envelope, dict)
        assert "timestamp" in envelope
        assert envelope["level"] == "INFO"
        assert envelope["message"] == "test message"
        assert envelope["logger"] == "root"
        assert "context" in envelope
        assert "diagnostics" in envelope
        assert "data" in envelope

    def test_custom_logger_name(self) -> None:
        """Custom logger name is used when provided."""
        envelope = build_envelope(
            level="DEBUG",
            message="debug msg",
            logger_name="myapp.module",
        )

        assert envelope["logger"] == "myapp.module"

    def test_timestamp_is_rfc3339_string(self) -> None:
        """Timestamp is RFC3339 UTC string with Z suffix (v1.1 schema)."""
        envelope = build_envelope(level="INFO", message="test")

        assert isinstance(envelope["timestamp"], str)
        assert envelope["timestamp"].endswith("Z")
        assert RFC3339_UTC_PATTERN.match(envelope["timestamp"]), (
            "Timestamp must match RFC3339 format"
        )


class TestBuildEnvelopeDataField:
    """Test data field handling in envelope (replaces metadata in v1.1)."""

    def test_extra_fields_in_data(self) -> None:
        """Extra fields are placed in nested data dict (non-context fields)."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"custom_key": "123", "action": "login"},
        )

        assert "data" in envelope
        assert envelope["data"]["custom_key"] == "123"
        assert envelope["data"]["action"] == "login"

    def test_non_context_bound_fields_in_data(self) -> None:
        """Non-context bound fields are placed in nested data dict."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"custom_field": "req-456", "tenant": "acme"},
        )

        assert "data" in envelope
        assert envelope["data"]["custom_field"] == "req-456"
        assert envelope["data"]["tenant"] == "acme"

    def test_extra_overrides_bound_context(self) -> None:
        """Extra fields take precedence over bound context in data."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"key": "from_context"},
            extra={"key": "from_extra"},
        )

        assert envelope["data"]["key"] == "from_extra"

    def test_empty_data_when_no_extra_or_context(self) -> None:
        """Empty data dict when extra and context are both empty."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra=None,
            bound_context=None,
        )

        # Core fields present with empty data
        assert set(envelope.keys()) == {
            "timestamp",
            "level",
            "message",
            "logger",
            "context",
            "diagnostics",
            "data",
        }
        assert envelope["data"] == {}


class TestBuildEnvelopeExceptions:
    """Test exception serialization in envelope."""

    def test_exception_serialized_in_diagnostics(self) -> None:
        """Exception is serialized into diagnostics.exception when enabled."""
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        envelope = build_envelope(
            level="ERROR",
            message="failed",
            exc_info=exc_info,
            exceptions_enabled=True,
        )

        assert "diagnostics" in envelope
        assert "exception" in envelope["diagnostics"]
        exc_data = envelope["diagnostics"]["exception"]
        assert exc_data["error.type"] == "ValueError"
        assert "test error" in exc_data["error.message"]
        assert "error.stack" in exc_data

    def test_exception_not_serialized_when_disabled(self) -> None:
        """Exception is not serialized when exceptions_enabled=False."""
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        envelope = build_envelope(
            level="ERROR",
            message="failed",
            exc_info=exc_info,
            exceptions_enabled=False,
        )

        # Empty diagnostics since exception serialization is disabled
        assert "exception" not in envelope["diagnostics"]
        assert envelope["diagnostics"] == {}

    def test_exception_from_exc_parameter(self) -> None:
        """Exception can be provided via exc parameter."""
        exc = RuntimeError("direct exception")

        envelope = build_envelope(
            level="ERROR",
            message="failed",
            exc=exc,
            exceptions_enabled=True,
        )

        exc_data = envelope["diagnostics"]["exception"]
        assert exc_data["error.type"] == "RuntimeError"
        assert "direct exception" in exc_data["error.message"]

    def test_exc_info_true_captures_current(self) -> None:
        """exc_info=True captures the current exception."""
        try:
            raise TypeError("in handler")
        except TypeError:
            envelope = build_envelope(
                level="ERROR",
                message="caught",
                exc_info=True,
                exceptions_enabled=True,
            )

        exc_data = envelope["diagnostics"]["exception"]
        assert exc_data["error.type"] == "TypeError"
        assert "in handler" in exc_data["error.message"]

    def test_no_exception_when_none_provided(self) -> None:
        """No exception fields when no exception provided."""
        envelope = build_envelope(
            level="INFO",
            message="normal",
            exceptions_enabled=True,
        )

        # Empty diagnostics when no exception
        assert "exception" not in envelope["diagnostics"]
        assert envelope["diagnostics"] == {}

    def test_exception_max_frames_respected(self) -> None:
        """Exception serialization respects max_frames limit."""

        def deep_call(n: int) -> None:
            if n <= 0:
                raise RecursionError("deep")
            deep_call(n - 1)

        try:
            deep_call(10)
        except RecursionError:
            import sys

            exc_info = sys.exc_info()

        envelope = build_envelope(
            level="ERROR",
            message="deep error",
            exc_info=exc_info,
            exceptions_enabled=True,
            exceptions_max_frames=3,
        )

        exc_data = envelope["diagnostics"]["exception"]
        assert "error.frames" in exc_data
        assert len(exc_data["error.frames"]) <= 3


class TestBuildEnvelopeCorrelation:
    """Test correlation ID handling in envelope."""

    def test_correlation_id_in_context(self) -> None:
        """Correlation ID is in context when provided."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            correlation_id="corr-789",
        )

        assert envelope["context"]["correlation_id"] == "corr-789"

    def test_correlation_id_generated_when_missing(self) -> None:
        """Correlation ID is auto-generated when not provided."""
        envelope = build_envelope(
            level="INFO",
            message="test",
        )

        corr_id = envelope["context"]["correlation_id"]
        assert isinstance(corr_id, str), "correlation_id must be a string"
        # Should be a valid UUID string
        assert len(corr_id) == 36
        assert corr_id.count("-") == 4


class TestBuildEnvelopeContextRouting:
    """Test that context fields from bound_context are routed correctly."""

    def test_trace_fields_routed_to_context(self) -> None:
        """Trace context fields go to context dict, not data."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={
                "request_id": "req-123",
                "user_id": "user-456",
                "tenant_id": "tenant-789",
                "trace_id": "trace-abc",
                "span_id": "span-def",
                "custom_field": "should_go_to_data",
            },
        )

        # Trace fields in context
        assert envelope["context"]["request_id"] == "req-123"
        assert envelope["context"]["user_id"] == "user-456"
        assert envelope["context"]["tenant_id"] == "tenant-789"
        assert envelope["context"]["trace_id"] == "trace-abc"
        assert envelope["context"]["span_id"] == "span-def"

        # Custom field in data, not context
        assert "custom_field" not in envelope["context"]
        assert envelope["data"]["custom_field"] == "should_go_to_data"
