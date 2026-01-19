"""
Tests for the strict_serialization fixture.

The strict_serialization fixture fails if the fallback serialization path
is triggered, catching schema drift between build_envelope() and serialize_envelope().
"""

from __future__ import annotations

import json

import pytest

from fapilog.core.envelope import build_envelope
from fapilog.core.serialization import serialize_envelope

pytestmark = pytest.mark.contract


class TestStrictSerializationFixture:
    """Tests verifying the strict_serialization fixture behavior."""

    def test_normal_serialization_works_with_strict_fixture(
        self, strict_serialization: None
    ) -> None:
        """Normal envelope serialization should work with strict mode enabled.

        This test verifies that the happy path (build_envelope -> serialize_envelope)
        works without triggering the fallback path.
        """
        envelope = build_envelope(level="INFO", message="test message")
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["schema_version"] == "1.1"
        assert parsed["log"]["level"] == "INFO"

    def test_all_log_levels_work_with_strict_fixture(
        self, strict_serialization: None
    ) -> None:
        """All log levels should serialize without triggering fallback."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in levels:
            envelope = build_envelope(level=level, message=f"test {level}")
            view = serialize_envelope(envelope)
            parsed = json.loads(view.data)
            assert parsed["log"]["level"] == level

    def test_envelope_with_context_works_with_strict_fixture(
        self, strict_serialization: None
    ) -> None:
        """Envelope with context should serialize without triggering fallback."""
        envelope = build_envelope(
            level="INFO",
            message="test with context",
            bound_context={
                "request_id": "req-123",
                "user_id": "user-456",
            },
            correlation_id="corr-xyz",
        )
        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["log"]["context"]["request_id"] == "req-123"
        assert parsed["log"]["context"]["correlation_id"] == "corr-xyz"

    def test_envelope_with_exception_works_with_strict_fixture(
        self, strict_serialization: None
    ) -> None:
        """Envelope with exception should serialize without triggering fallback."""
        try:
            raise ValueError("test error")
        except ValueError:
            envelope = build_envelope(
                level="ERROR",
                message="error occurred",
                exc_info=True,
            )

        view = serialize_envelope(envelope)
        parsed = json.loads(view.data)

        assert parsed["log"]["level"] == "ERROR"
        assert "exception" in parsed["log"]["diagnostics"]
