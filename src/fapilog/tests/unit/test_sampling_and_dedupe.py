from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade


@pytest.mark.asyncio
async def test_probabilistic_sampling_drops_within_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collected: list[dict[str, Any]] = []

    # Force a fixed sampling rate via env
    monkeypatch.setenv("FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE", "0.25")

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=4096,
        batch_max_size=1024,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()

    total = 2000
    for i in range(total):
        logger.info("m", i=i)

    res = await logger.stop_and_drain()
    # Expect about 25% retained; allow generous margin due to randomness
    retained_ratio = res.processed / total if total else 0.0
    assert 0.15 <= retained_ratio <= 0.35


@pytest.mark.asyncio
async def test_error_dedupe_suppresses_repeats(monkeypatch: pytest.MonkeyPatch) -> None:
    collected: list[dict[str, Any]] = []

    # Short window to make the test snappy
    monkeypatch.setenv("FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS", "0.2")

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=1024,
        batch_max_size=256,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()

    for _ in range(50):
        logger.error("same-error")

    await asyncio.sleep(0.25)
    # New window; one more should pass and roll the summary of suppressed
    logger.error("same-error")
    res = await logger.stop_and_drain()

    # Only two processed (one at start of each window)
    assert res.processed == 2
    assert res.submitted >= 2
