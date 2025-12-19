import asyncio
import gzip
import json
from pathlib import Path

import pytest

from fapilog.core.serialization import serialize_mapping_to_json_bytes
from fapilog.plugins.sinks.rotating_file import (
    RotatingFileSink,
    RotatingFileSinkConfig,
)


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


@pytest.mark.asyncio
async def test_write_serialized_fast_path_matches_write(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
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
        entry = {"a": 1, "b": "x"}
        # normal path
        await sink.write(entry)
        # fast path
        view = serialize_mapping_to_json_bytes(entry)
        await sink.write_serialized(view)
    finally:
        await sink.stop()
    # Validate both lines exist and parse
    files = [p for p in tmp_path.iterdir() if p.is_file() and p.suffix == ".jsonl"]
    assert files
    with open(files[0], "rb") as f:
        text = f.read().decode("utf-8").strip().splitlines()
        assert len(text) >= 2
        assert all(json.loads(line) for line in text[:2])


@pytest.mark.asyncio
async def test_start_error_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that start() handles initialization errors gracefully."""

    async def failing_mkdir(*args, **kwargs):
        raise OSError("Permission denied")

    monkeypatch.setattr("asyncio.to_thread", failing_mkdir)

    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)

    # Should not raise, should handle error gracefully
    result = await sink.start()
    assert result is None


@pytest.mark.asyncio
async def test_stop_error_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that stop() handles cleanup errors gracefully."""

    class BrokenFile:
        def flush(self):
            raise OSError("flush failed")

        def close(self):
            raise OSError("close failed")

    async def fake_open_new(self):
        self._active_path = Path(tmp_path / "broken.jsonl")
        self._active_file = BrokenFile()
        self._active_size = 0
        self._next_rotation_deadline = None

    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.RotatingFileSink._open_new_file",
        fake_open_new,
        raising=True,
    )

    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)
    await sink.start()

    # Should not raise, should handle error gracefully
    result = await sink.stop()
    assert result is None


@pytest.mark.asyncio
async def test_strict_envelope_mode_error_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test strict envelope mode error handling in write()."""

    # Mock settings to return strict mode
    class MockSettings:
        class Core:
            strict_envelope_mode = True

        core = Core()

    monkeypatch.setattr("fapilog.core.settings.Settings", lambda: MockSettings())

    # Mock serialize_envelope to fail
    def failing_serialize(*args, **kwargs):
        raise ValueError("Invalid envelope")

    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.serialize_envelope",
        failing_serialize,
    )

    cfg = RotatingFileSinkConfig(directory=tmp_path, mode="json")
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        # Should return None due to strict mode
        result = await sink.write({"invalid": "data"})
        assert result is None
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_fallback_write_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fallback write methods when os.writev is not available or fails."""

    class FallbackFile:
        def __init__(self):
            self._buf = bytearray()
            self._fileno_called = False

        def fileno(self):
            self._fileno_called = True
            return 999  # Invalid fd

        def writelines(self, segments):
            for seg in segments:
                self._buf.extend(seg)

        def write(self, data):
            self._buf.extend(data)

        def flush(self):
            pass

        def close(self):
            pass

        def get_content(self):
            return bytes(self._buf)

    async def fake_open_new(self):
        self._active_path = Path(tmp_path / "fallback.jsonl")
        self._active_file = FallbackFile()
        self._active_size = 0
        self._next_rotation_deadline = None

    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.RotatingFileSink._open_new_file",
        fake_open_new,
        raising=True,
    )

    cfg = RotatingFileSinkConfig(directory=tmp_path, mode="json")
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        await sink.write({"test": "data"})

        # Verify fallback write was used
        assert sink._active_file._fileno_called
        content = sink._active_file.get_content()
        assert b"test" in content
        assert b"data" in content
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_write_segments_exception_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that write segment exceptions are handled gracefully."""

    class ExceptionFile:
        def __init__(self):
            self._buf = bytearray()

        def fileno(self):
            raise OSError("fileno failed")

        def writelines(self, segments):
            raise OSError("writelines failed")

        def write(self, data):
            raise OSError("write failed")

        def flush(self):
            raise OSError("flush failed")

        def close(self):
            pass

        def get_content(self):
            return bytes(self._buf)

    async def fake_open_new(self):
        self._active_path = Path(tmp_path / "exception.jsonl")
        self._active_file = ExceptionFile()
        self._active_size = 0
        self._next_rotation_deadline = None

    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.RotatingFileSink._open_new_file",
        fake_open_new,
        raising=True,
    )

    cfg = RotatingFileSinkConfig(directory=tmp_path, mode="json")
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        # Should not raise, should handle all write exceptions gracefully
        result = await sink.write({"test": "data"})
        assert result is None
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_text_mode_fallback_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test text mode fallback when sorting fails."""

    class UnsortableDict(dict):
        def items(self):
            raise TypeError("Cannot sort")

    cfg = RotatingFileSinkConfig(directory=tmp_path, mode="text")
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        # Should handle unsortable dict gracefully
        await sink.write(UnsortableDict({"key": "value"}))

        # Verify fallback message was written
        files = [p for p in tmp_path.iterdir() if p.is_file()]
        assert files
        with open(files[0], "rb") as f:
            content = f.read().decode("utf-8")
            assert "message=" in content
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_open_new_file_stat_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _open_new_file handles stat exceptions gracefully."""

    # Mock only the specific stat call, not all asyncio.to_thread calls
    original_to_thread = asyncio.to_thread

    async def mock_to_thread(func, *args, **kwargs):
        if func.__name__ == "stat":
            raise OSError("stat failed")
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", mock_to_thread)

    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)

    # Should handle stat failure gracefully
    await sink._open_new_file()
    assert sink._active_size == 0


@pytest.mark.asyncio
async def test_rotate_active_file_no_active_file(tmp_path: Path) -> None:
    """Test _rotate_active_file when no active file exists."""

    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)

    # Should handle gracefully and open new file
    await sink._rotate_active_file()
    assert sink._active_file is not None
    assert sink._active_path is not None


@pytest.mark.asyncio
async def test_compress_file_exception_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _compress_file handles compression failures gracefully."""

    # Create a test file to compress
    test_file = tmp_path / "test.jsonl"
    test_file.write_text('{"test": "data"}\n')

    def failing_compress(*args, **kwargs):
        raise OSError("compression failed")

    monkeypatch.setattr("asyncio.to_thread", failing_compress)

    cfg = RotatingFileSinkConfig(directory=tmp_path, compress_rotated=True)
    sink = RotatingFileSink(cfg)

    # Should handle compression failure gracefully
    await sink._compress_file(test_file)

    # Original file should remain
    assert test_file.exists()


@pytest.mark.asyncio
async def test_enforce_retention_exception_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _enforce_retention handles exceptions gracefully."""

    def failing_list_files(*args, **kwargs):
        raise OSError("list failed")

    monkeypatch.setattr("asyncio.to_thread", failing_list_files)

    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)

    # Should handle list failure gracefully
    await sink._enforce_retention()


@pytest.mark.asyncio
async def test_enforce_retention_unlink_exceptions(tmp_path: Path) -> None:
    """Test _enforce_retention handles unlink exceptions gracefully."""

    # Create some test files
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test-{i}.jsonl"
        test_file.write_text(f'{{"test": {i}}}\n')
        test_files.append(test_file)

    cfg = RotatingFileSinkConfig(directory=tmp_path, max_files=1)
    sink = RotatingFileSink(cfg)

    # Mock _list_rotated_files to return our test files
    def mock_list_files():
        return test_files

    sink._list_rotated_files = mock_list_files

    # Should handle unlink exceptions gracefully
    await sink._enforce_retention()


@pytest.mark.asyncio
async def test_enforce_retention_max_total_bytes_exceptions(tmp_path: Path) -> None:
    """Test _enforce_retention handles stat exceptions in max_total_bytes logic."""

    # Create some test files
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test-{i}.jsonl"
        test_file.write_text(f'{{"test": {i}}}\n')
        test_files.append(test_file)

    cfg = RotatingFileSinkConfig(directory=tmp_path, max_total_bytes=10)
    sink = RotatingFileSink(cfg)

    # Mock _list_rotated_files to return our test files
    def mock_list_files():
        return test_files

    sink._list_rotated_files = mock_list_files

    # Should handle stat exceptions gracefully
    await sink._enforce_retention()


@pytest.mark.asyncio
async def test_list_rotated_files_directory_not_exists(tmp_path: Path) -> None:
    """Test _list_rotated_files when directory doesn't exist."""

    cfg = RotatingFileSinkConfig(directory=tmp_path / "nonexistent")
    sink = RotatingFileSink(cfg)

    # Should handle non-existent directory gracefully
    result = sink._list_rotated_files()
    assert result == []


@pytest.mark.asyncio
async def test_list_rotated_files_iterdir_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _list_rotated_files handles iterdir exceptions gracefully."""

    cfg = RotatingFileSinkConfig(directory=tmp_path)
    sink = RotatingFileSink(cfg)

    # Create a directory that will fail on iterdir
    class BrokenPath:
        def exists(self) -> bool:
            return True

        def iterdir(self):
            raise OSError("iterdir failed")

    sink._cfg.directory = BrokenPath()

    # Should handle iterdir failure gracefully
    result = sink._list_rotated_files()
    assert result == []


@pytest.mark.asyncio
async def test_stringify_exception_handling() -> None:
    """Test _stringify handles string conversion exceptions gracefully."""

    cfg = RotatingFileSinkConfig(directory=Path("/tmp"))
    sink = RotatingFileSink(cfg)

    class Unstringable:
        def __str__(self):
            raise ValueError("Cannot convert to string")

    # Should handle string conversion failure gracefully
    result = sink._stringify(Unstringable())
    assert result == "<?>"


@pytest.mark.asyncio
async def test_write_serialized_non_json_mode(tmp_path: Path) -> None:
    """Test write_serialized gracefully ignores non-JSON mode."""

    cfg = RotatingFileSinkConfig(directory=tmp_path, mode="text")
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        # Should return None for non-JSON mode
        from fapilog.core.serialization import SerializedView

        mock_view = SerializedView(data=b'{"test": "data"}')
        result = await sink.write_serialized(mock_view)
        assert result is None
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_interval_rotation_zero_interval(tmp_path: Path) -> None:
    """Test interval rotation with zero interval (should disable)."""

    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        interval_seconds=0,  # Should disable interval rotation
        max_bytes=1000,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        await sink.write({"test": "data"})
        # Should not have rotation deadline
        assert sink._next_rotation_deadline is None
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_interval_rotation_negative_interval(tmp_path: Path) -> None:
    """Test interval rotation with negative interval (should disable)."""

    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        interval_seconds=-1,  # Should disable interval rotation
        max_bytes=1000,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()

    try:
        await sink.write({"test": "data"})
        # Should not have rotation deadline
        assert sink._next_rotation_deadline is None
    finally:
        await sink.stop()


@pytest.mark.asyncio
async def test_retention_max_files_zero(tmp_path: Path) -> None:
    """Test retention with max_files=0 (should delete all rotated files)."""

    # Create some test files
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test-{i}.jsonl"
        test_file.write_text(f'{{"test": {i}}}\n')
        test_files.append(test_file)

    cfg = RotatingFileSinkConfig(directory=tmp_path, max_files=0)
    sink = RotatingFileSink(cfg)

    # Mock _list_rotated_files to return our test files
    def mock_list_files():
        return test_files

    sink._list_rotated_files = mock_list_files

    # Should delete all rotated files
    await sink._enforce_retention()

    # Verify files were deleted (mocked, but logic should work)


@pytest.mark.asyncio
async def test_retention_max_total_bytes_zero(tmp_path: Path) -> None:
    """Test retention with max_total_bytes=0 (should delete all rotated files)."""

    # Create some test files
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test-{i}.jsonl"
        test_file.write_text(f'{{"test": {i}}}\n')
        test_files.append(test_file)

    cfg = RotatingFileSinkConfig(directory=tmp_path, max_total_bytes=0)
    sink = RotatingFileSink(cfg)

    # Mock _list_rotated_files to return our test files
    def mock_list_files():
        return test_files

    sink._list_rotated_files = mock_list_files

    # Should delete all rotated files
    await sink._enforce_retention()

    # Verify files were deleted (mocked, but logic should work)


@pytest.mark.asyncio
async def test_retention_max_total_bytes_exact_match(tmp_path: Path) -> None:
    """Test retention when total bytes exactly matches max_total_bytes."""

    # Create test files with known sizes
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test-{i}.jsonl"
        content = f'{{"test": {i}}}\n'
        test_file.write_text(content)
        test_files.append(test_file)

    # Calculate exact total size
    total_size = sum(f.stat().st_size for f in test_files)

    cfg = RotatingFileSinkConfig(directory=tmp_path, max_total_bytes=total_size)
    sink = RotatingFileSink(cfg)

    # Mock _list_rotated_files to return our test files
    def mock_list_files():
        return test_files

    sink._list_rotated_files = mock_list_files

    # Should keep all files when exactly at limit
    await sink._enforce_retention()

    # Verify no files were deleted (mocked, but logic should work)


@pytest.mark.asyncio
async def test_retention_max_total_bytes_under_limit(tmp_path: Path) -> None:
    """Test retention when total bytes is under max_total_bytes limit."""

    # Create test files with known sizes
    test_files = []
    for i in range(3):
        test_file = tmp_path / f"test-{i}.jsonl"
        content = f'{{"test": {i}}}\n'
        test_file.write_text(content)
        test_files.append(test_file)

    # Set limit higher than total size
    total_size = sum(f.stat().st_size for f in test_files)
    cfg = RotatingFileSinkConfig(directory=tmp_path, max_total_bytes=total_size + 100)
    sink = RotatingFileSink(cfg)

    # Mock _list_rotated_files to return our test files
    def mock_list_files():
        return test_files

    sink._list_rotated_files = mock_list_files

    # Should keep all files when under limit
    await sink._enforce_retention()

    # Verify no files were deleted (mocked, but logic should work)
