from __future__ import annotations

import io
import json
import sys
from unittest.mock import patch

import pytest

from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


@pytest.mark.asyncio
async def test_stdout_json_sink_best_effort_envelope_error() -> None:
    # Force envelope to raise so best-effort path is taken
    with patch(
        "fapilog.plugins.sinks.stdout_json.serialize_envelope",
        side_effect=TypeError("x"),
    ):
        # Disable diagnostics output to stdout
        with patch("fapilog.core.settings.Settings") as MockSettings:
            cfg = MockSettings.return_value
            cfg.core.strict_envelope_mode = False
            cfg.core.internal_logging_enabled = False

            buf = io.BytesIO()
            orig = sys.stdout
            sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
            try:
                sink = StdoutJsonSink()
                payload = {"a": 1}
                await sink.write(payload)
                sys.stdout.flush()
                lines = buf.getvalue().decode("utf-8").splitlines()
                assert len(lines) == 1
                assert json.loads(lines[0]) == payload
            finally:
                sys.stdout = orig  # type: ignore[assignment]
