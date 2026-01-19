from __future__ import annotations

import io
import sys
from unittest.mock import patch

import pytest

from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


@pytest.mark.asyncio
async def test_stdout_json_sink_strict_envelope_error_drops_line() -> None:
    # Force envelope to raise; sink with strict_envelope_mode=True should drop
    # Pre-configure diagnostics to avoid Settings() call in warn()
    import fapilog.core.diagnostics as diag

    diag.configure_diagnostics(enabled=True)
    diag._reset_for_tests()

    with patch(
        "fapilog.plugins.sinks.stdout_json.serialize_envelope",
        side_effect=TypeError("x"),
    ):
        buf = io.BytesIO()
        orig = sys.stdout
        sys.stdout = io.TextIOWrapper(buf, encoding="utf-8")  # type: ignore[assignment]
        try:
            # Pass strict_envelope_mode=True directly (Story 1.25 - config injection)
            sink = StdoutJsonSink(strict_envelope_mode=True)
            await sink.write({"a": 1})
            sys.stdout.flush()
            # No line should be written in strict mode on error
            data = buf.getvalue().decode("utf-8").splitlines()
            assert data == []
        finally:
            sys.stdout = orig  # type: ignore[assignment]
