"""
Zero-copy-oriented serialization utilities for core pipeline.

This module provides a basic JSON serializer that minimizes copies by using
orjson and exposing bytes directly. Callers can create memoryviews over the
returned bytes to avoid further copying. This satisfies the foundational
requirements for Story 2.1a.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

import orjson

from .errors import ErrorCategory, ErrorSeverity, FapilogError, create_error_context


@runtime_checkable
class MappingLike(Protocol):
    def items(self) -> Any:  # pragma: no cover - structural protocol
        ...


def _default(obj: Any) -> Any:
    """Default serializer hook for unsupported types.

    Keep minimal; prefer upstream objects to be plain JSON types already.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@dataclass
class SerializedView:
    """A lightweight container exposing zero-copy friendly views."""

    data: bytes

    @property
    def view(self) -> memoryview:
        return memoryview(self.data)

    def __bytes__(self) -> bytes:  # convenience
        return self.data


def serialize_mapping_to_json_bytes(
    payload: Mapping[str, Any] | MappingLike,
    *,
    on_memory_usage_bytes: Callable[[int], None] | None = None,
) -> SerializedView:
    """Serialize mapping to JSON bytes using orjson without intermediate str.

    Returns a `SerializedView` exposing a memoryview to avoid copying when
    writing to files or sockets.
    """
    try:
        data = orjson.dumps(payload, default=_default, option=orjson.OPT_SORT_KEYS)
    except TypeError as e:
        context = create_error_context(ErrorCategory.SERIALIZATION, ErrorSeverity.HIGH)
        raise FapilogError(
            "Serialization failed",
            category=ErrorCategory.SERIALIZATION,
            error_context=context,
            cause=e,
        ) from e
    if on_memory_usage_bytes is not None:
        try:
            on_memory_usage_bytes(len(data))
        except Exception:
            # Metrics callbacks must never break serialization
            pass
    return SerializedView(data=data)
