from __future__ import annotations

import asyncio
import io
import json
import sys
from typing import Any

import pytest

from fapilog.core.serialization import serialize_mapping_to_json_bytes
from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


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
async def test_stdout_json_sink_swallows_errors() -> None:
    class BrokenBuffer:
        # behavior check
        def write(self, _data: bytes) -> int:  # pragma: no cover
            raise RuntimeError("boom")

        def flush(self) -> None:  # pragma: no cover
            raise RuntimeError("boom")

    class BrokenStdout:
        def __init__(self) -> None:
            self.buffer = BrokenBuffer()

    orig = sys.stdout
    sys.stdout = BrokenStdout()  # type: ignore[assignment]
    try:
        sink = StdoutJsonSink()
        # Should not raise even if stdout errors
        await sink.write({"x": 1})
    finally:
        sys.stdout = orig  # type: ignore[assignment]
