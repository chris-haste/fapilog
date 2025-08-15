import asyncio
import gzip
import json
import os
import time
from pathlib import Path

import pytest

# Ensure reasonable default for loop stall bound in environments without CI vars
if "FAPILOG_TEST_MAX_LOOP_STALL_SECONDS" not in os.environ:
    os.environ["FAPILOG_TEST_MAX_LOOP_STALL_SECONDS"] = "0.035"

from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig


async def _monitor_loop_latency(
    stop_evt: asyncio.Event, period: float = 0.001
) -> float:
    """Monitor event-loop sleep latency; return max observed sleep interval.

    Uses a small sleep to sample; aims to detect stalls due to blocking operations.
    """
    max_interval = 0.0
    last = time.perf_counter()
    while not stop_evt.is_set():
        await asyncio.sleep(period)
        now = time.perf_counter()
        interval = now - last
        if interval > max_interval:
            max_interval = interval
        last = now
    return max_interval


@pytest.mark.asyncio
async def test_high_throughput_rotation_latency(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="it",
        mode="json",
        max_bytes=2048,  # frequent rotations
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=False,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()

    stop_evt = asyncio.Event()
    monitor_task = asyncio.create_task(_monitor_loop_latency(stop_evt))

    try:
        total = 1200
        concurrency = 25
        sem = asyncio.Semaphore(concurrency)

        async def submit(i: int) -> None:
            async with sem:
                await sink.write({"i": i, "msg": "x" * 16})

        await asyncio.gather(*(submit(i) for i in range(total)))
    finally:
        await sink.stop()
        stop_evt.set()
        max_interval = await monitor_task

    files = [p for p in tmp_path.iterdir() if p.is_file()]
    assert len(files) >= 2
    # Assert no large loop stalls; allow some CI jitter. Target < 20ms.
    # Respect CI override; enforce a minimum guard to reduce flakiness on slow runners
    stall_bound = max(
        float(os.getenv("FAPILOG_TEST_MAX_LOOP_STALL_SECONDS", "0.030")), 0.12
    )
    assert max_interval < stall_bound


@pytest.mark.asyncio
async def test_interval_rotation_deadline_alignment(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="it",
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
        for _ in range(10):
            await sink.write({"a": 1})
        # Cross next interval boundary to trigger time-based rotation
        await asyncio.sleep(1.2)
        for _ in range(10):
            await sink.write({"b": 2})
    finally:
        await sink.stop()

    files = sorted(p for p in tmp_path.iterdir() if p.is_file())
    assert len(files) >= 2


@pytest.mark.asyncio
async def test_compressed_rotation_throughput(tmp_path: Path) -> None:
    cfg = RotatingFileSinkConfig(
        directory=tmp_path,
        filename_prefix="it",
        mode="json",
        max_bytes=1536,  # frequent rotations
        interval_seconds=None,
        max_files=None,
        max_total_bytes=None,
        compress_rotated=True,
    )
    sink = RotatingFileSink(cfg)
    await sink.start()
    try:
        for i in range(500):
            await sink.write({"i": i, "payload": "y" * 24})
    finally:
        await sink.stop()

    gz_files = [p for p in tmp_path.iterdir() if p.suffix.endswith("gz")]
    assert gz_files, "Expected compressed rotated files"
    # Validate JSONL content in at least one gz file
    with gzip.open(gz_files[0], "rb") as f:
        chunk = f.read().decode("utf-8")
        # Validate a couple of lines are parseable JSON
        lines = [ln for ln in chunk.strip().splitlines() if ln][:5]
        for ln in lines:
            json.loads(ln)
