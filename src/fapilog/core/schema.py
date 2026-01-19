"""
Shared type definitions for the canonical log schema v1.1.

These TypedDict definitions provide:
1. Static type checking via mypy
2. IDE autocomplete for schema fields
3. Documentation of the expected structure
4. Single source of truth for producer/consumer contracts

The v1.1 schema organizes fields into semantic groupings:
- context: Request/trace identifiers (WHO and WHAT request)
- diagnostics: Runtime/operational data (WHERE and system state)
- data: User-provided structured data
"""

from __future__ import annotations

from typing import Any, TypedDict


class LogContext(TypedDict, total=False):
    """Request/trace context fields.

    These fields identify WHO and WHAT request is being logged.
    All fields are optional to support partial context.
    """

    correlation_id: str | None
    request_id: str | None
    user_id: str | None
    tenant_id: str | None
    trace_id: str | None
    span_id: str | None


class LogDiagnostics(TypedDict, total=False):
    """Runtime/operational context fields.

    These fields identify WHERE the log originated and system state.
    All fields are optional as they may be added by enrichers.
    """

    service: str | None
    env: str | None
    host: str | None
    pid: int | None
    exception: dict[str, Any] | None


class LogEnvelopeV1(TypedDict):
    """Canonical log envelope structure v1.1.

    This is the schema produced by build_envelope() and consumed by
    serialize_envelope(). All fields are required at the envelope level,
    though context/diagnostics/data dicts may be empty.
    """

    timestamp: str
    level: str
    message: str
    logger: str
    context: LogContext
    diagnostics: LogDiagnostics
    data: dict[str, Any]
