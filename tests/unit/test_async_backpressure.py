"""Tests for async backpressure retry (Story 1.58).

AC2: Async facade implements backpressure with asyncio.sleep()
AC3: Async backpressure does not block the event loop
AC4: Protected levels bypass async backpressure
AC5: Async backpressure retry counter in DrainResult
AC6: drop_on_full=True behavior unchanged for async facade
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from fapilog.core.logger import AsyncLoggerFacade


def _make_async_logger(
    *,
    queue_capacity: int = 10,
    drop_on_full: bool = False,
    backpressure_wait_ms: int = 50,
    protected_levels: list[str] | None = None,
    sink_write: Any = None,
) -> AsyncLoggerFacade:
    """Create an AsyncLoggerFacade with a configurable sink."""
    if sink_write is None:
        sink_write = AsyncMock()
    return AsyncLoggerFacade(
        name="async-bp-test",
        queue_capacity=queue_capacity,
        batch_max_size=100,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=backpressure_wait_ms,
        drop_on_full=drop_on_full,
        sink_write=sink_write,
        protected_levels=protected_levels,
    )


def _blocking_sink() -> Any:
    """Create an async sink that blocks for 10s, keeping queue full."""

    async def sink(entry: dict[str, Any]) -> None:
        await asyncio.sleep(10)

    return sink


class TestAsyncBackpressureRetry:
    """AC2: Async facade retries with asyncio.sleep() when queue full."""

    @pytest.mark.asyncio
    async def test_retry_waits_when_queue_full(self) -> None:
        """When drop_on_full=False and queue is full, _enqueue retries with delay."""
        logger = _make_async_logger(
            queue_capacity=2,
            backpressure_wait_ms=30,
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = asyncio.get_event_loop().time()
        await logger._enqueue("INFO", "backpressure_event")
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        # Should have waited (not instant drop)
        assert elapsed_ms >= 15  # noqa: WA002 - timing assertion
        assert logger._dropped == 1

    @pytest.mark.asyncio
    async def test_retry_bounded_by_backpressure_wait_ms(self) -> None:
        """Retry loop does not exceed backpressure_wait_ms budget."""
        logger = _make_async_logger(
            queue_capacity=2,
            backpressure_wait_ms=20,
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = asyncio.get_event_loop().time()
        await logger._enqueue("INFO", "backpressure_event")
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        # Should not exceed budget by more than one sleep interval + tolerance
        assert elapsed_ms < 50
        assert elapsed_ms >= 15  # noqa: WA002 - timing assertion

    @pytest.mark.asyncio
    async def test_backpressure_wait_ms_zero_skips_retry(self) -> None:
        """backpressure_wait_ms=0 skips retry (same as sync behavior)."""
        logger = _make_async_logger(
            queue_capacity=2,
            backpressure_wait_ms=0,
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = asyncio.get_event_loop().time()
        await logger._enqueue("INFO", "zero_budget")
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        # Should drop instantly (budget is 0)
        assert elapsed_ms < 10
        assert logger._dropped == 1

    @pytest.mark.asyncio
    async def test_event_enqueued_after_retry_succeeds(self) -> None:
        """If space opens during retry, event is enqueued and counter incremented."""
        logger = _make_async_logger(queue_capacity=2, backpressure_wait_ms=200)
        logger.start = lambda: None  # type: ignore[assignment]

        logger._queue.try_enqueue({"level": "INFO", "message": "fill_0"})
        logger._queue.try_enqueue({"level": "INFO", "message": "fill_1"})

        # Free a slot after 20ms so retry succeeds mid-loop
        async def _free_slot() -> None:
            await asyncio.sleep(0.02)
            logger._queue.try_dequeue()

        task = asyncio.create_task(_free_slot())
        await logger._enqueue("INFO", "retry_event")
        await task

        assert logger._dropped == 0
        assert logger._backpressure_retries == 1


class TestAsyncNonBlocking:
    """AC3: Async backpressure does not block the event loop."""

    @pytest.mark.asyncio
    async def test_other_coroutines_progress_during_backpressure(self) -> None:
        """Other coroutines execute during async backpressure wait."""
        logger = _make_async_logger(
            queue_capacity=2,
            backpressure_wait_ms=50,
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        progress: list[int] = []

        async def background_task() -> None:
            for i in range(10):
                progress.append(i)
                await asyncio.sleep(0.001)

        task = asyncio.create_task(background_task())
        await logger._enqueue("INFO", "backpressure_event")
        await task

        # Background task made progress during backpressure wait
        assert len(progress) == 10


class TestAsyncProtectedLevelsBypass:
    """AC4: Protected levels bypass async backpressure."""

    @pytest.mark.asyncio
    async def test_protected_levels_bypass_backpressure(self) -> None:
        """Protected events skip the backpressure retry loop."""
        logger = _make_async_logger(
            queue_capacity=2,
            backpressure_wait_ms=100,
            protected_levels=["ERROR", "CRITICAL", "FATAL", "AUDIT", "SECURITY"],
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = asyncio.get_event_loop().time()
        # ERROR goes to protected queue via DualQueue, no backpressure
        await logger._enqueue("ERROR", "critical_event")
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        assert elapsed_ms < 10
        # Protected events route to protected queue — should not be dropped
        assert logger._dropped == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "level", ["ERROR", "CRITICAL", "FATAL", "AUDIT", "SECURITY"]
    )
    async def test_all_protected_levels_bypass(self, level: str) -> None:
        """All five default protected levels bypass async backpressure."""
        logger = _make_async_logger(
            queue_capacity=2,
            backpressure_wait_ms=100,
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = asyncio.get_event_loop().time()
        await logger._enqueue(level, "protected_event")
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        assert elapsed_ms < 10


class TestAsyncBackpressureRetryCounter:
    """AC5: Async backpressure retry counter in DrainResult."""

    @pytest.mark.asyncio
    async def test_backpressure_retries_incremented(self) -> None:
        """Async backpressure retries are counted."""
        logger = _make_async_logger(queue_capacity=2, backpressure_wait_ms=200)
        logger.start = lambda: None  # type: ignore[assignment]

        logger._queue.try_enqueue({"level": "INFO", "message": "fill_0"})
        logger._queue.try_enqueue({"level": "INFO", "message": "fill_1"})

        # Free a slot after 20ms
        async def _free_slot() -> None:
            await asyncio.sleep(0.02)
            logger._queue.try_dequeue()

        task = asyncio.create_task(_free_slot())
        await logger._enqueue("INFO", "retry_event")
        await task

        assert logger._backpressure_retries == 1


class TestAsyncDropOnFullTrue:
    """AC6: drop_on_full=True drops instantly for async facade."""

    @pytest.mark.asyncio
    async def test_drop_on_full_true_drops_instantly(self) -> None:
        """When drop_on_full=True, async facade drops immediately with no retry."""
        logger = _make_async_logger(
            queue_capacity=2,
            drop_on_full=True,
            backpressure_wait_ms=100,
            sink_write=_blocking_sink(),
        )
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = asyncio.get_event_loop().time()
        await logger._enqueue("INFO", "dropped_event")
        elapsed_ms = (asyncio.get_event_loop().time() - start) * 1000

        assert elapsed_ms < 10
        assert logger._dropped == 1
