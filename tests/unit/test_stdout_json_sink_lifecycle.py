from __future__ import annotations

import pytest

from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


@pytest.mark.asyncio
async def test_stdout_json_sink_start_stop_and_write() -> None:
    sink = StdoutJsonSink()
    await sink.start()
    # Minimal write path
    await sink.write({"level": "INFO", "message": "x"})
    await sink.stop()
