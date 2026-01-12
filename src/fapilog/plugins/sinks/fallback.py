from __future__ import annotations

import json
import sys
from typing import Any

from ...core import diagnostics
from ...core.defaults import should_fallback_sink


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


def _write_to_stderr(payload: Any, *, serialized: bool) -> None:
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
) -> None:
    if not should_fallback_sink(True):
        return

    sink_label = _sink_name(sink)
    error_type = type(error).__name__
    try:
        _write_to_stderr(payload, serialized=serialized)
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

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            await self._primary.write(entry)
        except Exception as exc:
            await handle_sink_write_failure(
                entry,
                sink=self._primary,
                error=exc,
                serialized=False,
            )

    async def write_serialized(self, view: Any) -> None:
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
            )


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    FallbackSink,
    handle_sink_write_failure,
)
