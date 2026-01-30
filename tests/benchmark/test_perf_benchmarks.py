import asyncio
import io
import os
import sys
import time
from typing import Any

import pytest

from conftest import get_test_timeout
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


# Story 12.23: Backpressure event signaling CPU benchmark


@pytest.mark.asyncio
async def test_backpressure_event_signaling_low_cpu() -> None:
    """Verify event-based waiting uses minimal CPU under sustained full-queue.

    This test validates AC4 from Story 12.23: CPU usage should be low when
    enqueuers are blocked waiting on a full queue, because we use asyncio.Event
    signaling instead of spin-waiting.

    The test runs multiple enqueuers waiting on a full queue and measures that
    the event loop is not busy-spinning (it yields control properly).
    """
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    # Fill the queue
    assert q.try_enqueue(0) is True

    n_waiters = 100
    wait_duration = 0.1  # seconds
    completed = 0
    timed_out = 0

    async def enqueue_waiter(value: int) -> None:
        nonlocal completed, timed_out
        try:
            await q.await_enqueue(value, timeout=wait_duration)
            completed += 1
        except Exception:
            timed_out += 1

    # Start many waiting enqueuers - they should all block efficiently
    start = time.perf_counter()
    tasks = [asyncio.create_task(enqueue_waiter(i)) for i in range(1, n_waiters + 1)]

    # Let them wait for the duration
    await asyncio.sleep(wait_duration + 0.05)

    # All should have timed out (queue never has space)
    await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    # Key validation: elapsed time should be close to wait_duration
    # If spin-waiting, elapsed would be much longer due to CPU contention
    # With event signaling, the event loop can sleep efficiently
    assert timed_out == n_waiters, (
        f"Expected all {n_waiters} to timeout, got {timed_out}"
    )
    assert completed == 0, "No enqueue should have succeeded"

    # Elapsed time should be reasonable (not spinning)
    # Allow some overhead but should complete within 3x the wait duration
    # Use get_test_timeout() to scale for CI environments
    max_elapsed = get_test_timeout(wait_duration * 3)
    assert elapsed < max_elapsed, (
        f"Elapsed {elapsed:.3f}s >> expected <{max_elapsed:.3f}s. "
        "Event signaling may not be working correctly."
    )
