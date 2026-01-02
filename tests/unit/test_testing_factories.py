"""
TDD tests for Story 4.27: Plugin Testing Utilities - Factories.

Tests for create_log_event, create_batch_events, create_sensitive_event.
"""

from __future__ import annotations


class TestCreateLogEvent:
    """Tests for create_log_event factory."""

    def test_create_log_event_defaults(self) -> None:
        """create_log_event should create valid event with defaults."""
        from fapilog.testing import create_log_event

        event = create_log_event()

        assert "level" in event
        assert event["level"] == "INFO"
        assert "message" in event
        assert "timestamp" in event
        assert "logger" in event
        assert "correlation_id" in event

    def test_create_log_event_custom_level(self) -> None:
        """create_log_event should accept custom level."""
        from fapilog.testing import create_log_event

        event = create_log_event(level="ERROR")
        assert event["level"] == "ERROR"

    def test_create_log_event_custom_message(self) -> None:
        """create_log_event should accept custom message."""
        from fapilog.testing import create_log_event

        event = create_log_event(message="Custom message")
        assert event["message"] == "Custom message"

    def test_create_log_event_with_metadata(self) -> None:
        """create_log_event should include metadata kwargs."""
        from fapilog.testing import create_log_event

        event = create_log_event(user_id="123", request_id="abc")

        assert event["metadata"]["user_id"] == "123"
        assert event["metadata"]["request_id"] == "abc"

    def test_create_log_event_timestamp_is_iso(self) -> None:
        """create_log_event timestamp should be ISO format."""
        from fapilog.testing import create_log_event

        event = create_log_event()

        # Should be parseable as ISO
        from datetime import datetime

        datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))


class TestCreateBatchEvents:
    """Tests for create_batch_events factory."""

    def test_create_batch_events_count(self) -> None:
        """create_batch_events should create specified number of events."""
        from fapilog.testing import create_batch_events

        events = create_batch_events(5)
        assert len(events) == 5

    def test_create_batch_events_unique_messages(self) -> None:
        """create_batch_events should have unique messages."""
        from fapilog.testing import create_batch_events

        events = create_batch_events(3)
        messages = [e["message"] for e in events]

        assert len(set(messages)) == 3  # All unique

    def test_create_batch_events_shared_level(self) -> None:
        """create_batch_events should apply level to all events."""
        from fapilog.testing import create_batch_events

        events = create_batch_events(3, level="WARNING")

        for event in events:
            assert event["level"] == "WARNING"

    def test_create_batch_events_with_metadata(self) -> None:
        """create_batch_events should include metadata in all events."""
        from fapilog.testing import create_batch_events

        events = create_batch_events(2, service="test")

        for event in events:
            assert event["metadata"]["service"] == "test"


class TestCreateSensitiveEvent:
    """Tests for create_sensitive_event factory."""

    def test_create_sensitive_event_has_user_data(self) -> None:
        """create_sensitive_event should have user section."""
        from fapilog.testing import create_sensitive_event

        event = create_sensitive_event()

        assert "user" in event
        assert "password" in event["user"]
        assert "email" in event["user"]

    def test_create_sensitive_event_has_payment_data(self) -> None:
        """create_sensitive_event should have payment section."""
        from fapilog.testing import create_sensitive_event

        event = create_sensitive_event()

        assert "payment" in event
        assert "card_number" in event["payment"]
        assert "cvv" in event["payment"]

    def test_create_sensitive_event_has_auth_data(self) -> None:
        """create_sensitive_event should have auth section."""
        from fapilog.testing import create_sensitive_event

        event = create_sensitive_event()

        assert "auth" in event
        assert "api_key" in event["auth"]
        assert "token" in event["auth"]

    def test_create_sensitive_event_has_url_with_creds(self) -> None:
        """create_sensitive_event should have URL with credentials."""
        from fapilog.testing import create_sensitive_event

        event = create_sensitive_event()

        assert "url" in event
        assert "user:pass@" in event["url"]


class TestGenerateCorrelationId:
    """Tests for generate_correlation_id factory."""

    def test_generate_correlation_id_format(self) -> None:
        """generate_correlation_id should return hex string."""
        from fapilog.testing import generate_correlation_id

        cid = generate_correlation_id()

        assert len(cid) == 32
        assert all(c in "0123456789abcdef" for c in cid)

    def test_generate_correlation_id_unique(self) -> None:
        """generate_correlation_id should return unique IDs."""
        from fapilog.testing import generate_correlation_id

        ids = [generate_correlation_id() for _ in range(100)]
        assert len(set(ids)) == 100
