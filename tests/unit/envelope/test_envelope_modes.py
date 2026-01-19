from __future__ import annotations

import io
import json
import sys
from typing import Any

from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


async def _capture_stdout_line(
    payload: dict[str, Any], *, strict_envelope_mode: bool = False
) -> dict[str, Any]:
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
    try:
        # Pass strict_envelope_mode directly (Story 1.25 - config injection)
        sink = StdoutJsonSink(strict_envelope_mode=strict_envelope_mode)
        await sink.write(payload)
        sys.stdout.flush()
        line = buf.getvalue().decode("utf-8").splitlines()[0]
        return json.loads(line)
    finally:
        sys.stdout = orig  # type: ignore[assignment]


async def test_best_effort_mode_fallback_when_envelope_invalid() -> None:
    """In best-effort mode (default), invalid envelopes fall back to raw mapping."""
    bad = {
        "timestamp": "not-a-timestamp",
        "level": "INFO",
        "message": "x",
        "context": {},
        "diagnostics": {},
    }
    # Best-effort mode (default strict_envelope_mode=False)
    out = await _capture_stdout_line(bad, strict_envelope_mode=False)
    # In best-effort, we emit original mapping
    assert out == bad


async def test_strict_mode_drops_when_envelope_invalid() -> None:
    """In strict mode, invalid envelopes are dropped (no output)."""
    bad = {
        "timestamp": "not-a-timestamp",
        "level": "INFO",
        "message": "x",
        "context": {},
        "diagnostics": {},
    }
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
    try:
        # Strict mode via constructor (Story 1.25 - config injection)
        sink = StdoutJsonSink(strict_envelope_mode=True)
        await sink.write(bad)
        sys.stdout.flush()
        text = buf.getvalue().decode("utf-8")
        assert text.strip() == ""
    finally:
        sys.stdout = orig  # type: ignore[assignment]
