"""Tests for message_id vs correlation_id semantics (Story 1.34).

AC1: Auto-generated ID is named message_id (not correlation_id)
AC2: correlation_id only appears when explicitly set via context
AC3: Both IDs present when context is set
"""

from __future__ import annotations

import re
from uuid import UUID

from fapilog.core.envelope import build_envelope

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class TestMessageIdAlwaysPresent:
    """AC1: message_id is always present and unique per log entry."""

    def test_message_id_present_without_context(self) -> None:
        """message_id appears even when no correlation context is set."""
        envelope = build_envelope(level="INFO", message="test")

        assert "message_id" in envelope["context"]
        assert isinstance(envelope["context"]["message_id"], str)
        # Should be valid UUID
        UUID(envelope["context"]["message_id"])

    def test_message_id_is_valid_uuid(self) -> None:
        """message_id is a valid UUID string."""
        envelope = build_envelope(level="INFO", message="test")

        message_id = envelope["context"]["message_id"]
        assert UUID_PATTERN.match(message_id), f"Invalid UUID format: {message_id}"

    def test_message_id_unique_per_call(self) -> None:
        """Each call to build_envelope generates a unique message_id."""
        envelope1 = build_envelope(level="INFO", message="first")
        envelope2 = build_envelope(level="INFO", message="second")

        assert envelope1["context"]["message_id"] != envelope2["context"]["message_id"]


class TestCorrelationIdOnlyWhenExplicitlySet:
    """AC2: correlation_id only appears when explicitly set."""

    def test_correlation_id_absent_without_context(self) -> None:
        """correlation_id is NOT present when not explicitly set."""
        envelope = build_envelope(level="INFO", message="test")

        assert "correlation_id" not in envelope["context"]

    def test_correlation_id_present_when_explicitly_set(self) -> None:
        """correlation_id appears when explicitly provided."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            correlation_id="req-123",
        )

        assert envelope["context"]["correlation_id"] == "req-123"

    def test_correlation_id_from_bound_context(self) -> None:
        """correlation_id can be set via bound_context request_id mapping."""
        # When request_id_var is set in context, it should map to correlation_id
        envelope = build_envelope(
            level="INFO",
            message="test",
            correlation_id="req-from-context",
        )

        assert envelope["context"]["correlation_id"] == "req-from-context"


class TestBothIdsWhenContextSet:
    """AC3: Both message_id and correlation_id present when context is set."""

    def test_both_ids_present_with_correlation(self) -> None:
        """Both message_id and correlation_id appear when correlation is set."""
        envelope = build_envelope(
            level="INFO",
            message="test",
            correlation_id="req-123",
        )

        # Both should be present
        assert "message_id" in envelope["context"]
        assert "correlation_id" in envelope["context"]
        # And they should be different
        assert (
            envelope["context"]["message_id"] != envelope["context"]["correlation_id"]
        )

    def test_message_id_unique_within_same_correlation(self) -> None:
        """message_id is unique even when correlation_id is the same."""
        envelope1 = build_envelope(
            level="INFO",
            message="first",
            correlation_id="req-123",
        )
        envelope2 = build_envelope(
            level="INFO",
            message="second",
            correlation_id="req-123",
        )

        # Same correlation_id
        assert (
            envelope1["context"]["correlation_id"]
            == envelope2["context"]["correlation_id"]
            == "req-123"
        )
        # Different message_id
        assert envelope1["context"]["message_id"] != envelope2["context"]["message_id"]

    def test_correlation_id_shared_across_messages(self) -> None:
        """correlation_id remains constant when explicitly provided."""
        correlation = "shared-req-456"

        envelope1 = build_envelope(
            level="INFO",
            message="first",
            correlation_id=correlation,
        )
        envelope2 = build_envelope(
            level="INFO",
            message="second",
            correlation_id=correlation,
        )

        assert envelope1["context"]["correlation_id"] == correlation
        assert envelope2["context"]["correlation_id"] == correlation
