"""
Async logging API surface.

For story 2.1a we only define the minimal surface used by tests and
serialization. The full pipeline will be expanded in later stories.
"""

from __future__ import annotations

from typing import Iterable

from .events import LogEvent


class AsyncLogger:
    """Minimal async logger facade used by the core pipeline tests."""

    async def log_many(self, events: Iterable[LogEvent]) -> int:
        """Placeholder batching API for later pipeline integration."""
        return sum(1 for _ in events)
