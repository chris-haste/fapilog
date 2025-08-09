"""
Event models for the async-first logging pipeline.

Defines the minimal `LogEvent` structure used by the core serialization engine.

Keep this intentionally small; plugins may extend or wrap this model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import BaseModel, Field


class LogEvent(BaseModel):
    """Canonical event structure for logging in the core pipeline.

    This model is designed to be efficient and stable. Additional fields
    can be added over time, but existing fields should remain compatible.
    """

    # Required core fields
    timestamp: float = Field(
        default_factory=lambda: datetime.now(timezone.utc).timestamp(),
        description="Event time as POSIX timestamp (UTC)",
        ge=0,
    )
    level: str = Field(default="INFO", description="Log level")
    message: str = Field(default="", description="Human-readable message")

    # Optional context fields
    logger: str | None = Field(default=None, description="Logger name")
    component: str | None = Field(
        default=None, description="Component or subsystem name"
    )
    correlation_id: str | None = Field(
        default=None, description="Correlation or request identifier"
    )

    # Free-form metadata for structured logging
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "allow",
        "frozen": False,
        "populate_by_name": True,
    }

    def to_mapping(self) -> Mapping[str, Any]:
        """Return a readonly mapping for zero-copy style access.

        Pydantic returns a dict; callers should avoid mutating it in
        performance critical paths to prevent copies.
        """
        # exclude_none keeps payload compact
        return self.model_dump(exclude_none=True)
