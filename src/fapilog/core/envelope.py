"""
Envelope building for log events.

This module extracts the envelope construction logic from the logger
to improve maintainability and testability.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import TracebackType
from typing import Any
from uuid import uuid4


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
) -> dict[str, Any]:
    """Construct a log envelope with all metadata.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        message: Log message string.
        extra: Additional fields to include in the metadata.
        bound_context: Context fields bound to the logger.
        exc: Exception instance to serialize.
        exc_info: Exception info tuple or True to capture current exception.
        exceptions_enabled: Whether to serialize exceptions.
        exceptions_max_frames: Maximum traceback frames to include.
        exceptions_max_stack_chars: Maximum characters for stack trace.
        logger_name: Name of the logger.
        correlation_id: Correlation ID for request tracing.

    Returns:
        A dictionary containing the log envelope with nested metadata.
    """
    # Build merged metadata dict (bound_context first, then extra for precedence)
    merged_metadata: dict[str, Any] = {}
    if bound_context:
        merged_metadata.update(bound_context)
    if extra:
        merged_metadata.update(extra)

    # Handle exception serialization into metadata
    # Wrapped in try/except to ensure logging doesn't fail if serialization errors
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
                    merged_metadata.update(exc_data)
        except Exception:
            pass  # Don't let serialization errors break logging

    # Generate or use provided correlation ID
    corr_id = correlation_id if correlation_id is not None else str(uuid4())

    # Build envelope with nested metadata (matches LogEvent.to_mapping() structure)
    envelope: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "level": level,
        "message": message,
        "logger": logger_name,
        "correlation_id": corr_id,
        "metadata": merged_metadata,
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
