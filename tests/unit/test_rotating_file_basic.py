"""
Tests for RotatingFileSink basic operations.

Scope:
- JSON size rotation
- Time rotation
- Text mode and collision suffix
- Timestamp collision suffix
- Nested directory creation
- Write serialized fast path
"""

import asyncio
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
    """Test collision suffix when files are created in the same second.

    This test patches datetime to always return the same timestamp,
    forcing the collision suffix (-1, -2, etc.) to be used when
    multiple files are created.
    """
    from datetime import datetime as _REAL_DT
    from datetime import timezone

    # Always return the same timestamp to force collision
    fixed_time = _REAL_DT(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    class _FakeDT:
        """Fake datetime that always returns the same timestamp."""

        UTC = timezone.utc

        @staticmethod
        def now(tz=None):  # type: ignore[no-untyped-def]
            # Always return the same second to force collision suffix
            return fixed_time.replace(tzinfo=tz)

    # Apply monkeypatch before creating sink
    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.datetime", _FakeDT, raising=True
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
    # Expect files - at least one should end with .jsonl
    assert any(n.endswith(".jsonl") for n in names), f"No .jsonl files found: {names}"
    # When timestamps collide, suffix should be added
    assert any("-1.jsonl" in n for n in names), (
        f"Expected collision suffix (-1) in filenames: {names}"
    )


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
