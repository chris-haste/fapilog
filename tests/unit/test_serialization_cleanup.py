"""
Tests for serialize_envelope() cleanup (Story 1.28).

After Stories 1.26 and 1.27, the pipeline produces log events in the v1.1
canonical schema from build_envelope() + enrichers. serialize_envelope()
now trusts this input and only fails for truly unserializable data.

Key behaviors verified:
1. Accepts v1.1 schema output from build_envelope() without exception
2. Provides defaults for missing context/diagnostics (backwards compatibility)
3. Rejects non-serializable data (actual error case)
4. Includes data field in output
"""

from __future__ import annotations

import json

import pytest

from fapilog.core.envelope import build_envelope
from fapilog.core.errors import FapilogError
from fapilog.core.serialization import serialize_envelope


class NonSerializable:
    """Object that cannot be JSON serialized."""

    pass


class TestSerializeEnvelopeAcceptsV11Schema:
    """AC1: serialize_envelope() accepts v1.1 schema from build_envelope()."""

    def test_serialize_envelope_accepts_build_envelope_output(self) -> None:
        """Direct output from build_envelope() serializes without exception."""
        envelope = build_envelope(level="INFO", message="test message")

        view = serialize_envelope(envelope)

        parsed = json.loads(view.data)
        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["level"] == "INFO"
        assert parsed["log"]["message"] == "test message"
        assert isinstance(parsed["log"]["context"], dict)
        assert isinstance(parsed["log"]["diagnostics"], dict)
        assert isinstance(parsed["log"]["data"], dict)

    def test_serialize_envelope_preserves_context_fields(self) -> None:
        """Context fields from build_envelope() are preserved."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"request_id": "req-123", "user_id": "user-456"},
        )

        view = serialize_envelope(envelope)

        parsed = json.loads(view.data)
        assert parsed["log"]["context"]["request_id"] == "req-123"
        assert parsed["log"]["context"]["user_id"] == "user-456"

    def test_serialize_envelope_preserves_data_fields(self) -> None:
        """Data fields from build_envelope() are preserved."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            extra={"custom_field": "value", "count": 42},
        )

        view = serialize_envelope(envelope)

        parsed = json.loads(view.data)
        # Non-context fields go to data
        assert parsed["log"]["data"]["custom_field"] == "value"
        assert parsed["log"]["data"]["count"] == 42

    def test_serialize_envelope_preserves_diagnostics(self) -> None:
        """Diagnostics from build_envelope() (e.g., exception info) are preserved."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            envelope = build_envelope(level="ERROR", message="error occurred", exc=e)

        view = serialize_envelope(envelope)

        parsed = json.loads(view.data)
        assert "exception" in parsed["log"]["diagnostics"]


class TestSerializeEnvelopeBackwardsCompatibility:
    """serialize_envelope() provides defaults for missing optional fields."""

    def test_serialize_envelope_defaults_missing_context(self) -> None:
        """Missing context field defaults to empty dict."""
        log = {
            "timestamp": 1723734312.123,
            "level": "INFO",
            "message": "test",
            # No context field
            "diagnostics": {},
        }

        view = serialize_envelope(log)

        parsed = json.loads(view.data)
        assert parsed["log"]["context"] == {}

    def test_serialize_envelope_defaults_missing_diagnostics(self) -> None:
        """Missing diagnostics field defaults to empty dict."""
        log = {
            "timestamp": 1723734312.123,
            "level": "INFO",
            "message": "test",
            "context": {},
            # No diagnostics field
        }

        view = serialize_envelope(log)

        parsed = json.loads(view.data)
        assert parsed["log"]["diagnostics"] == {}

    def test_serialize_envelope_defaults_missing_data(self) -> None:
        """Missing data field defaults to empty dict."""
        log = {
            "timestamp": 1723734312.123,
            "level": "INFO",
            "message": "test",
            "context": {},
            "diagnostics": {},
            # No data field
        }

        view = serialize_envelope(log)

        parsed = json.loads(view.data)
        assert parsed["log"]["data"] == {}


class TestSerializeEnvelopeRejectsUnserializable:
    """AC: serialize_envelope() rejects non-serializable data."""

    def test_serialize_envelope_raises_for_non_serializable_in_data(self) -> None:
        """Non-serializable object in data field raises FapilogError."""
        log = {
            "timestamp": 1723734312.123,
            "level": "INFO",
            "message": "test",
            "context": {},
            "diagnostics": {},
            "data": {"bad": NonSerializable()},
        }

        with pytest.raises(FapilogError, match="Serialization failed"):
            serialize_envelope(log)

    def test_serialize_envelope_raises_for_non_serializable_in_context(self) -> None:
        """Non-serializable object in context field raises FapilogError."""
        log = {
            "timestamp": 1723734312.123,
            "level": "INFO",
            "message": "test",
            "context": {"bad": NonSerializable()},
            "diagnostics": {},
        }

        with pytest.raises(FapilogError, match="Serialization failed"):
            serialize_envelope(log)


class TestSerializeEnvelopeRequiredFields:
    """serialize_envelope() still requires core fields."""

    def test_serialize_envelope_requires_timestamp(self) -> None:
        """Missing timestamp raises ValueError."""
        log = {"level": "INFO", "message": "test"}

        with pytest.raises(ValueError, match="missing required fields"):
            serialize_envelope(log)

    def test_serialize_envelope_requires_level(self) -> None:
        """Missing level raises ValueError."""
        log = {"timestamp": 1723734312.123, "message": "test"}

        with pytest.raises(ValueError, match="missing required fields"):
            serialize_envelope(log)

    def test_serialize_envelope_requires_message(self) -> None:
        """Missing message raises ValueError."""
        log = {"timestamp": 1723734312.123, "level": "INFO"}

        with pytest.raises(ValueError, match="missing required fields"):
            serialize_envelope(log)
