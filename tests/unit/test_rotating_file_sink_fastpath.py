from __future__ import annotations

from pathlib import Path

import pytest

from fapilog.core.serialization import serialize_mapping_to_json_bytes
from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig


@pytest.mark.asyncio
async def test_write_serialized_ignored_in_text_mode(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="fp",
        mode="text",
        max_bytes=10_000,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        view = serialize_mapping_to_json_bytes({"a": 1})
        # Should not raise and should not write JSONL in text mode
        await sink.write_serialized(view)
        await sink.write({"a": 2})
    finally:
        await sink.stop()
    files = [p for p in tmp_path.iterdir() if p.is_file()]
    assert files
    with open(files[0], "rb") as f:
        text = f.read().decode("utf-8")
        # Only the regular text line should be present
        assert "a=2" in text
