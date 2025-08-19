from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade


@pytest.mark.asyncio
async def test_fastpath_serialize_in_flush_falls_back_on_error() -> None:
    collected: list[dict[str, Any]] = []
    attempted: dict[str, int] = {"serialized_calls": 0}

    async def _sink_write(entry: dict[str, Any]) -> None:
        collected.append(dict(entry))

    async def _sink_write_serialized(_view: object) -> None:
        # Simulate a sink that declares fast path but fails at runtime
        attempted["serialized_calls"] += 1
        raise RuntimeError("boom")

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=_sink_write,
        sink_write_serialized=_sink_write_serialized,
        enrichers=[],
        metrics=None,
        serialize_in_flush=True,
    )
    logger.start()
    logger.info("m", i=1)
    # Allow timeout-based flush
    await asyncio.sleep(0.05)
    await logger.stop_and_drain()

    # Fast path attempted, but fell back to dict write
    assert attempted["serialized_calls"] >= 1
    assert len(collected) == 1
