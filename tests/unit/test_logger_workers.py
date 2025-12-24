import asyncio

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


@pytest.mark.asyncio
async def test_sync_logger_respects_worker_count_in_loop():
    async def sink_write(entry: dict) -> None:
        return None

    logger = SyncLoggerFacade(
        name="loop",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink_write,
        num_workers=3,
    )
    logger.start()
    assert len(logger._worker_tasks) == 3
    await logger.stop_and_drain()


def test_sync_logger_respects_worker_count_thread_mode():
    async def sink_write(entry: dict) -> None:
        return None

    logger = SyncLoggerFacade(
        name="thread",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink_write,
        num_workers=2,
    )
    logger.start()
    assert len(logger._worker_tasks) == 2
    asyncio.run(logger.stop_and_drain())


@pytest.mark.asyncio
async def test_async_logger_respects_worker_count():
    async def sink_write(entry: dict) -> None:
        return None

    logger = AsyncLoggerFacade(
        name="async",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink_write,
        num_workers=4,
    )
    logger.start()
    assert len(logger._worker_tasks) == 4
    await logger.stop_and_drain()
