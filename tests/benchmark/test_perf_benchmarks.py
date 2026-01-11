import asyncio
import io
import os
import sys
import time
from typing import Any

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.serialization import (
    convert_json_bytes_to_jsonl,
    serialize_envelope,
    serialize_mapping_to_json_bytes,
)
from fapilog.plugins.sinks.rotating_file import (
    RotatingFileSink,
    RotatingFileSinkConfig,
)
from fapilog.plugins.sinks.stdout_json import StdoutJsonSink
from fapilog.plugins.sinks.stdout_pretty import StdoutPrettySink

# Skip this module if pytest-benchmark plugin is not available (e.g., in some CI tox envs)
pytest.importorskip("pytest_benchmark")

pytestmark = [pytest.mark.benchmark, pytest.mark.slow]


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


def test_stdout_pretty_format_benchmark(benchmark: Any) -> None:
    sink = StdoutPrettySink(colors=False)
    entry = {
        "timestamp": 1736605822.0,
        "level": "INFO",
        "message": "benchmark",
        "metadata": {"key": "value", "user": {"id": 123}},
    }

    result = benchmark(lambda: sink._format_pretty(entry))
    assert "benchmark" in result
    assert benchmark.stats.stats.mean < 0.0001


def test_stdout_pretty_vs_json_overhead() -> None:
    entry = {
        "timestamp": 1736605822.0,
        "level": "INFO",
        "message": "benchmark",
        "metadata": {"key": "value", "user": {"id": 123}},
    }
    envelope_entry = {
        "timestamp": entry["timestamp"],
        "level": entry["level"],
        "message": entry["message"],
        "context": entry["metadata"],
        "diagnostics": {},
    }
    pretty_sink = StdoutPrettySink(colors=False)
    n = 1000

    start = time.perf_counter()
    for _ in range(n):
        view = serialize_envelope(envelope_entry)
        convert_json_bytes_to_jsonl(view)
    json_mean = (time.perf_counter() - start) / n

    start = time.perf_counter()
    for _ in range(n):
        pretty_sink._format_pretty(entry)
    pretty_mean = (time.perf_counter() - start) / n

    multiplier = 2.0
    if os.getenv("COV_CORE_SOURCE") or os.getenv("COVERAGE_PROCESS_START"):
        # Coverage adds overhead; allow a wider threshold for this comparison.
        multiplier = 3.0
    else:
        try:
            import coverage as coverage_module
        except Exception:  # pragma: no cover - optional coverage detection
            coverage_module = None
        if coverage_module and coverage_module.Coverage.current() is not None:
            multiplier = 3.0
    assert pretty_mean < json_mean * multiplier


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
