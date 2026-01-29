from __future__ import annotations

import asyncio
import io
import json
import sys
from typing import Any

import pytest

from fapilog.core.serialization import serialize_mapping_to_json_bytes
from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

has_writev = hasattr(__import__("os"), "writev")


def _swap_stdout_bytesio() -> tuple[io.BytesIO, Any]:
    buf = io.BytesIO()
    orig = sys.stdout
    sys.stdout = io.TextIOWrapper(
        buf,
        encoding="utf-8",
    )  # type: ignore[assignment]
    return buf, orig


@pytest.mark.asyncio
async def test_stdout_json_sink_writes_single_valid_json_line() -> None:
    buf, orig = _swap_stdout_bytesio()
    try:
        sink = StdoutJsonSink()
        payload = {"a": 1, "b": "x"}
        await sink.write(payload)
        sys.stdout.flush()
        data = buf.getvalue().decode("utf-8").splitlines()
        assert len(data) == 1
        parsed = json.loads(data[0])
        assert parsed == payload
    finally:
        sys.stdout = orig  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_stdout_json_sink_write_serialized() -> None:
    buf, orig = _swap_stdout_bytesio()
    try:
        sink = StdoutJsonSink()
        entry = {"a": 2}
        view = serialize_mapping_to_json_bytes(entry)
        await sink.write_serialized(view)
        sys.stdout.flush()
        data = buf.getvalue().decode("utf-8").splitlines()
        assert len(data) == 1
        parsed = json.loads(data[0])
        assert parsed == entry
    finally:
        sys.stdout = orig  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_stdout_json_sink_concurrent_writes_are_line_delimited() -> None:
    buf, orig = _swap_stdout_bytesio()
    try:
        sink = StdoutJsonSink()
        n = 25

        async def writer(i: int) -> None:
            await sink.write({"i": i})

        await asyncio.gather(*[writer(i) for i in range(n)])
        sys.stdout.flush()
        text = buf.getvalue().decode("utf-8")
        lines = text.splitlines()
        assert len(lines) == n
        # Validate all are proper JSON objects
        parsed = [json.loads(line) for line in lines]
        assert {p["i"] for p in parsed} == set(range(n))
    finally:
        sys.stdout = orig  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_stdout_json_sink_raises_sink_write_error_on_failure() -> None:
    class BrokenBuffer:
        # behavior check
        def write(self, _data: bytes) -> int:  # pragma: no cover
            raise RuntimeError("boom")

        def flush(self) -> None:  # pragma: no cover
            raise RuntimeError("boom")

    class BrokenStdout:
        def __init__(self) -> None:
            self.buffer = BrokenBuffer()

    from fapilog.core.errors import SinkWriteError

    orig = sys.stdout
    sys.stdout = BrokenStdout()  # type: ignore[assignment]
    try:
        sink = StdoutJsonSink()
        # Should raise SinkWriteError when stdout errors
        with pytest.raises(SinkWriteError) as exc_info:
            await sink.write({"x": 1})
        assert exc_info.value.context.plugin_name == "stdout_json"
        assert isinstance(exc_info.value.__cause__, Exception)
        assert "BrokenBuffer" in str(exc_info.value.__cause__)
    finally:
        sys.stdout = orig  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_capture_mode_enables_redirect_stdout() -> None:
    """AC1: capture_mode=True uses buffered writes capturable via sys.stdout."""
    buf, orig = _swap_stdout_bytesio()
    try:
        sink = StdoutJsonSink(capture_mode=True)
        payload = {"message": "test capture mode"}
        await sink.write(payload)
        sys.stdout.flush()
        output = buf.getvalue().decode("utf-8")
        assert "test capture mode" in output
        # Verify it's valid JSON
        parsed = json.loads(output.strip())
        assert parsed["message"] == "test capture mode"
    finally:
        sys.stdout = orig  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_capture_mode_write_serialized() -> None:
    """capture_mode also works for write_serialized()."""
    buf, orig = _swap_stdout_bytesio()
    try:
        sink = StdoutJsonSink(capture_mode=True)
        entry = {"data": "serialized capture"}
        view = serialize_mapping_to_json_bytes(entry)
        await sink.write_serialized(view)
        sys.stdout.flush()
        output = buf.getvalue().decode("utf-8")
        assert "serialized capture" in output
    finally:
        sys.stdout = orig  # type: ignore[assignment]


@pytest.mark.asyncio
@pytest.mark.skipif(not has_writev, reason="os.writev not available on this platform")
async def test_default_mode_uses_writev_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: Default behavior uses os.writev() for performance."""
    writev_called = False
    original_writev = __import__("os").writev

    def track_writev(fd: int, buffers: list[bytes]) -> int:
        nonlocal writev_called
        writev_called = True
        return original_writev(fd, buffers)

    monkeypatch.setattr("os.writev", track_writev)

    sink = StdoutJsonSink()  # capture_mode=False by default
    await sink.write({"default": "mode"})

    assert writev_called, "os.writev() should be called in default mode"


@pytest.mark.asyncio
@pytest.mark.skipif(not has_writev, reason="os.writev not available on this platform")
async def test_capture_mode_skips_writev(monkeypatch: pytest.MonkeyPatch) -> None:
    """capture_mode=True should skip os.writev() even when available."""
    writev_called = False

    def track_writev(fd: int, buffers: list[bytes]) -> int:
        nonlocal writev_called
        writev_called = True
        return 0

    monkeypatch.setattr("os.writev", track_writev)

    buf, orig = _swap_stdout_bytesio()
    try:
        sink = StdoutJsonSink(capture_mode=True)
        await sink.write({"capture": "mode"})
        sys.stdout.flush()
    finally:
        sys.stdout = orig  # type: ignore[assignment]

    assert not writev_called, "os.writev() should be skipped in capture mode"


@pytest.mark.asyncio
@pytest.mark.skipif(not has_writev, reason="os.writev not available on this platform")
async def test_write_serialized_default_uses_writev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """write_serialized() also uses os.writev() by default."""
    writev_called = False
    original_writev = __import__("os").writev

    def track_writev(fd: int, buffers: list[bytes]) -> int:
        nonlocal writev_called
        writev_called = True
        return original_writev(fd, buffers)

    monkeypatch.setattr("os.writev", track_writev)

    sink = StdoutJsonSink()  # capture_mode=False by default
    view = serialize_mapping_to_json_bytes({"serialized": "default"})
    await sink.write_serialized(view)

    assert writev_called, (
        "os.writev() should be called for write_serialized() in default mode"
    )
