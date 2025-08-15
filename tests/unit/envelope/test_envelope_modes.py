from __future__ import annotations

import json
from unittest.mock import patch

from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


async def _capture_stdout_line(payload: dict) -> dict:
    import io
    import sys

    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
    try:
        sink = StdoutJsonSink()
        await sink.write(payload)
        sys.stdout.flush()
        line = buf.getvalue().decode("utf-8").splitlines()[0]
        return json.loads(line)
    finally:
        sys.stdout = orig  # type: ignore[assignment]


async def test_best_effort_mode_fallback_when_envelope_invalid() -> None:
    bad = {
        "timestamp": "not-a-timestamp",
        "level": "INFO",
        "message": "x",
        "context": {},
        "diagnostics": {},
    }
    with patch("fapilog.core.settings.Settings") as MockSettings:
        inst = MockSettings.return_value
        inst.core.strict_envelope_mode = False
        inst.core.internal_logging_enabled = False
        out = await _capture_stdout_line(bad)
        # In best-effort, we emit original mapping
        assert out == bad


async def test_strict_mode_drops_when_envelope_invalid() -> None:
    bad = {
        "timestamp": "not-a-timestamp",
        "level": "INFO",
        "message": "x",
        "context": {},
        "diagnostics": {},
    }
    with patch("fapilog.core.settings.Settings") as MockSettings:
        inst = MockSettings.return_value
        inst.core.strict_envelope_mode = True
        inst.core.internal_logging_enabled = False
        import io
        import sys

        buf = io.BytesIO()
        orig = sys.stdout
        sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
        try:
            sink = StdoutJsonSink()
            await sink.write(bad)
            sys.stdout.flush()
            text = buf.getvalue().decode("utf-8")
            assert text.strip() == ""
        finally:
            sys.stdout = orig  # type: ignore[assignment]
