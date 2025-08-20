from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from ...core import diagnostics
from ...core.serialization import (
    SerializedView,
    convert_json_bytes_to_jsonl,
    serialize_envelope,
)


class StdoutJsonSink:
    """Async-friendly stdout sink that writes structured JSON lines.

    - Accepts dict-like finalized entries and emits one JSON per line to stdout
    - Uses zero-copy serialization helpers
    - Never raises upstream; errors are contained
    """

    _lock: asyncio.Lock

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def start(self) -> None:  # lifecycle placeholder
        return None

    async def stop(self) -> None:  # lifecycle placeholder
        return None

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            try:
                view = serialize_envelope(entry)
            except Exception as e:
                # Strict vs best-effort behavior
                strict = False
                try:
                    from ...core import settings as _settings

                    strict = bool(_settings.Settings().core.strict_envelope_mode)
                except Exception:
                    strict = False
                diagnostics.warn(
                    "sink",
                    "envelope serialization error",
                    reason=type(e).__name__,
                    detail=str(e),
                    mode=("strict" if strict else "best"),
                )
                if strict:
                    return None
                from ...core.serialization import (
                    serialize_mapping_to_json_bytes,
                )

                view = serialize_mapping_to_json_bytes(entry)
            # Use segmented JSONL conversion to avoid copying
            segments = convert_json_bytes_to_jsonl(view)
            payload_segments: tuple[memoryview, ...] = tuple(
                segments.iter_memoryviews()
            )
            async with self._lock:

                def _write_segments() -> None:
                    # Prefer zero-copy vectored write if available
                    try:
                        if hasattr(os, "writev"):
                            fd = sys.stdout.buffer.fileno()
                            os.writev(fd, list(payload_segments))
                            return
                    except Exception:
                        # Fallback to buffered writes below
                        pass
                    buf = sys.stdout.buffer
                    try:
                        buf.writelines(payload_segments)
                    finally:
                        try:
                            buf.flush()
                        except Exception:
                            pass

                await asyncio.to_thread(_write_segments)
        except Exception:
            # Contain sink errors; do not propagate
            return None

    async def write_serialized(self, view: SerializedView) -> None:
        try:
            # Use segmented JSONL conversion to avoid copying
            segments = convert_json_bytes_to_jsonl(view)
            payload_segments: tuple[memoryview, ...] = tuple(
                segments.iter_memoryviews()
            )
            async with self._lock:

                def _write_segments() -> None:
                    # Prefer zero-copy vectored write if available
                    try:
                        if hasattr(os, "writev"):
                            fd = sys.stdout.buffer.fileno()
                            os.writev(fd, list(payload_segments))
                            return
                    except Exception:
                        # Fallback to buffered writes below
                        pass
                    buf = sys.stdout.buffer
                    try:
                        buf.writelines(payload_segments)
                    finally:
                        try:
                            buf.flush()
                        except Exception:
                            pass

                await asyncio.to_thread(_write_segments)
        except Exception:
            return None


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    StdoutJsonSink,
    StdoutJsonSink.write,  # vulture: used
    StdoutJsonSink.write_serialized,  # vulture: used
)

# Minimal plugin metadata for discovery compatibility
PLUGIN_METADATA = {
    "name": "stdout-json-sink",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": __name__,
    "description": "Async stdout JSONL sink",
    "author": "Fapilog Core",
    "api_version": "1.0",
}
