"""
JSON Schema validation tests for pipeline output.

These tests validate that serialized log envelopes conform to the published
JSON schema (schemas/log_envelope_v1.json). If these tests fail, the
pipeline output has drifted from the documented schema.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate as jsonschema_validate

from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope

pytestmark = pytest.mark.contract

SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "log_envelope_v1.json"


@pytest.fixture
def envelope_schema() -> dict:
    """Load the canonical JSON schema for log envelopes."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


class TestSchemaValidation:
    """Tests validating pipeline output against the published JSON schema."""

    def test_serialized_output_validates_against_schema(
        self, envelope_schema: dict
    ) -> None:
        """Serialized envelope must conform to published JSON schema."""
        envelope = build_envelope(level="INFO", message="test message")
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        # Should not raise ValidationError
        jsonschema_validate(parsed, envelope_schema)

    def test_all_log_levels_validate_against_schema(
        self, envelope_schema: dict
    ) -> None:
        """All log levels must produce schema-valid output."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in levels:
            envelope = build_envelope(level=level, message=f"test {level}")
            view = serialize_envelope(envelope)
            parsed = json.loads(view.data)

            # Should not raise ValidationError
            jsonschema_validate(parsed, envelope_schema)

    def test_envelope_with_extra_data_validates(self, envelope_schema: dict) -> None:
        """Envelope with user data must conform to schema."""
        envelope = build_envelope(
            level="INFO",
            message="test with data",
            extra={"user_id": "u-123", "action": "login", "duration_ms": 150},
        )
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        jsonschema_validate(parsed, envelope_schema)

    def test_envelope_with_context_validates(self, envelope_schema: dict) -> None:
        """Envelope with context fields must conform to schema."""
        envelope = build_envelope(
            level="INFO",
            message="test with context",
            bound_context={
                "request_id": "req-123",
                "user_id": "user-456",
                "tenant_id": "tenant-789",
            },
        )
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        jsonschema_validate(parsed, envelope_schema)
        # Also verify context fields are in the right place
        log = parsed["log"]
        assert log["context"]["request_id"] == "req-123"
        assert log["context"]["user_id"] == "user-456"

    def test_envelope_with_exception_validates(self, envelope_schema: dict) -> None:
        """Envelope with exception info must conform to schema."""
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

        jsonschema_validate(parsed, envelope_schema)
        # Verify exception is in diagnostics
        log = parsed["log"]
        assert "exception" in log["diagnostics"]

    def test_schema_version_is_correct(self, envelope_schema: dict) -> None:
        """Schema version in output must match v1.1."""
        envelope = build_envelope(level="INFO", message="test")
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["schema_version"] == "1.1"
        jsonschema_validate(parsed, envelope_schema)

    def test_timestamp_format_is_rfc3339(self, envelope_schema: dict) -> None:
        """Timestamp must be RFC3339 UTC with Z suffix."""
        envelope = build_envelope(level="INFO", message="test")
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        timestamp = parsed["log"]["timestamp"]
        # RFC3339 UTC format: YYYY-MM-DDTHH:MM:SS.mmmZ
        assert timestamp.endswith("Z")
        assert "T" in timestamp
        jsonschema_validate(parsed, envelope_schema)

    def test_required_fields_present(self, envelope_schema: dict) -> None:
        """All required fields must be present in output."""
        envelope = build_envelope(level="INFO", message="test")
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        # Top-level required fields
        assert "schema_version" in parsed
        assert "log" in parsed

        # Log-level required fields
        log = parsed["log"]
        assert "timestamp" in log
        assert "level" in log
        assert "message" in log
        assert "context" in log
        assert "diagnostics" in log
        assert "data" in log

        jsonschema_validate(parsed, envelope_schema)
