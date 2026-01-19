"""Tests for LogEvent model v1.1 schema with semantic groupings."""

from __future__ import annotations

from fapilog.core.events import LogEvent


class TestLogEventV1_1Schema:
    """Tests for LogEvent model matching v1.1 canonical schema."""

    def test_log_event_has_semantic_group_fields(self) -> None:
        """LogEvent model has context, diagnostics, and data fields."""
        event = LogEvent(
            timestamp=1705312800.0,
            level="INFO",
            message="test",
        )

        assert hasattr(event, "context")
        assert hasattr(event, "diagnostics")
        assert hasattr(event, "data")

    def test_log_event_semantic_groups_default_to_empty_dicts(self) -> None:
        """Semantic group fields default to empty dicts."""
        event = LogEvent(level="INFO", message="test")

        assert event.context == {}
        assert event.diagnostics == {}
        assert event.data == {}

    def test_log_event_can_be_created_with_semantic_groups(self) -> None:
        """LogEvent accepts semantic group data on construction."""
        event = LogEvent(
            timestamp=1705312800.0,
            level="INFO",
            message="test",
            logger="myapp",
            context={"correlation_id": "abc", "request_id": "req-123"},
            diagnostics={"host": "server1", "pid": 12345},
            data={"user_action": "login"},
        )

        assert event.context["correlation_id"] == "abc"
        assert event.context["request_id"] == "req-123"
        assert event.diagnostics["host"] == "server1"
        assert event.diagnostics["pid"] == 12345
        assert event.data["user_action"] == "login"

    def test_log_event_removed_legacy_fields(self) -> None:
        """Legacy fields (metadata, correlation_id, component) are removed."""
        # These fields should not be accepted (or if accepted via extra, ignored)
        event = LogEvent(level="INFO", message="test")

        # These should not be present as model fields
        assert (
            not hasattr(event, "metadata") or getattr(event, "metadata", None) is None
        )
        assert (
            not hasattr(event, "correlation_id")
            or getattr(event, "correlation_id", None) is None
        )
        assert (
            not hasattr(event, "component") or getattr(event, "component", None) is None
        )


class TestLogEventToMapping:
    """Tests for LogEvent.to_mapping() method."""

    def test_to_mapping_includes_semantic_groups(self) -> None:
        """to_mapping() includes all semantic group fields."""
        event = LogEvent(
            timestamp=1705312800.0,
            level="INFO",
            message="test",
            logger="myapp",
            context={"correlation_id": "abc"},
            diagnostics={"host": "server1"},
            data={"user_action": "login"},
        )

        mapping = event.to_mapping()

        assert "context" in mapping
        assert "diagnostics" in mapping
        assert "data" in mapping
        assert mapping["context"]["correlation_id"] == "abc"
        assert mapping["diagnostics"]["host"] == "server1"
        assert mapping["data"]["user_action"] == "login"

    def test_to_mapping_excludes_none_values(self) -> None:
        """to_mapping() excludes None values (compact output)."""
        event = LogEvent(
            timestamp=1705312800.0,
            level="INFO",
            message="test",
            logger=None,  # Should be excluded
        )

        mapping = event.to_mapping()

        assert "logger" not in mapping

    def test_to_mapping_includes_empty_semantic_groups(self) -> None:
        """to_mapping() includes empty semantic groups (they're dicts, not None)."""
        event = LogEvent(
            timestamp=1705312800.0,
            level="INFO",
            message="test",
        )

        mapping = event.to_mapping()

        # Empty dicts should be included (they're not None)
        assert "context" in mapping
        assert "diagnostics" in mapping
        assert "data" in mapping

    def test_to_mapping_preserves_core_fields(self) -> None:
        """to_mapping() includes required core fields."""
        event = LogEvent(
            timestamp=1705312800.0,
            level="ERROR",
            message="Something failed",
            logger="myapp.service",
        )

        mapping = event.to_mapping()

        assert mapping["timestamp"] == 1705312800.0
        assert mapping["level"] == "ERROR"
        assert mapping["message"] == "Something failed"
        assert mapping["logger"] == "myapp.service"


class TestLogEventConstruction:
    """Tests for LogEvent construction behavior."""

    def test_timestamp_has_default(self) -> None:
        """Timestamp defaults to current UTC time."""
        event = LogEvent(level="INFO", message="test")

        # Timestamp should be a valid positive POSIX timestamp
        assert event.timestamp > 0
        assert isinstance(event.timestamp, float)

    def test_level_has_default(self) -> None:
        """Level defaults to INFO."""
        event = LogEvent(message="test")

        assert event.level == "INFO"

    def test_message_has_default(self) -> None:
        """Message defaults to empty string."""
        event = LogEvent()

        assert event.message == ""
