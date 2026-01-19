"""
Contract tests ensuring schema compatibility between envelope building and serialization.

These tests verify the producer/consumer contract:
- Producer: build_envelope() creates log envelopes
- Consumer: serialize_envelope() serializes envelopes to JSON

If these tests fail, schemas have drifted apart and need realignment.
"""

from __future__ import annotations

import json

import pytest

from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope

pytestmark = pytest.mark.contract


class TestEnvelopeContract:
    """Contract tests ensuring schema compatibility between pipeline stages."""

    def test_build_envelope_output_is_serializable(self) -> None:
        """build_envelope() output must be valid serialize_envelope() input."""
        envelope = build_envelope(level="INFO", message="test message")

        # This should NOT raise - if it does, schemas have drifted
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        # Verify schema version and structure
        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["level"] == "INFO"
        assert parsed["log"]["message"] == "test message"

    def test_build_envelope_with_all_options_is_serializable(self) -> None:
        """Full-featured envelope must serialize without exception."""
        envelope = build_envelope(
            level="ERROR",
            message="error occurred",
            extra={"user_id": "u-123", "action": "login"},
            correlation_id="corr-abc",
            logger_name="myapp.auth",
            exc_info=False,
        )

        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["level"] == "ERROR"
        assert parsed["log"]["message"] == "error occurred"
        assert parsed["log"]["logger"] == "myapp.auth"

    def test_build_envelope_with_exception_is_serializable(self) -> None:
        """Envelope with exception info must serialize without exception."""
        try:
            raise ValueError("test error")
        except ValueError:
            envelope = build_envelope(
                level="ERROR",
                message="An error occurred",
                exc_info=True,
            )

        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["level"] == "ERROR"
        assert "exception" in parsed["log"]["diagnostics"]

    def test_build_envelope_with_bound_context_is_serializable(self) -> None:
        """Envelope with bound context must serialize without exception."""
        envelope = build_envelope(
            level="INFO",
            message="test with context",
            bound_context={
                "request_id": "req-123",
                "user_id": "user-456",
                "custom_field": "custom_value",
            },
        )

        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["context"]["request_id"] == "req-123"
        assert parsed["log"]["context"]["user_id"] == "user-456"
        assert parsed["log"]["data"]["custom_field"] == "custom_value"

    def test_build_envelope_with_nested_extra_is_serializable(self) -> None:
        """Envelope with nested extra data must serialize without exception."""
        envelope = build_envelope(
            level="INFO",
            message="test with nested data",
            extra={
                "metadata": {
                    "nested": {"deep": {"value": 42}},
                    "list_data": [1, 2, 3],
                },
            },
        )

        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["data"]["metadata"]["nested"]["deep"]["value"] == 42
        assert parsed["log"]["data"]["metadata"]["list_data"] == [1, 2, 3]

    def test_build_envelope_all_log_levels_serializable(self) -> None:
        """All log levels must produce serializable envelopes."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in levels:
            envelope = build_envelope(level=level, message=f"test {level}")
            view = serialize_envelope(envelope)
            parsed = json.loads(view.data)
            assert parsed["schema_version"] == "1.1", f"Failed for level: {level}"
            assert parsed["log"]["level"] == level, f"Wrong level for: {level}"
