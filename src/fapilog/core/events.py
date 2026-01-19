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
    """Canonical event structure for logging in the core pipeline (v1.1 schema).

    This model follows the v1.1 canonical schema with semantic field groupings:
    - context: Request/trace identifiers (correlation_id, request_id, trace_id, etc.)
    - diagnostics: Runtime/operational data (host, pid, service, k8s info, exceptions)
    - data: User-provided structured data

    Breaking changes from v1.0:
    - Removed: metadata (use data instead)
    - Removed: correlation_id (use context["correlation_id"])
    - Removed: component (use context or data)
    """

    # Required core fields
    timestamp: float = Field(
        default_factory=lambda: datetime.now(timezone.utc).timestamp(),
        description="Event time as POSIX timestamp (UTC)",
        ge=0,
    )
    level: str = Field(default="INFO", description="Log level")
    message: str = Field(default="", description="Human-readable message")

    # Optional identification
    logger: str | None = Field(default=None, description="Logger name")

    # Semantic groupings (v1.1)
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Request/trace context - identifies WHO and WHAT request",
    )
    diagnostics: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime/operational context - identifies WHERE and system state",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="User-provided structured data (replaces metadata)",
    )

    model_config = {
        "extra": "allow",
        "frozen": False,
        "populate_by_name": True,
    }

    def to_mapping(self) -> Mapping[str, Any]:
        """Return a readonly mapping for zero-copy style access.

        Returns a dict with v1.1 schema structure including semantic groups.
        Pydantic returns a dict; callers should avoid mutating it in
        performance critical paths to prevent copies.
        """
        # exclude_none keeps payload compact
        return self.model_dump(exclude_none=True)
