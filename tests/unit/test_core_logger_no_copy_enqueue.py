from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade


@pytest.mark.asyncio
async def test_same_thread_enqueue_preserves_identity() -> None:
    seen: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        seen.append(entry)

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=8,
        batch_max_size=1,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=capture,
    )
    logger.start()

    sentinel = object()
    logger.info("m", sentinel=sentinel)
    await asyncio.sleep(0.05)
    await logger.stop_and_drain()

    assert seen, "expected at least one entry"
    meta = seen[0].get("metadata", {})
    # The sentinel is embedded under metadata.sentinel; ensure same identity
    assert meta.get("sentinel") is sentinel


def _cross_thread_submit(logger: SyncLoggerFacade, sentinel: object) -> None:
    # Submit from a different thread to exercise cross-thread path
    logger.info("x", marker=sentinel)


@pytest.mark.asyncio
async def test_cross_thread_enqueue_preserves_identity() -> None:
    seen: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        seen.append(entry)

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=8,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=capture,
    )
    logger.start()
    sentinel = object()
    # Submit from a thread
    await asyncio.to_thread(_cross_thread_submit, logger, sentinel)
    await asyncio.sleep(0.1)
    await logger.stop_and_drain()

    assert seen, "expected emitted entries"
    meta = seen[0].get("metadata", {})
    assert meta.get("marker") is sentinel
