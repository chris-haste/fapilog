"""Unit tests for envelope building module."""

from __future__ import annotations

from fapilog.core.envelope import build_envelope


class TestBuildEnvelopeBasic:
    """Test basic envelope construction."""

    def test_returns_dict_with_required_fields(self) -> None:
        """Envelope contains timestamp, level, message, logger, and correlation_id."""
        envelope = build_envelope(level="INFO", message="test message")

        assert isinstance(envelope, dict)
        assert "timestamp" in envelope
        assert envelope["level"] == "INFO"
        assert envelope["message"] == "test message"
        assert envelope["logger"] == "root"
        assert "correlation_id" in envelope

    def test_custom_logger_name(self) -> None:
        """Custom logger name is used when provided."""
        envelope = build_envelope(
            level="DEBUG",
            message="debug msg",
            logger_name="myapp.module",
        )

        assert envelope["logger"] == "myapp.module"

    def test_timestamp_is_posix_float(self) -> None:
        """Timestamp is a POSIX float (matches LogEvent.to_mapping())."""
        envelope = build_envelope(level="INFO", message="test")

        assert isinstance(envelope["timestamp"], float)
        # Should be a reasonable recent timestamp (after year 2020)
        assert envelope["timestamp"] > 1577836800  # 2020-01-01


class TestBuildEnvelopeMetadata:
    """Test metadata merging in envelope."""

    def test_extra_fields_in_metadata(self) -> None:
        """Extra fields are placed in nested metadata dict."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"user_id": "123", "action": "login"},
        )

        assert "metadata" in envelope
        assert envelope["metadata"]["user_id"] == "123"
        assert envelope["metadata"]["action"] == "login"

    def test_bound_context_in_metadata(self) -> None:
        """Bound context fields are placed in nested metadata dict."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"request_id": "req-456", "tenant": "acme"},
        )

        assert "metadata" in envelope
        assert envelope["metadata"]["request_id"] == "req-456"
        assert envelope["metadata"]["tenant"] == "acme"

    def test_extra_overrides_bound_context(self) -> None:
        """Extra fields take precedence over bound context in metadata."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            bound_context={"user_id": "from_context"},
            extra={"user_id": "from_extra"},
        )

        assert envelope["metadata"]["user_id"] == "from_extra"

    def test_empty_metadata_when_no_extra_or_context(self) -> None:
        """Empty metadata dict when extra and context are both empty."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra=None,
            bound_context=None,
        )

        # Core fields present with empty metadata
        assert set(envelope.keys()) == {
            "timestamp",
            "level",
            "message",
            "logger",
            "correlation_id",
            "metadata",
        }
        assert envelope["metadata"] == {}


class TestBuildEnvelopeExceptions:
    """Test exception serialization in envelope."""

    def test_exception_serialized_when_enabled(self) -> None:
        """Exception is serialized into metadata when exceptions_enabled=True."""
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

        assert "metadata" in envelope
        assert "error.type" in envelope["metadata"]
        assert envelope["metadata"]["error.type"] == "ValueError"
        assert "error.message" in envelope["metadata"]
        assert "test error" in envelope["metadata"]["error.message"]
        assert "error.stack" in envelope["metadata"]

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

        # Empty metadata since exception serialization is disabled
        assert "error.type" not in envelope.get("metadata", {})
        assert envelope["metadata"] == {}

    def test_exception_from_exc_parameter(self) -> None:
        """Exception can be provided via exc parameter."""
        exc = RuntimeError("direct exception")

        envelope = build_envelope(
            level="ERROR",
            message="failed",
            exc=exc,
            exceptions_enabled=True,
        )

        assert envelope["metadata"]["error.type"] == "RuntimeError"
        assert "direct exception" in envelope["metadata"]["error.message"]

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

        assert envelope["metadata"]["error.type"] == "TypeError"
        assert "in handler" in envelope["metadata"]["error.message"]

    def test_no_exception_when_none_provided(self) -> None:
        """No exception fields when no exception provided."""
        envelope = build_envelope(
            level="INFO",
            message="normal",
            exceptions_enabled=True,
        )

        # Empty metadata when no exception and no extra
        assert envelope["metadata"] == {}

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

        assert "error.frames" in envelope["metadata"]
        assert len(envelope["metadata"]["error.frames"]) <= 3


class TestBuildEnvelopeCorrelation:
    """Test correlation ID handling in envelope."""

    def test_correlation_id_included(self) -> None:
        """Correlation ID is included when provided."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            correlation_id="corr-789",
        )

        assert envelope["correlation_id"] == "corr-789"

    def test_correlation_id_generated_when_missing(self) -> None:
        """Correlation ID is auto-generated when not provided."""
        envelope = build_envelope(
            level="INFO",
            message="test",
        )

        assert "correlation_id" in envelope
        # Should be a valid UUID string
        assert len(envelope["correlation_id"]) == 36
        assert envelope["correlation_id"].count("-") == 4
