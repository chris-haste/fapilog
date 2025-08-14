import asyncio
import io
import sys
from typing import Any

import pytest

# Skip this module if pytest-benchmark plugin is not available (e.g., in some CI tox envs)
pytest.importorskip("pytest_benchmark")

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.serialization import (
    convert_json_bytes_to_jsonl,
    serialize_mapping_to_json_bytes,
)
from fapilog.plugins.sinks.rotating_file import (
    RotatingFileSink,
    RotatingFileSinkConfig,
)
from fapilog.plugins.sinks.stdout_json import StdoutJsonSink


def test_serialize_mapping_benchmark(benchmark: Any) -> None:
    payload = {"a": 1, "b": "x" * 64, "c": {"n": 2}}

    def run() -> bytes:
        view = serialize_mapping_to_json_bytes(payload)
        seg = convert_json_bytes_to_jsonl(view)
        return seg.to_bytes()

    res = benchmark(run)
    # sanity
    assert res.endswith(b"\n")


def test_ring_queue_enqueue_dequeue_benchmark(benchmark: Any) -> None:
    q = NonBlockingRingQueue[int](capacity=65536)
    n = 10000

    def run() -> int:
        count = 0
        for i in range(n):
            ok = q.try_enqueue(i)
            if not ok:
                break
        for _ in range(n):
            ok, _val = q.try_dequeue()
            if not ok:
                break
            count += 1
        return count

    processed = benchmark(run)
    assert processed > 0


def test_stdout_sink_benchmark(benchmark: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Swap stdout to in-memory buffer to avoid console I/O
    class _Buf:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

    orig = sys.stdout
    sys.stdout = _Buf()  # type: ignore[assignment]
    try:
        sink = StdoutJsonSink()
        payload = {"a": 1, "b": "x" * 32}

        def run() -> None:
            asyncio.run(sink.write(payload))

        benchmark(run)
    finally:
        sys.stdout = orig


@pytest.mark.usefixtures("tmp_path")
def test_rotating_file_sink_benchmark(benchmark: Any, tmp_path: Any) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="bench",
        mode="json",
        max_bytes=10_000_000,  # avoid rotation during benchmark
        interval_seconds=None,
        compress_rotated=False,
    )

    async def write_n(n: int) -> None:
        sink = RotatingFileSink(cfg)
        await sink.start()
        try:
            for i in range(n):
                await sink.write({"i": i, "msg": "y" * 16})
        finally:
            await sink.stop()

    def run() -> None:
        asyncio.run(write_n(200))

    benchmark(run)
