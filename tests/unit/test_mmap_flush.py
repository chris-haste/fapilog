from pathlib import Path

import pytest

from fapilog.plugins.sinks.mmap_persistence import MemoryMappedPersistence


@pytest.mark.asyncio
async def test_mmap_periodic_and_close_flush(tmp_path: Path):
    p = tmp_path / "data.log"
    async with MemoryMappedPersistence(
        p, initial_size_bytes=1024, growth_chunk_bytes=1024, periodic_flush_bytes=8
    ) as mm:
        # Write 8 bytes triggers periodic flush
        await mm.append(b"ABCDEFGH")
        # Append line and ensure offsets increase
        off, n = await mm.append_line(b"I")
        assert n >= 2 and off >= 8
    # Re-open and ensure file exists and has non-zero size
    assert p.exists() and p.stat().st_size > 0
