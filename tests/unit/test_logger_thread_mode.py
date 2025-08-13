from __future__ import annotations

import asyncio
from typing import Any

from fapilog.core.logger import SyncLoggerFacade


def test_thread_mode_drain() -> None:
    collected: list[dict[str, Any]] = []

    async def collect(entry: dict[str, Any]) -> None:
        collected.append(entry)

    logger = SyncLoggerFacade(
        name="thread",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=collect,
    )
    # Start in thread mode (no running loop here)
    logger.start()
    for i in range(6):
        logger.info("item", i=i)
    res = asyncio.run(logger.stop_and_drain())
    assert res.submitted == 6
    assert res.processed == 6
    assert res.dropped == 0
