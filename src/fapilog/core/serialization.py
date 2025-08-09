"""
Zero-copy-oriented serialization utilities for core pipeline.

This module provides a basic JSON serializer that minimizes copies by using
orjson and exposing bytes directly. Callers can create memoryviews over the
returned bytes to avoid further copying. This satisfies the foundational
requirements for Story 2.1a.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    Protocol,
    Sequence,
    runtime_checkable,
)

import orjson

from .errors import (
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    create_error_context,
)


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


@dataclass
class SegmentedSerialized:
    """Zero-copy friendly segmented representation of serialized data.

    Holds multiple memoryview segments that together form a single logical
    payload. Useful for conversions like appending a newline without copying
    the original buffer.
    """

    segments: Sequence[memoryview]

    @property
    def total_length(self) -> int:
        return sum(len(s) for s in self.segments)

    def iter_memoryviews(self) -> Iterable[memoryview]:
        return iter(self.segments)

    def to_bytes(self) -> bytes:
        # Explicit copy when a contiguous buffer is needed by a caller
        return b"".join(bytes(s) for s in self.segments)


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
        data = orjson.dumps(
            payload,
            default=_default,
            option=orjson.OPT_SORT_KEYS,
        )
    except TypeError as e:
        context = create_error_context(
            ErrorCategory.SERIALIZATION,
            ErrorSeverity.HIGH,
        )
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


def serialize_protobuf_like(obj: Any) -> SerializedView:
    """Serialize a protobuf-like message to bytes without extra copies.

    Supports objects implementing `SerializeToString()` or `to_bytes()`.
    Falls back to raw bytes if `obj` is already bytes-like.
    """
    try:
        if hasattr(obj, "SerializeToString") and callable(obj.SerializeToString):
            data = obj.SerializeToString()
        elif hasattr(obj, "to_bytes") and callable(obj.to_bytes):
            data = obj.to_bytes()
        elif isinstance(obj, (bytes, bytearray, memoryview)):
            data = bytes(obj)
        else:
            raise TypeError("Object does not support protobuf-like serialization")
        return SerializedView(data=data)
    except Exception as e:  # Defensive error wrapping
        context = create_error_context(ErrorCategory.SERIALIZATION, ErrorSeverity.HIGH)
        raise FapilogError(
            "Protobuf-like serialization failed",
            category=ErrorCategory.SERIALIZATION,
            error_context=context,
            cause=e,
        ) from e


def convert_json_bytes_to_jsonl(view: SerializedView) -> SegmentedSerialized:
    """Convert JSON bytes to JSONL (append newline) without copying payload.

    Returns a segmented payload with the original JSON bytes and a newline.
    """
    return SegmentedSerialized(segments=(view.view, memoryview(b"\n")))


def serialize_custom_fapilog_v1(
    payload: Mapping[str, Any] | MappingLike,
) -> SerializedView:
    """Serialize mapping to a simple custom framed format.

    Format: 4-byte big-endian length prefix of the JSON payload,
    followed by the JSON bytes. This entails a single allocation
    for (4 + len(json)).
    """
    json_view = serialize_mapping_to_json_bytes(payload)
    json_bytes = bytes(json_view.data)  # one contiguous buffer already
    length = len(json_bytes)
    header = length.to_bytes(4, byteorder="big", signed=False)
    framed = header + json_bytes
    return SerializedView(data=framed)
