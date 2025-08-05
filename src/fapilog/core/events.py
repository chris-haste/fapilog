"""
Log event classes for fapilog v3 async-first logging.

This module provides the LogEvent class and related enums for structured
logging with rich metadata and future alerting capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict


class EventCategory(str, Enum):
    """Event categories for future alerting rules."""

    ERROR = "error"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BUSINESS = "business"
    SYSTEM = "system"
    COMPLIANCE = "compliance"


class EventSeverity(str, Enum):
    """Event severity levels for future alerting."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEvent:
    """Enhanced log event with alerting-ready metadata."""

    # Core logging fields
    message: str
    level: str
    timestamp: datetime

    # Alerting-ready metadata (future functionality)
    source: str = ""  # Service/component name
    category: EventCategory = EventCategory.SYSTEM
    severity: int = 3  # Numeric severity (1-10)
    tags: Dict[str, str] = field(default_factory=dict)  # Key-value tags
    context: Dict[str, Any] = field(default_factory=dict)  # Request context
    metrics: Dict[str, float] = field(default_factory=dict)  # Performance metrics
    correlation_id: str = ""  # For tracing across services

    def __post_init__(self) -> None:
        """Validate event after initialization."""
        if not self.message:
            raise ValueError("Log event message cannot be empty")

        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime object")

        if not (1 <= self.severity <= 10):
            raise ValueError("Severity must be between 1 and 10")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "message": self.message,
            "level": self.level,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "category": self.category,
            "severity": self.severity,
            "tags": self.tags,
            "context": self.context,
            "metrics": self.metrics,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEvent":
        """Create event from dictionary."""
        return cls(
            message=data["message"],
            level=data["level"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", ""),
            category=EventCategory(data.get("category", "system")),
            severity=data.get("severity", 3),
            tags=data.get("tags", {}),
            context=data.get("context", {}),
            metrics=data.get("metrics", {}),
            correlation_id=data.get("correlation_id", ""),
        )

    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the event."""
        self.tags[key] = value

    def add_metric(self, key: str, value: float) -> None:
        """Add a metric to the event."""
        self.metrics[key] = value

    def add_context(self, key: str, value: Any) -> None:
        """Add context to the event."""
        self.context[key] = value

    def is_alertable(self) -> bool:
        """Check if this event should trigger alerts."""
        return (
            self.category in [EventCategory.ERROR, EventCategory.SECURITY]
            or self.severity >= 8
        )

    def get_alert_key(self) -> str:
        """Get a unique key for alerting deduplication."""
        return f"{self.source}:{self.category}:{self.severity}"
