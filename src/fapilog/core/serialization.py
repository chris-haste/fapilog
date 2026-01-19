"""
Zero-copy-oriented serialization utilities for core pipeline.

This module provides JSON serialization optimized for the fapilog logging
pipeline, minimizing copies by using orjson and exposing bytes directly.
Callers can create memoryviews over the returned bytes to avoid further copying.

Key functions:
- serialize_envelope(): Schema-versioned envelope serialization (v1.1 schema)
- serialize_mapping_to_json_bytes(): Generic JSON serialization
- ensure_rfc3339_utc(): Timestamp normalization

After Stories 1.26/1.27/1.28 (v1.1 schema alignment):
- build_envelope() produces events with context/diagnostics/data fields
- serialize_envelope() trusts this upstream schema compliance
- Serialization failures only occur for non-JSON-serializable objects
- The fallback path is now truly exceptional, not the normal path
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
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


# -----------------------------
# Envelope Serialization (v1.0)
# -----------------------------
_RFC3339_UTC_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$")


def ensure_rfc3339_utc(ts: float | str) -> str:
    """Normalize a timestamp to RFC3339 UTC with 'Z' suffix and millisecond precision.

    Accepts a POSIX seconds float or an existing RFC3339 string. Raises on invalid input.
    """
    if isinstance(ts, (int, float)):
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        # Millisecond precision for stability
        s = dt.isoformat(timespec="milliseconds")
        return s.replace("+00:00", "Z")
    if isinstance(ts, str):
        # If already RFC3339 UTC with 'Z', accept; if not, try parsing
        if _RFC3339_UTC_REGEX.match(ts):
            return ts
        # Best-effort: attempt to parse common ISO forms and coerce to UTC Z
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            s = dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            if _RFC3339_UTC_REGEX.match(s):
                return s
        except Exception:
            pass
    raise TypeError("timestamp must be float seconds or RFC3339 string (UTC)")


def serialize_envelope(log: Mapping[str, Any]) -> SerializedView:
    """Build a schema-versioned envelope {"schema_version":"1.1","log":{...}}.

    After Stories 1.26/1.27, the pipeline produces log events in the v1.1
    canonical schema from build_envelope() + enrichers. This function trusts
    that upstream provides the correct structure and only fails for truly
    unserializable data (non-JSON-serializable objects).

    The v1.1 schema organizes fields into semantic groupings:
    - context: Request/trace identifiers (correlation_id, request_id, etc.)
    - diagnostics: Runtime/operational data (exception info, etc.)
    - data: User-provided structured data

    Required keys in log: timestamp, level, message.
    - timestamp may be float seconds or RFC3339 string; normalized to RFC3339 UTC Z.

    Optional keys with defaults:
    - context: {} (request/trace context from enrichers)
    - diagnostics: {} (runtime info like exceptions)
    - data: {} (user-provided structured data)
    - tags: list[str]
    - logger: str

    Raises:
        ValueError: If timestamp, level, or message are missing.
        FapilogError: If the payload contains non-JSON-serializable objects.
    """
    # Validate required fields (minimal validation - trust upstream schema)
    if "timestamp" not in log or "level" not in log or "message" not in log:
        raise ValueError("missing required fields in log payload")

    # Normalize timestamp
    ts = ensure_rfc3339_utc(log["timestamp"])

    # Get context/diagnostics/data with defaults (trust upstream provides mappings)
    context = log.get("context")
    diagnostics = log.get("diagnostics")
    data = log.get("data")

    # Construct normalized log object
    norm_log: dict[str, Any] = {
        "timestamp": ts,
        "level": str(log["level"]),
        "message": str(log["message"]),
        "context": dict(context) if isinstance(context, Mapping) else {},
        "diagnostics": dict(diagnostics) if isinstance(diagnostics, Mapping) else {},
        "data": dict(data) if isinstance(data, Mapping) else {},
    }

    # Copy optional known fields when present
    for key in ("tags", "logger"):
        if key in log:
            norm_log[key] = log[key]

    envelope = {"schema_version": "1.1", "log": norm_log}
    return serialize_mapping_to_json_bytes(envelope)
