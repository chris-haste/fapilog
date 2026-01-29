from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from ...core import diagnostics
from ...core.errors import SinkWriteError
from ...core.serialization import (
    SerializedView,
    convert_json_bytes_to_jsonl,
    serialize_envelope,
)


class StdoutJsonSink:
    """Async-friendly stdout sink that writes structured JSON lines.

    - Accepts dict-like finalized entries and emits one JSON per line to stdout
    - Uses zero-copy serialization helpers
    - Signals failures via SinkWriteError; core catches and triggers fallback

    Args:
        strict_envelope_mode: If True, drop entries that fail envelope
            serialization. If False, fall back to best-effort JSON.
        capture_mode: If True, skip os.writev() optimization and use buffered
            writes that can be captured via sys.stdout replacement. Useful for
            testing. Default False for production performance.
    """

    name = "stdout_json"
    _lock: asyncio.Lock

    def __init__(
        self, *, strict_envelope_mode: bool = False, capture_mode: bool = False
    ) -> None:
        self._lock = asyncio.Lock()
        self._strict_envelope_mode = strict_envelope_mode
        self._capture_mode = capture_mode

    async def start(self) -> None:  # lifecycle placeholder
        return None

    async def stop(self) -> None:  # lifecycle placeholder
        return None

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            try:
                view = serialize_envelope(entry)
            except Exception as e:
                # After Story 1.28: This exception path is now truly exceptional.
                # With v1.1 schema alignment, serialize_envelope() only fails for
                # non-JSON-serializable objects (e.g., custom classes, lambdas),
                # not schema mismatch.
                strict = self._strict_envelope_mode
                diagnostics.warn(
                    "sink",
                    "serialization error (non-serializable data)",
                    reason=type(e).__name__,
                    detail=str(e),
                    mode=("strict" if strict else "best-effort"),
                )
                if strict:
                    return None
                # Best-effort fallback for edge cases
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
                capture_mode = self._capture_mode

                def _write_segments() -> None:
                    # Prefer zero-copy vectored write if available (skip in capture mode)
                    if not capture_mode:
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
        except Exception as e:
            raise SinkWriteError(
                f"Failed to write to {self.name}",
                sink_name=self.name,
                cause=e,
            ) from e

    async def write_serialized(self, view: SerializedView) -> None:
        try:
            # Use segmented JSONL conversion to avoid copying
            segments = convert_json_bytes_to_jsonl(view)
            payload_segments: tuple[memoryview, ...] = tuple(
                segments.iter_memoryviews()
            )
            async with self._lock:
                capture_mode = self._capture_mode

                def _write_segments() -> None:
                    # Prefer zero-copy vectored write if available (skip in capture mode)
                    if not capture_mode:
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
        except Exception as e:
            raise SinkWriteError(
                f"Failed to write to {self.name}",
                sink_name=self.name,
                cause=e,
            ) from e

    async def health_check(self) -> bool:
        try:
            return bool(sys.stdout and sys.stdout.buffer.writable())
        except Exception:
            return False


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    StdoutJsonSink,
    StdoutJsonSink.write,  # vulture: used
    StdoutJsonSink.write_serialized,  # vulture: used
)

# Minimal plugin metadata for discovery compatibility
PLUGIN_METADATA = {
    "name": "stdout_json",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.stdout_json:StdoutJsonSink",
    "description": "Async stdout JSONL sink",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
