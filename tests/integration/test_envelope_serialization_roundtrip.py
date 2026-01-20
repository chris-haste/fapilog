"""Integration tests for envelope build and serialization roundtrip.

Story 1.26: Validates that build_envelope() output can be serialized by
serialize_envelope() without exception - the critical fix for the schema
incompatibility between these two functions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope

pytestmark = pytest.mark.integration


class TestBuildSerializeRoundtrip:
    """Tests that build_envelope() output is accepted by serialize_envelope()."""

    def test_basic_envelope_serializes_without_exception(self) -> None:
        """serialize_envelope(build_envelope(...)) must not raise."""
        envelope = build_envelope(level="INFO", message="Test message")
        result = serialize_envelope(envelope)

        # Verify serialization produced valid JSON bytes
        parsed = json.loads(result.data)
        assert "schema_version" in parsed
        assert "log" in parsed

    def test_envelope_with_correlation_id_serializes(self) -> None:
        """Envelope with correlation_id serializes successfully."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            correlation_id="corr-123",
        )
        result = serialize_envelope(envelope)

        parsed = json.loads(result.data)
        assert parsed["log"]["context"]["correlation_id"] == "corr-123"

    def test_envelope_with_extra_data_serializes(self) -> None:
        """Envelope with extra user data serializes successfully."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            extra={"user_action": "login", "duration_ms": 150},
        )
        result = serialize_envelope(envelope)

        parsed = json.loads(result.data)
        assert parsed["log"]["data"]["user_action"] == "login"
        assert parsed["log"]["data"]["duration_ms"] == 150

    def test_envelope_with_exception_serializes(self) -> None:
        """Envelope with exception data serializes successfully."""
        try:
            raise ValueError("test error")
        except ValueError:
            envelope = build_envelope(
                level="ERROR",
                message="Error occurred",
                exc_info=True,
            )
        result = serialize_envelope(envelope)

        parsed = json.loads(result.data)
        assert "exception" in parsed["log"]["diagnostics"]

    def test_envelope_with_bound_context_serializes(self) -> None:
        """Envelope with bound context serializes successfully."""
        envelope = build_envelope(
            level="INFO",
            message="Test",
            bound_context={
                "request_id": "req-123",
                "custom_field": "value",
            },
        )
        result = serialize_envelope(envelope)

        parsed = json.loads(result.data)
        assert parsed["log"]["context"]["request_id"] == "req-123"
        assert parsed["log"]["data"]["custom_field"] == "value"

    def test_serialized_envelope_has_v1_1_schema_version(self) -> None:
        """Serialized envelope should have schema_version 1.1."""
        envelope = build_envelope(level="INFO", message="Test")
        result = serialize_envelope(envelope)

        parsed = json.loads(result.data)
        assert parsed["schema_version"] == "1.1"


class TestJsonSchemaValidation:
    """Tests that serialized envelopes validate against the JSON schema."""

    def test_serialized_envelope_validates_against_json_schema(self) -> None:
        """Serialized envelope should pass JSON schema validation."""
        jsonschema = pytest.importorskip("jsonschema")

        schema_path = Path(__file__).parents[2] / "schemas" / "log_envelope_v1.json"
        schema = json.loads(schema_path.read_text())

        envelope = build_envelope(
            level="INFO",
            message="Test message",
            extra={"key": "value"},
            correlation_id="corr-123",
        )
        result = serialize_envelope(envelope)
        parsed = json.loads(result.data)

        # Should not raise
        jsonschema.validate(parsed, schema)

    def test_envelope_with_all_fields_validates(self) -> None:
        """Envelope with all optional fields should validate."""
        jsonschema = pytest.importorskip("jsonschema")

        schema_path = Path(__file__).parents[2] / "schemas" / "log_envelope_v1.json"
        schema = json.loads(schema_path.read_text())

        try:
            raise ValueError("test")
        except ValueError:
            envelope = build_envelope(
                level="ERROR",
                message="Full test",
                logger_name="myapp.service",
                correlation_id="corr-456",
                extra={"extra_key": "extra_value"},
                bound_context={
                    "request_id": "req-789",
                    "user_id": "user-123",
                    "trace_id": "trace-abc",
                    "span_id": "span-def",
                    "custom": "data",
                },
                exc_info=True,
            )

        result = serialize_envelope(envelope)
        parsed = json.loads(result.data)

        # Should not raise
        jsonschema.validate(parsed, schema)
