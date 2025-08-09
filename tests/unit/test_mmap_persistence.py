import asyncio
from pathlib import Path

import pytest

from fapilog.core.events import LogEvent
from fapilog.core.serialization import serialize_mapping_to_json_bytes
from fapilog.plugins.sinks import MemoryMappedPersistence


@pytest.mark.asyncio
async def test_append_and_stats(tmp_path: Path) -> None:
    target = tmp_path / "logs.jsonl"
    async with MemoryMappedPersistence(
        target,
        initial_size_bytes=1024,
    ) as sink:
        event = LogEvent(level="INFO", message="hello", metadata={"a": 1})
        view = serialize_mapping_to_json_bytes(event.to_mapping())
        off, n = await sink.append_line(view.view)
        assert off == 0
        assert n > 0

        stats = await sink.stats()
        assert stats.file_size_bytes >= 1024
        assert stats.write_offset == n

    # Verify file includes a newline and contains expected message key
    content = target.read_bytes()
    assert content.endswith(b"\n")
    # Simple sanity: ensure it contains expected key
    assert b'"message":"hello"' in content


@pytest.mark.asyncio
async def test_grows_when_needed(tmp_path: Path) -> None:
    target = tmp_path / "logs.jsonl"
    # Very small initial size to force growth
    async with MemoryMappedPersistence(
        target,
        initial_size_bytes=64,
        growth_chunk_bytes=64,
    ) as sink:
        payload = b"x" * 200
        off1, n1 = await sink.append(payload)
        assert off1 == 0 and n1 == 200
        stats = await sink.stats()
        assert stats.file_size_bytes >= 200


@pytest.mark.asyncio
async def test_concurrent_appends(tmp_path: Path) -> None:
    target = tmp_path / "logs.jsonl"
    sink = MemoryMappedPersistence(target, initial_size_bytes=128)
    await sink.open()

    async def write_line(i: int) -> int:
        evt = LogEvent(level="DEBUG", message=f"m{i}")
        view = serialize_mapping_to_json_bytes(evt.to_mapping())
        _, n = await sink.append_line(view.view)
        return n

    sizes = await asyncio.gather(*(write_line(i) for i in range(10)))
    assert all(s > 0 for s in sizes)
    await sink.close()
