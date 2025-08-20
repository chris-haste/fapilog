from __future__ import annotations

from pathlib import Path

import pytest

from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig


@pytest.mark.asyncio
async def test_rotating_file_sink_text_mode_writes_key_value_lines(
    tmp_path: Path,
) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="ut",
        mode="text",
        max_bytes=10_000_000,
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"b": 2, "a": 1})
        await sink.write({"msg": "hello", "ok": True})
    finally:
        await sink.stop()

    files = [p for p in tmp_path.iterdir() if p.is_file() and p.suffix == ".log"]
    assert files, "expected a .log file in text mode"
    text = files[0].read_text()
    lines = [ln for ln in text.splitlines() if ln]
    assert len(lines) == 2
    # Sorted keys ensure deterministic order
    assert lines[0] == "a=1 b=2"
    assert "msg=hello" in lines[1] and "ok=True" in lines[1]
