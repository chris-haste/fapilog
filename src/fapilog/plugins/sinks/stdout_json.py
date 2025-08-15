from __future__ import annotations

import asyncio
import sys
from typing import Any

from ...core import diagnostics
from ...core.serialization import serialize_envelope


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
                    mode="strict" if strict else "best-effort",
                    reason=type(e).__name__,
                    detail=str(e),
                )
                if strict:
                    return None
                from ...core.serialization import serialize_mapping_to_json_bytes

                view = serialize_mapping_to_json_bytes(entry)
            # Coalesce write+newline+flush into a single to_thread call
            async with self._lock:

                def _write_line() -> None:
                    buf = sys.stdout.buffer
                    buf.write(view.data)
                    buf.write(b"\n")
                    buf.flush()

                await asyncio.to_thread(_write_line)
        except Exception:
            # Contain sink errors; do not propagate
            return None


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object] = (StdoutJsonSink,)

# Minimal plugin metadata for discovery compatibility
PLUGIN_METADATA = {
    "name": "stdout-json-sink",
    "version": "0.1.0",
    "plugin_type": "sink",
    "entry_point": __name__,
    "description": "Async stdout JSONL sink",
    "author": "Fapilog",
    "api_version": "1.0",
}
