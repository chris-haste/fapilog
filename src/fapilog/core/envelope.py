"""
Envelope building for log events.

This module extracts the envelope construction logic from the logger
to improve maintainability and testability.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, cast
from uuid import uuid4

from .schema import LogContext, LogDiagnostics, LogEnvelopeV1

_CONTEXT_FIELDS = frozenset(
    {"request_id", "user_id", "tenant_id", "trace_id", "span_id"}
)


def build_envelope(
    level: str,
    message: str,
    *,
    extra: dict[str, Any] | None = None,
    bound_context: dict[str, Any] | None = None,
    exc: BaseException | None = None,
    exc_info: tuple[
        type[BaseException] | None,
        BaseException | None,
        TracebackType | None,
    ]
    | bool
    | None = None,
    exceptions_enabled: bool = True,
    exceptions_max_frames: int = 50,
    exceptions_max_stack_chars: int = 20000,
    logger_name: str = "root",
    correlation_id: str | None = None,
) -> LogEnvelopeV1:
    """Construct a log envelope following the canonical v1.1 schema.

    The v1.1 schema organizes fields into semantic groupings:
    - context: Request/trace identifiers (correlation_id, request_id, etc.)
    - diagnostics: Runtime/operational data (exception info, etc.)
    - data: User-provided structured data from extra and bound_context

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        message: Log message string.
        extra: Additional fields to include in the data dict.
        bound_context: Context fields bound to the logger. Fields matching
            context identifiers (request_id, user_id, etc.) go to context;
            other fields go to data.
        exc: Exception instance to serialize.
        exc_info: Exception info tuple or True to capture current exception.
        exceptions_enabled: Whether to serialize exceptions.
        exceptions_max_frames: Maximum traceback frames to include.
        exceptions_max_stack_chars: Maximum characters for stack trace.
        logger_name: Name of the logger.
        correlation_id: Correlation ID for request tracing.

    Returns:
        A dictionary containing the v1.1 log envelope with structure:
        {
            "timestamp": str,      # RFC3339 UTC with Z suffix
            "level": str,          # DEBUG, INFO, WARNING, ERROR, CRITICAL
            "message": str,        # Human-readable log message
            "logger": str,         # Logger name
            "context": {...},      # Request/trace context
            "diagnostics": {...},  # Runtime/operational context
            "data": {...},         # User-provided structured data
        }
    """
    # Build context dict (request/trace identifiers)
    context: dict[str, Any] = {}
    corr_id = correlation_id if correlation_id is not None else str(uuid4())
    context["correlation_id"] = corr_id

    # Extract trace context fields from bound_context (first)
    if bound_context:
        for key in _CONTEXT_FIELDS:
            if key in bound_context:
                context[key] = bound_context[key]

    # Extract trace context fields from extra (override bound_context)
    if extra:
        for key in _CONTEXT_FIELDS:
            if key in extra:
                context[key] = extra[key]

    # Build diagnostics dict (runtime/operational context)
    diagnostics: dict[str, Any] = {}

    # Handle exception serialization into diagnostics
    if exceptions_enabled:
        try:
            norm_exc_info = _normalize_exc_info(exc, exc_info)
            if norm_exc_info is not None:
                from .errors import serialize_exception

                exc_data = serialize_exception(
                    norm_exc_info,
                    max_frames=exceptions_max_frames,
                    max_stack_chars=exceptions_max_stack_chars,
                )
                if exc_data:
                    diagnostics["exception"] = exc_data
        except Exception:
            pass  # Don't let serialization errors break logging

    # Build data dict (user-provided structured data)
    data: dict[str, Any] = {}
    if bound_context:
        # Non-context fields go to data
        for key, value in bound_context.items():
            if key not in _CONTEXT_FIELDS:
                data[key] = value

    # Flatten data={...} kwarg if present and is a dict-like mapping
    # This allows the common pattern: logger.info("msg", data={"key": "val"})
    # to flatten into the data section rather than nesting as data.data
    data_dict_values: dict[str, Any] = {}
    if extra and "data" in extra and isinstance(extra["data"], Mapping):
        data_dict_values = dict(extra["data"])
        # Remove "data" from extra so it's not processed again below
        extra = {k: v for k, v in extra.items() if k != "data"}

        # Route context fields from data dict to context section
        for key in _CONTEXT_FIELDS:
            if key in data_dict_values:
                context[key] = data_dict_values.pop(key)

        # Merge remaining data dict values into data (can be overridden by extra)
        for key, value in data_dict_values.items():
            data[key] = value

    if extra:
        # Non-context extra fields go to data (context fields already in context)
        # These override data dict values on collision
        for key, value in extra.items():
            if key not in _CONTEXT_FIELDS:
                data[key] = value

    # RFC3339 timestamp with millisecond precision and Z suffix
    ts = (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )

    # Build v1.1 envelope
    envelope: LogEnvelopeV1 = {
        "timestamp": ts,
        "level": level,
        "message": message,
        "logger": logger_name,
        "context": cast(LogContext, context),
        "diagnostics": cast(LogDiagnostics, diagnostics),
        "data": data,
    }

    return envelope


def _normalize_exc_info(
    exc: BaseException | None,
    exc_info: tuple[
        type[BaseException] | None,
        BaseException | None,
        TracebackType | None,
    ]
    | bool
    | None,
) -> (
    tuple[type[BaseException] | None, BaseException | None, TracebackType | None] | None
):
    """Normalize exception info from various input formats.

    Args:
        exc: Exception instance.
        exc_info: Exception info tuple or True for current exception.

    Returns:
        Normalized exception info tuple or None.
    """
    if exc is not None:
        return (
            type(exc),
            exc,
            getattr(exc, "__traceback__", None),
        )

    if exc_info is True:
        return sys.exc_info()

    if isinstance(exc_info, tuple):
        return exc_info

    return None
