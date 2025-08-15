import asyncio
import os
import time
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.sinks.rotating_file import (
    RotatingFileSink,
    RotatingFileSinkConfig,
)


async def _monitor_loop_latency(
    stop_evt: asyncio.Event, period: float = 0.001
) -> float:
    """Monitor event-loop sleep latency; return max observed interval."""
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


def _get_counter(registry: Any, base_name: str) -> float:
    """Fetch a Counter value from prometheus_client registry.

    Handles the `_total` sample suffix automatically (even if base already
    ends with `_total`).
    """
    for metric in registry.collect():
        if metric.name == base_name:
            for s in metric.samples:
                if s.name.endswith("_total") and not s.labels:
                    return float(s.value)
    return 0.0


def _get_gauge(registry: Any, base_name: str) -> float:
    for metric in registry.collect():
        if metric.name == base_name:
            for s in metric.samples:
                if s.name == base_name and not s.labels:
                    return float(s.value)
    return 0.0


def _get_hist_count_sum(registry: Any, base_name: str) -> tuple[int, float]:
    count = 0
    total = 0.0
    for metric in registry.collect():
        if metric.name == base_name:
            for s in metric.samples:
                if s.name == base_name + "_count":
                    count = int(s.value)
                elif s.name == base_name + "_sum":
                    total = float(s.value)
    return count, total


@pytest.mark.asyncio
async def test_load_metrics_with_drops_and_stall_bounds(tmp_path) -> None:
    # Metrics enabled to collect counters/histograms
    metrics = MetricsCollector(enabled=True)
    sink = RotatingFileSink(
        RotatingFileSinkConfig(
            directory=tmp_path,
            filename_prefix="load",
            mode="json",
            max_bytes=1_000_000,
            interval_seconds=None,
            compress_rotated=False,
        )
    )
    await sink.start()

    logger = SyncLoggerFacade(
        name="load-test",
        queue_capacity=16,  # very small to induce contention
        batch_max_size=32,
        batch_timeout_seconds=0.002,
        backpressure_wait_ms=0,  # immediate drop on full
        drop_on_full=True,  # allow drops under pressure
        sink_write=sink.write,
        metrics=metrics,
    )

    stop_evt = asyncio.Event()
    monitor_task = asyncio.create_task(_monitor_loop_latency(stop_evt))

    # Produce a burst of events on a background thread to stress the queue
    total = 20_000

    def _produce() -> None:
        for i in range(total):
            logger.info("msg", idx=i)

    try:
        await asyncio.to_thread(_produce)
    finally:
        drain = await logger.stop_and_drain()
        await sink.stop()
        stop_evt.set()
        max_interval = await monitor_task

    # Assert loop stall within tolerance (no long blocking from sink/rotation)
    # Allow override via env in CI; default 0.20s for shared runners
    stall_bound = float(os.getenv("FAPILOG_TEST_MAX_LOOP_STALL_SECONDS", "0.20"))
    assert max_interval < stall_bound

    # Metrics assertions
    reg = metrics.registry
    assert reg is not None
    dropped = _get_counter(reg, "fapilog_events_dropped_total")
    flush_count, flush_sum = _get_hist_count_sum(reg, "fapilog_flush_seconds")
    q_hwm = _get_gauge(reg, "fapilog_queue_high_watermark")

    # Expect some drops and non-zero flushes
    # Accept either metrics-reported drops or logger drain drops to reduce
    # flakiness
    assert (dropped > 0) or (drain.dropped > 0)
    assert flush_count > 0
    assert q_hwm >= 1

    # Average flush latency should be sane; allow override via env
    avg_flush = (flush_sum / flush_count) if flush_count else 0.0
    flush_bound = float(os.getenv("FAPILOG_TEST_MAX_AVG_FLUSH_SECONDS", "0.30"))
    assert avg_flush < flush_bound


@pytest.mark.asyncio
async def test_load_metrics_no_drops_and_low_latency(tmp_path) -> None:
    metrics = MetricsCollector(enabled=True)
    sink = RotatingFileSink(
        RotatingFileSinkConfig(
            directory=tmp_path,
            filename_prefix="load",
            mode="json",
            max_bytes=5_000_000,
            interval_seconds=None,
            compress_rotated=False,
        )
    )
    await sink.start()

    logger = SyncLoggerFacade(
        name="load-test",
        queue_capacity=8_192,  # ample capacity to avoid drops
        batch_max_size=64,
        batch_timeout_seconds=0.010,
        backpressure_wait_ms=5,
        drop_on_full=False,
        sink_write=sink.write,
        metrics=metrics,
    )

    stop_evt = asyncio.Event()
    monitor_task = asyncio.create_task(_monitor_loop_latency(stop_evt))

    total = 5_000

    def _produce() -> None:
        for i in range(total):
            logger.info("ok", n=i)

    try:
        await asyncio.to_thread(_produce)
    finally:
        drain = await logger.stop_and_drain()
        await sink.stop()
        stop_evt.set()
        max_interval = await monitor_task

    # No drops expected
    assert drain.dropped == 0
    stall_bound = float(os.getenv("FAPILOG_TEST_MAX_LOOP_STALL_SECONDS", "0.20"))
    assert max_interval < stall_bound

    reg = metrics.registry
    assert reg is not None
    dropped = _get_counter(reg, "fapilog_events_dropped_total")
    flush_count, flush_sum = _get_hist_count_sum(reg, "fapilog_flush_seconds")

    assert dropped == 0
    assert flush_count > 0
    avg_flush = (flush_sum / flush_count) if flush_count else 0.0
    flush_bound = float(os.getenv("FAPILOG_TEST_MAX_AVG_FLUSH_SECONDS", "0.30"))
    assert avg_flush < flush_bound
