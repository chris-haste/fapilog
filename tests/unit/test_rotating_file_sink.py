import asyncio
import gzip
import json
from pathlib import Path

import pytest

from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig


@pytest.mark.asyncio
async def test_json_size_rotation(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=100,  # very small to trigger rotation
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        # Write multiple entries to exceed 100 bytes
        for i in range(20):
            await sink.write({"i": i, "text": "x" * 10})
        await sink.stop()
    finally:
        await sink.stop()

    files = sorted(p.name for p in tmp_path.iterdir() if p.is_file())
    assert any(name.startswith("test-") and name.endswith(".jsonl") for name in files)
    # Expect multiple files due to rotation
    assert len(files) >= 2


@pytest.mark.asyncio
async def test_time_rotation(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=10_000_000,
        interval_seconds=1,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"a": 1})
        # Wait beyond interval boundary to trigger time rotation
        await asyncio.sleep(1.2)
        await sink.write({"b": 2})
        await sink.stop()
    finally:
        await sink.stop()

    files = sorted(p.name for p in tmp_path.iterdir() if p.is_file())
    assert len(files) >= 2


@pytest.mark.asyncio
async def test_retention_max_files(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=80,
        interval_seconds=None,
        max_files=2,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        for i in range(30):
            await sink.write({"i": i, "text": "x" * 10})
        await sink.stop()
    finally:
        await sink.stop()

    files = sorted(p for p in tmp_path.iterdir() if p.is_file())
    assert len(files) <= 2


@pytest.mark.asyncio
async def test_compression_and_integrity(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=50,
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=True,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"k": "v"})
        await sink.write({"k": "v2"})
        # Force rotation by size
        await sink.write({"k": "v3", "pad": "x" * 200})
        await sink.stop()
    finally:
        await sink.stop()

    gz_files = [p for p in tmp_path.iterdir() if p.suffix.endswith("gz")]
    assert gz_files, "Expected compressed rotated files"
    # Decompress and ensure JSON lines
    for gz in gz_files:
        with gzip.open(gz, "rb") as f:
            content = f.read().decode("utf-8")
            for line in content.strip().splitlines():
                json.loads(line)


@pytest.mark.asyncio
async def test_text_mode_and_collision_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force same timestamp for two consecutive file creations to test collision suffix
    fixed = 1_726_000_000.0
    times = [fixed, fixed, fixed + 2]

    def fake_time() -> float:
        return times.pop(0) if times else fixed + 3

    monkeypatch.setattr("time.time", fake_time)

    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="text",
        max_bytes=20,
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"b": 2, "a": 1})
        # Force rotation by size quickly
        await sink.write({"msg": "x" * 100})
        await sink.stop()
    finally:
        await sink.stop()

    names = sorted(p.name for p in tmp_path.iterdir())
    # At least two files, second one may have -1 suffix
    assert any(n.endswith(".log") for n in names)
    with open(tmp_path / names[-1], "rb") as f:
        last = f.read().decode("utf-8").strip()
        # deterministic order key=value separated by space
        assert "a=1" in last or "msg=" in last


@pytest.mark.asyncio
async def test_timestamp_collision_suffix_with_datetime_monkeypatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force datetime.now(UTC) to return the same second twice to trigger suffix -1
    from datetime import UTC as _REAL_UTC
    from datetime import datetime as _REAL_DT

    class _FakeDT:
        UTC = _REAL_UTC

        def __init__(self) -> None:
            self.calls = 0

        def now(self, tz):  # type: ignore[no-untyped-def]
            # Return same second for first two calls, then +2s
            self.calls += 1
            if self.calls <= 2:
                return _REAL_DT(2025, 1, 1, 12, 0, 0, tzinfo=tz)
            return _REAL_DT(2025, 1, 1, 12, 0, 2, tzinfo=tz)

    fake_dt = _FakeDT()
    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.datetime", fake_dt, raising=True
    )

    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=40,  # small to force rotation on second write
        interval_seconds=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"k": "v"})
        await sink.write({"k": "v2", "pad": "x" * 200})  # trigger rotation
        await sink.stop()
    finally:
        await sink.stop()

    names = sorted(p.name for p in tmp_path.iterdir() if p.is_file())
    # Expect two files in same timestamp, second with -1 suffix
    assert any(n.endswith(".jsonl") for n in names)
    assert any("-1.jsonl" in n for n in names)


@pytest.mark.asyncio
async def test_retention_with_compressed_files_max_files(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=60,
        interval_seconds=None,
        max_files=2,
        max_total_bytes=None,
        compress_rotated=True,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        for i in range(50):
            await sink.write({"i": i, "pad": "y" * 10})
        await sink.stop()
    finally:
        await sink.stop()

    gz_files = [p for p in tmp_path.iterdir() if p.suffix.endswith("gz")]
    # Only last couple of rotated files should remain compressed
    assert len(gz_files) <= 2
    # Active file (last) remains as .jsonl
    assert any(p.name.endswith(".jsonl") for p in tmp_path.iterdir())


@pytest.mark.asyncio
async def test_size_rotation_keeps_file_sizes_below_threshold(tmp_path: Path) -> None:
    limit = 200
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=limit,
        interval_seconds=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        for i in range(100):
            await sink.write({"i": i, "pad": "z" * 50})
        await sink.stop()
    finally:
        await sink.stop()

    for p in tmp_path.iterdir():
        if p.is_file() and p.name.endswith(".jsonl"):
            assert p.stat().st_size <= limit


@pytest.mark.asyncio
async def test_write_error_is_contained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenFile:
        def write(self, _seg):  # type: ignore[no-untyped-def]
            raise OSError("disk full")

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    async def fake_open_new(self) -> None:  # type: ignore[no-redef]
        self._active_path = Path(tmp_path / "broken.jsonl")
        self._active_file = BrokenFile()  # type: ignore[assignment]
        self._active_size = 0
        self._next_rotation_deadline = None

    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.RotatingFileSink._open_new_file",
        fake_open_new,
        raising=True,
    )

    sink = RotatingFileSink(
        RotatingFileSinkConfig(directory=tmp_path, max_bytes=1024, mode="json")
    )
    await sink.start()
    try:
        # Should not raise even if underlying write fails
        await sink.write({"a": 1})
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_flush_error_is_contained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FlushBrokenFile:
        def __init__(self) -> None:
            self._buf = bytearray()

        def write(self, seg):  # type: ignore[no-untyped-def]
            # seg is a memoryview; accept and append
            self._buf.extend(seg)

        def flush(self) -> None:
            raise OSError("flush failed")

        def close(self) -> None:
            pass

    async def fake_open_new(self) -> None:  # type: ignore[no-redef]
        self._active_path = Path(tmp_path / "flushbroken.jsonl")
        self._active_file = FlushBrokenFile()  # type: ignore[assignment]
        self._active_size = 0
        self._next_rotation_deadline = None

    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.RotatingFileSink._open_new_file",
        fake_open_new,
        raising=True,
    )

    sink = RotatingFileSink(
        RotatingFileSinkConfig(directory=tmp_path, max_bytes=1024, mode="json")
    )
    await sink.start()
    try:
        # Should not raise even if flush fails
        await sink.write({"a": 1})
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_retention_max_total_bytes(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=60,
        interval_seconds=None,
        max_files=None,
        max_total_bytes=300,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        for i in range(100):
            await sink.write({"i": i, "txt": "y" * 8})
        await sink.stop()
    finally:
        await sink.stop()

    files = [p for p in tmp_path.iterdir() if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    assert total <= 300


@pytest.mark.asyncio
async def test_nested_directory_creation(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    cfg = RotatingFileSinkConfig(
        directory=nested,
        filename_prefix="test",
        mode="json",
        max_bytes=10_000,
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"x": 1})
        await sink.stop()
    finally:
        await sink.stop()

    assert nested.exists()
    files = [p for p in nested.iterdir() if p.is_file()]
    assert files, "Expected at least one file in nested directory"


@pytest.mark.asyncio
async def test_compression_failure_keeps_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("compress failed")

    monkeypatch.setattr(gzip, "open", boom)

    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=50,
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=True,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        await sink.write({"k": "v"})
        await sink.write({"k": "v2", "pad": "x" * 200})  # force rotation
        await sink.stop()
    finally:
        await sink.stop()

    # Compression failed; rotated original should remain as .jsonl
    names = [p.name for p in tmp_path.iterdir() if p.is_file()]
    assert any(n.endswith(".jsonl") for n in names)


@pytest.mark.asyncio
async def test_no_size_rotation_when_max_bytes_zero(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="test",
        mode="json",
        max_bytes=0,  # disabled size rotation
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        for i in range(50):
            await sink.write({"i": i, "pad": "z" * 200})
        await sink.stop()
    finally:
        await sink.stop()

    files = [p for p in tmp_path.iterdir() if p.is_file()]
    # Only the active file should be present (no rotations by size)
    assert len(files) == 1
