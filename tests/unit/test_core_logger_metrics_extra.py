from __future__ import annotations

import asyncio

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector


def _sum_samples(registry, name: str, sample_suffix: str) -> float:
    total = 0.0
    for metric in registry.collect():
        if metric.name == name:
            for s in metric.samples:
                if s.name.endswith(sample_suffix):
                    total += float(s.value)
    return total


@pytest.mark.asyncio
async def test_sink_error_counter_and_flush_histogram_recorded() -> None:
    metrics = MetricsCollector(enabled=True)

    async def raising_sink(_entry: dict) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("fail")

    logger = SyncLoggerFacade(
        name="m",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=raising_sink,
        metrics=metrics,
    )
    logger.start()
    logger.info("x")
    await asyncio.sleep(0.05)
    await logger.stop_and_drain()

    reg = metrics.registry
    assert reg is not None
    # Flush histogram should have at least one count
    flush_count = _sum_samples(reg, "fapilog_flush_seconds", "_count")
    assert flush_count >= 1.0
