"""
Unit tests for LogEvent and related classes.
"""

from datetime import datetime

import pytest

from fapilog.core.events import EventCategory, EventSeverity, LogEvent


class TestEventCategory:
    """Test EventCategory enum."""

    def test_event_categories(self) -> None:
        """Test all event categories."""
        assert EventCategory.ERROR.value == "error"
        assert EventCategory.PERFORMANCE.value == "performance"
        assert EventCategory.SECURITY.value == "security"
        assert EventCategory.BUSINESS.value == "business"
        assert EventCategory.SYSTEM.value == "system"
        assert EventCategory.COMPLIANCE.value == "compliance"


class TestEventSeverity:
    """Test EventSeverity enum."""

    def test_event_severities(self) -> None:
        """Test all event severity levels."""
        assert EventSeverity.DEBUG.value == "debug"
        assert EventSeverity.INFO.value == "info"
        assert EventSeverity.WARNING.value == "warning"
        assert EventSeverity.ERROR.value == "error"
        assert EventSeverity.CRITICAL.value == "critical"


class TestLogEvent:
    """Test LogEvent functionality."""

    @pytest.fixture  # type: ignore[misc]
    def sample_timestamp(self) -> datetime:
        """Create a sample timestamp."""
        return datetime(2024, 1, 15, 10, 30, 45)

    @pytest.fixture  # type: ignore[misc]
    def basic_event(self, sample_timestamp: datetime) -> LogEvent:
        """Create a basic log event."""
        return LogEvent(
            message="Test message", level="INFO", timestamp=sample_timestamp
        )

    @pytest.fixture  # type: ignore[misc]
    def rich_event(self, sample_timestamp: datetime) -> LogEvent:
        """Create a log event with rich metadata."""
        return LogEvent(
            message="Rich test message",
            level="ERROR",
            timestamp=sample_timestamp,
            source="test_service",
            category=EventCategory.BUSINESS,
            severity=8,
            tags={"user_id": "123", "action": "login"},
            context={"ip": "192.168.1.1", "user_agent": "test"},
            metrics={"response_time": 1.5, "memory_usage": 512.0},
            correlation_id="corr-abc123",
        )

    def test_basic_event_creation(
        self, basic_event: LogEvent, sample_timestamp: datetime
    ) -> None:
        """Test basic event creation."""
        assert basic_event.message == "Test message"
        assert basic_event.level == "INFO"
        assert basic_event.timestamp == sample_timestamp
        assert basic_event.source == ""
        assert basic_event.category == EventCategory.SYSTEM
        assert basic_event.severity == 3
        assert basic_event.tags == {}
        assert basic_event.context == {}
        assert basic_event.metrics == {}
        assert basic_event.correlation_id == ""

    def test_rich_event_creation(
        self, rich_event: LogEvent, sample_timestamp: datetime
    ) -> None:
        """Test rich event creation with metadata."""
        assert rich_event.message == "Rich test message"
        assert rich_event.level == "ERROR"
        assert rich_event.timestamp == sample_timestamp
        assert rich_event.source == "test_service"
        assert rich_event.category == EventCategory.BUSINESS
        assert rich_event.severity == 8
        assert rich_event.tags == {"user_id": "123", "action": "login"}
        assert rich_event.context == {"ip": "192.168.1.1", "user_agent": "test"}
        assert rich_event.metrics == {"response_time": 1.5, "memory_usage": 512.0}
        assert rich_event.correlation_id == "corr-abc123"

    def test_empty_message_validation(self, sample_timestamp: datetime) -> None:
        """Test that empty message raises ValueError."""
        with pytest.raises(ValueError, match="Log event message cannot be empty"):
            LogEvent(message="", level="INFO", timestamp=sample_timestamp)

    def test_invalid_timestamp_validation(self) -> None:
        """Test that invalid timestamp raises ValueError."""
        with pytest.raises(ValueError, match="Timestamp must be a datetime object"):
            LogEvent(
                message="Test",
                level="INFO",
                timestamp="not a datetime",  # type: ignore
            )

    def test_severity_validation_too_low(self, sample_timestamp: datetime) -> None:
        """Test that severity below 1 raises ValueError."""
        with pytest.raises(ValueError, match="Severity must be between 1 and 10"):
            LogEvent(
                message="Test", level="INFO", timestamp=sample_timestamp, severity=0
            )

    def test_severity_validation_too_high(self, sample_timestamp: datetime) -> None:
        """Test that severity above 10 raises ValueError."""
        with pytest.raises(ValueError, match="Severity must be between 1 and 10"):
            LogEvent(
                message="Test", level="INFO", timestamp=sample_timestamp, severity=11
            )

    def test_severity_validation_valid_range(self, sample_timestamp: datetime) -> None:
        """Test that valid severity range works."""
        for severity in range(1, 11):
            event = LogEvent(
                message="Test",
                level="INFO",
                timestamp=sample_timestamp,
                severity=severity,
            )
            assert event.severity == severity

    def test_to_dict_basic(self, basic_event: LogEvent) -> None:
        """Test converting basic event to dictionary."""
        result = basic_event.to_dict()

        expected = {
            "message": "Test message",
            "level": "INFO",
            "timestamp": "2024-01-15T10:30:45",
            "source": "",
            "category": "system",
            "severity": 3,
            "tags": {},
            "context": {},
            "metrics": {},
            "correlation_id": "",
        }

        assert result == expected

    def test_to_dict_rich(self, rich_event: LogEvent) -> None:
        """Test converting rich event to dictionary."""
        result = rich_event.to_dict()

        expected = {
            "message": "Rich test message",
            "level": "ERROR",
            "timestamp": "2024-01-15T10:30:45",
            "source": "test_service",
            "category": "business",
            "severity": 8,
            "tags": {"user_id": "123", "action": "login"},
            "context": {"ip": "192.168.1.1", "user_agent": "test"},
            "metrics": {"response_time": 1.5, "memory_usage": 512.0},
            "correlation_id": "corr-abc123",
        }

        assert result == expected

    def test_from_dict_basic(self, sample_timestamp: datetime) -> None:
        """Test creating event from dictionary."""
        data = {
            "message": "Test from dict",
            "level": "WARNING",
            "timestamp": "2024-01-15T10:30:45",
        }

        event = LogEvent.from_dict(data)

        assert event.message == "Test from dict"
        assert event.level == "WARNING"
        assert event.timestamp == sample_timestamp
        assert event.source == ""
        assert event.category == EventCategory.SYSTEM
        assert event.severity == 3

    def test_from_dict_rich(self, sample_timestamp: datetime) -> None:
        """Test creating rich event from dictionary."""
        data = {
            "message": "Rich from dict",
            "level": "CRITICAL",
            "timestamp": "2024-01-15T10:30:45",
            "source": "dict_service",
            "category": "security",
            "severity": 9,
            "tags": {"alert": "true"},
            "context": {"user": "admin"},
            "metrics": {"cpu": 95.5},
            "correlation_id": "dict-123",
        }

        event = LogEvent.from_dict(data)

        assert event.message == "Rich from dict"
        assert event.level == "CRITICAL"
        assert event.timestamp == sample_timestamp
        assert event.source == "dict_service"
        assert event.category == EventCategory.SECURITY
        assert event.severity == 9
        assert event.tags == {"alert": "true"}
        assert event.context == {"user": "admin"}
        assert event.metrics == {"cpu": 95.5}
        assert event.correlation_id == "dict-123"

    def test_add_tag(self, basic_event: LogEvent) -> None:
        """Test adding tags to event."""
        basic_event.add_tag("test_key", "test_value")
        basic_event.add_tag("another_key", "another_value")

        assert basic_event.tags == {
            "test_key": "test_value",
            "another_key": "another_value",
        }

    def test_add_metric(self, basic_event: LogEvent) -> None:
        """Test adding metrics to event."""
        basic_event.add_metric("response_time", 2.5)
        basic_event.add_metric("memory_usage", 1024.0)

        assert basic_event.metrics == {"response_time": 2.5, "memory_usage": 1024.0}

    def test_add_context(self, basic_event: LogEvent) -> None:
        """Test adding context to event."""
        basic_event.add_context("request_id", "req-123")
        basic_event.add_context("user_data", {"id": 456, "name": "test"})

        assert basic_event.context == {
            "request_id": "req-123",
            "user_data": {"id": 456, "name": "test"},
        }

    def test_is_alertable_by_category(self, sample_timestamp: datetime) -> None:
        """Test alertable detection by category."""
        # Error category should be alertable
        error_event = LogEvent(
            message="Error occurred",
            level="ERROR",
            timestamp=sample_timestamp,
            category=EventCategory.ERROR,
            severity=5,
        )
        assert error_event.is_alertable() is True

        # Security category should be alertable
        security_event = LogEvent(
            message="Security issue",
            level="WARNING",
            timestamp=sample_timestamp,
            category=EventCategory.SECURITY,
            severity=4,
        )
        assert security_event.is_alertable() is True

        # Business category with low severity should not be alertable
        business_event = LogEvent(
            message="Business event",
            level="INFO",
            timestamp=sample_timestamp,
            category=EventCategory.BUSINESS,
            severity=3,
        )
        assert business_event.is_alertable() is False

    def test_is_alertable_by_severity(self, sample_timestamp: datetime) -> None:
        """Test alertable detection by severity."""
        # High severity (>=8) should be alertable regardless of category
        high_severity_event = LogEvent(
            message="High severity",
            level="ERROR",
            timestamp=sample_timestamp,
            category=EventCategory.SYSTEM,
            severity=8,
        )
        assert high_severity_event.is_alertable() is True

        # Critical severity should be alertable
        critical_event = LogEvent(
            message="Critical event",
            level="CRITICAL",
            timestamp=sample_timestamp,
            category=EventCategory.PERFORMANCE,
            severity=10,
        )
        assert critical_event.is_alertable() is True

        # Low severity system event should not be alertable
        low_severity_event = LogEvent(
            message="Low severity",
            level="INFO",
            timestamp=sample_timestamp,
            category=EventCategory.SYSTEM,
            severity=2,
        )
        assert low_severity_event.is_alertable() is False

    def test_get_alert_key(self, rich_event: LogEvent) -> None:
        """Test alert key generation."""
        alert_key = rich_event.get_alert_key()
        expected = "test_service:EventCategory.BUSINESS:8"
        assert alert_key == expected

    def test_get_alert_key_empty_source(self, sample_timestamp: datetime) -> None:
        """Test alert key generation with empty source."""
        event = LogEvent(
            message="Test",
            level="ERROR",
            timestamp=sample_timestamp,
            category=EventCategory.ERROR,
            severity=7,
        )

        alert_key = event.get_alert_key()
        expected = ":EventCategory.ERROR:7"
        assert alert_key == expected

    def test_round_trip_serialization(self, rich_event: LogEvent) -> None:
        """Test that event can be serialized and deserialized without loss."""
        # Convert to dict and back
        event_dict = rich_event.to_dict()
        recreated_event = LogEvent.from_dict(event_dict)

        # Should be identical
        assert recreated_event.message == rich_event.message
        assert recreated_event.level == rich_event.level
        assert recreated_event.timestamp == rich_event.timestamp
        assert recreated_event.source == rich_event.source
        assert recreated_event.category == rich_event.category
        assert recreated_event.severity == rich_event.severity
        assert recreated_event.tags == rich_event.tags
        assert recreated_event.context == rich_event.context
        assert recreated_event.metrics == rich_event.metrics
        assert recreated_event.correlation_id == rich_event.correlation_id
