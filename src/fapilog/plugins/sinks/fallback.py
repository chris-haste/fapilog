from __future__ import annotations

import json
import sys
from typing import Any, Literal

from ...core import diagnostics
from ...core.defaults import (
    FALLBACK_SCRUB_PATTERNS,
    FALLBACK_SENSITIVE_FIELDS,
    should_fallback_sink,
)

# Type alias for redact mode
RedactMode = Literal["inherit", "minimal", "none"]

# Prevent stack overflow on pathological input
_MAX_REDACT_DEPTH = 32


def _scrub_raw(text: str) -> str:
    """Apply regex scrubbing to raw text for common secret patterns.

    Used when JSON parsing fails and we must write raw bytes to stderr.
    Complements minimal_redact() which handles parsed JSON dicts.

    Args:
        text: The raw text to scrub.

    Returns:
        Text with common secret patterns (password=, token=, etc.) masked.
    """
    for pattern, replacement in FALLBACK_SCRUB_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _redact_list(items: list[Any], *, _depth: int) -> list[Any]:
    """Recursively redact sensitive fields within list items."""
    if _depth >= _MAX_REDACT_DEPTH:
        return items  # Stop recursion at depth limit

    result: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            result.append(minimal_redact(item, _depth=_depth + 1))
        elif isinstance(item, list):
            result.append(_redact_list(item, _depth=_depth + 1))
        else:
            result.append(item)
    return result


def minimal_redact(
    payload: dict[str, Any],
    *,
    _depth: int = 0,
) -> dict[str, Any]:
    """Apply minimal redaction for fallback safety.

    Masks values of keys that match FALLBACK_SENSITIVE_FIELDS (case-insensitive).
    Recursively processes nested dictionaries and lists.

    Args:
        payload: The dictionary to redact.
        _depth: Internal recursion depth counter (do not set manually).

    Returns:
        A new dictionary with sensitive fields masked as "***".
    """
    if _depth >= _MAX_REDACT_DEPTH:
        return payload  # Stop recursion at depth limit

    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in FALLBACK_SENSITIVE_FIELDS:
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = minimal_redact(value, _depth=_depth + 1)
        elif isinstance(value, list):
            result[key] = _redact_list(value, _depth=_depth + 1)
        else:
            result[key] = value
    return result


def _sink_name(sink: Any) -> str:
    return getattr(sink, "name", type(sink).__name__)


def _extract_bytes(payload: Any) -> bytes:
    """Extract raw bytes from various payload types.

    Handles SerializedView, memoryview, bytes, bytearray, and falls back
    to UTF-8 encoding for string types.
    """
    if hasattr(payload, "data"):
        data = getattr(payload, "data", b"")
        return bytes(data) if isinstance(data, memoryview) else data
    if isinstance(payload, memoryview):
        return bytes(payload)
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    return str(payload).encode("utf-8")


def _serialize_entry(entry: dict[str, Any]) -> str:
    try:
        return json.dumps(entry, separators=(",", ":"), default=str)
    except Exception:
        try:
            return json.dumps({"message": str(entry)}, separators=(",", ":"))
        except Exception:
            return '{"message":"unserializable"}'


def _format_payload(payload: Any, *, serialized: bool) -> str:
    if serialized:
        if hasattr(payload, "data"):
            data = getattr(payload, "data", b"")
        elif isinstance(payload, (bytes, bytearray, memoryview)):
            data = bytes(payload)
        else:
            return _serialize_entry({"message": str(payload)})
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return _serialize_entry({"message": str(data)})
    if isinstance(payload, dict):
        return _serialize_entry(payload)
    return _serialize_entry({"message": str(payload)})


def _write_to_stderr(
    payload: Any,
    *,
    serialized: bool,
    redact_mode: RedactMode = "minimal",
    fallback_scrub_raw: bool = True,
    fallback_raw_max_bytes: int | None = None,
) -> None:
    """Write payload to stderr with optional redaction.

    Args:
        payload: The payload to write.
        serialized: Whether the payload is already serialized.
        redact_mode: Redaction mode - "minimal" (default), "inherit", or "none".
        fallback_scrub_raw: Apply keyword scrubbing to raw output (Story 4.59).
        fallback_raw_max_bytes: Optional byte limit for raw output truncation.

    For serialized payloads with redact_mode="minimal", attempts to:
    1. Deserialize the JSON payload
    2. Apply minimal redaction if it's a dict
    3. Re-serialize for output

    Falls back to raw output with diagnostic warning if JSON parsing fails.
    When raw fallback is used, applies keyword scrubbing and optional truncation.
    """
    # Handle serialized payloads with minimal redaction (Story 4.54)
    if serialized and redact_mode == "minimal":
        try:
            data = _extract_bytes(payload)
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                parsed = minimal_redact(parsed)
            text = json.dumps(parsed, separators=(",", ":"), default=str)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            # Raw fallback path - apply scrubbing and truncation (Story 4.59)
            text = _format_payload(payload, serialized=True)
            original_size = len(text.encode("utf-8", errors="replace"))
            scrubbed = False
            truncated = False

            if fallback_scrub_raw:
                text = _scrub_raw(text)
                scrubbed = True

            if (
                fallback_raw_max_bytes is not None
                and len(text) > fallback_raw_max_bytes
            ):
                text = text[:fallback_raw_max_bytes] + "[truncated]"
                truncated = True

            diagnostics.warn(
                "fallback",
                "serialized payload not valid JSON, writing raw",
                error=str(exc),
                scrubbed=scrubbed,
                truncated=truncated,
                original_size=original_size,
                _rate_limit_key="fallback_json_error",
            )
    elif not serialized and isinstance(payload, dict):
        # Apply redaction for dict payloads when not serialized
        if redact_mode == "minimal":
            payload = minimal_redact(payload)
        # "inherit" mode is handled at a higher level (requires pipeline context)
        # "none" mode passes through without redaction
        text = _format_payload(payload, serialized=False)
    else:
        text = _format_payload(payload, serialized=serialized)

    if not text.endswith("\n"):
        text += "\n"
    sys.stderr.write(text)
    sys.stderr.flush()


async def handle_sink_write_failure(
    payload: Any,
    *,
    sink: Any,
    error: BaseException,
    serialized: bool = False,
    redact_mode: RedactMode = "minimal",
) -> None:
    if not should_fallback_sink(True):
        return

    sink_label = _sink_name(sink)
    error_type = type(error).__name__

    # Emit warning for unredacted fallback (AC1)
    if redact_mode == "none":
        try:
            diagnostics.warn(
                "sink",
                "fallback triggered without redaction configured",
            )
        except Exception:
            pass

    try:
        _write_to_stderr(payload, serialized=serialized, redact_mode=redact_mode)
    except Exception:
        try:
            diagnostics.warn(
                "sink",
                "all sinks failed, log entry lost",
                sink=sink_label,
                error=error_type,
                fallback="stderr",
            )
        except Exception:
            pass
        return

    try:
        diagnostics.warn(
            "sink",
            "primary sink failed, using stderr fallback",
            sink=sink_label,
            error=error_type,
            fallback="stderr",
        )
    except Exception:
        pass


class FallbackSink:
    """Wrap a sink and emit to stderr when the primary write fails."""

    def __init__(self, primary: Any) -> None:
        self._primary = primary

    @property
    def name(self) -> str:
        return _sink_name(self._primary)

    async def start(self) -> None:
        if hasattr(self._primary, "start"):
            await self._primary.start()

    async def stop(self) -> None:
        if hasattr(self._primary, "stop"):
            await self._primary.stop()

    async def write(
        self,
        entry: dict[str, Any],
        *,
        redact_mode: RedactMode = "minimal",
    ) -> None:
        try:
            await self._primary.write(entry)
        except Exception as exc:
            await handle_sink_write_failure(
                entry,
                sink=self._primary,
                error=exc,
                serialized=False,
                redact_mode=redact_mode,
            )

    async def write_serialized(
        self,
        view: Any,
        *,
        redact_mode: RedactMode = "minimal",
    ) -> None:
        try:
            await self._primary.write_serialized(view)
        except AttributeError:
            return None
        except Exception as exc:
            await handle_sink_write_failure(
                view,
                sink=self._primary,
                error=exc,
                serialized=True,
                redact_mode=redact_mode,
            )


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    FallbackSink,
    handle_sink_write_failure,
    _extract_bytes,
    _scrub_raw,
)
