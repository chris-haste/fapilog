from __future__ import annotations

import io
import sys
from unittest.mock import patch

import pytest

from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


@pytest.mark.asyncio
async def test_stdout_json_sink_strict_envelope_error_drops_line() -> None:
    # Force envelope to raise and strict mode True so sink should drop
    with patch(
        "fapilog.plugins.sinks.stdout_json.serialize_envelope",
        side_effect=TypeError("x"),
    ):
        with patch("fapilog.core.settings.Settings") as MockSettings:
            cfg = MockSettings.return_value
            cfg.core.strict_envelope_mode = True

            buf = io.BytesIO()
            orig = sys.stdout
            sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
            try:
                sink = StdoutJsonSink()
                await sink.write({"a": 1})
                sys.stdout.flush()
                # No line should be written in strict mode on error
                data = buf.getvalue().decode("utf-8").splitlines()
                assert data == []
            finally:
                sys.stdout = orig  # type: ignore[assignment]
