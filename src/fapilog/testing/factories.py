"""
Test data factories for testing fapilog plugins.

Provides utilities to generate test data for log events.
"""

from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from typing import Any


def create_log_event(
    level: str = "INFO",
    message: str | None = None,
    **metadata: Any,
) -> dict[str, Any]:
    """Create a log event with sensible defaults.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message (auto-generated if None)
        **metadata: Additional metadata fields

    Returns:
        Complete log event dict
    """
    if message is None:
        message = f"Test message {random.randint(1000, 9999)}"

    return {
        "level": level,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "logger": "test",
        "correlation_id": generate_correlation_id(),
        "metadata": metadata,
    }


def create_batch_events(
    count: int,
    level: str = "INFO",
    **metadata: Any,
) -> list[dict[str, Any]]:
    """Create a batch of log events.

    Args:
        count: Number of events to create
        level: Log level for all events
        **metadata: Metadata to include in all events

    Returns:
        List of log events
    """
    return [
        create_log_event(
            level=level,
            message=f"Batch message {i}",
            **metadata,
        )
        for i in range(count)
    ]


def generate_correlation_id() -> str:
    """Generate a random correlation ID."""
    return "".join(random.choices(string.hexdigits.lower()[:16], k=32))


def create_sensitive_event() -> dict[str, Any]:
    """Create an event with various sensitive fields for redaction testing."""
    return {
        "level": "INFO",
        "message": "User action",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": "user_123",
            "email": "test@example.com",
            "password": "supersecret123",
            "ssn": "123-45-6789",
        },
        "payment": {
            "card_number": "4111111111111111",
            "cvv": "123",
            "expiry": "12/25",
        },
        "auth": {
            "api_key": "sk-abcdef123456",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        },
        "url": "https://user:pass@api.example.com/data",
    }


# Mark as used for static analysis
_VULTURE_USED: tuple[object, ...] = (
    create_log_event,
    create_batch_events,
    create_sensitive_event,
    generate_correlation_id,
)
