from __future__ import annotations

import json
import sys
from typing import Any, Literal

from ...core import diagnostics
from ...core.defaults import FALLBACK_SENSITIVE_FIELDS, should_fallback_sink

# Type alias for redact mode
RedactMode = Literal["inherit", "minimal", "none"]


def minimal_redact(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply minimal redaction for fallback safety.

    Masks values of keys that match FALLBACK_SENSITIVE_FIELDS (case-insensitive).
    Recursively processes nested dictionaries but not lists.

    Args:
        payload: The dictionary to redact.

    Returns:
        A new dictionary with sensitive fields masked as "***".
    """
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in FALLBACK_SENSITIVE_FIELDS:
            result[key] = "***"
        elif isinstance(value, dict):
            result[key] = minimal_redact(value)
        else:
            result[key] = value
    return result


def _sink_name(sink: Any) -> str:
    return getattr(sink, "name", type(sink).__name__)


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
) -> None:
    """Write payload to stderr with optional redaction.

    Args:
        payload: The payload to write.
        serialized: Whether the payload is already serialized.
        redact_mode: Redaction mode - "minimal" (default), "inherit", or "none".
    """
    # Apply redaction for dict payloads when not serialized
    if not serialized and isinstance(payload, dict):
        if redact_mode == "minimal":
            payload = minimal_redact(payload)
        # "inherit" mode is handled at a higher level (requires pipeline context)
        # "none" mode passes through without redaction

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
)
