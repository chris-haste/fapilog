"""Tests for bounded backpressure retry (Story 1.53).

AC1: drop_on_full=False retries with bounded sleep before dropping
AC2: Protected levels bypass backpressure
AC3: drop_on_full=True drops instantly (no retry)
AC6: backpressure_retries counter tracked in DrainResult
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from fapilog.core.logger import DrainResult, SyncLoggerFacade


def _make_logger(
    *,
    queue_capacity: int = 10,
    drop_on_full: bool = False,
    backpressure_wait_ms: int = 50,
    protected_levels: list[str] | None = None,
    sink_write: Any = None,
) -> SyncLoggerFacade:
    """Create a SyncLoggerFacade with a configurable sink."""
    if sink_write is None:
        sink_write = AsyncMock()
    return SyncLoggerFacade(
        name="bp-test",
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


class TestBackpressureRetry:
    """AC1: Bounded backpressure retry for drop_on_full=False."""

    def test_retry_waits_when_queue_full(self) -> None:
        """When drop_on_full=False and queue is full, _enqueue retries with delay."""
        logger = _make_logger(
            queue_capacity=2,
            backpressure_wait_ms=30,
            sink_write=_blocking_sink(),
        )

        # Fill the queue BEFORE starting (no worker to drain)
        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        # _enqueue will call start() then try to enqueue into full queue
        start = time.monotonic()
        logger._enqueue("INFO", "backpressure_event")
        elapsed_ms = (time.monotonic() - start) * 1000

        # Should have waited at least a few ms (not instant drop)
        assert elapsed_ms >= 1.0  # noqa: WA002 - timing assertion, not count

    def test_retry_bounded_by_backpressure_wait_ms(self) -> None:
        """Retry loop does not exceed backpressure_wait_ms budget."""
        logger = _make_logger(
            queue_capacity=2,
            backpressure_wait_ms=20,
            sink_write=_blocking_sink(),
        )

        # Fill queue before start
        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = time.monotonic()
        logger._enqueue("INFO", "backpressure_event")
        elapsed_ms = (time.monotonic() - start) * 1000

        # Should not exceed budget by more than one sleep interval (10ms cap + tolerance)
        assert elapsed_ms < 50

    def test_event_enqueued_after_retry_succeeds(self) -> None:
        """If space opens during retry, event is enqueued."""
        logger = _make_logger(queue_capacity=2, backpressure_wait_ms=100)

        # Fill queue then free one slot
        logger._queue.try_enqueue({"level": "INFO", "message": "fill_0"})
        logger._queue.try_enqueue({"level": "INFO", "message": "fill_1"})
        logger._queue.try_dequeue()

        logger._enqueue("INFO", "retry_event")

        # Event should have been enqueued (not dropped)
        assert logger._dropped == 0


class TestDropOnFullTrue:
    """AC3: drop_on_full=True drops immediately."""

    def test_drop_on_full_true_drops_instantly(self) -> None:
        """When drop_on_full=True, events are dropped immediately with no retry."""
        logger = _make_logger(
            queue_capacity=2,
            drop_on_full=True,
            backpressure_wait_ms=100,
            sink_write=_blocking_sink(),
        )

        # Fill queue before calling _enqueue.
        # Prevent worker from draining by mocking start() as no-op.
        logger.start = lambda: None  # type: ignore[assignment]

        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = time.monotonic()
        logger._enqueue("INFO", "dropped_event")
        elapsed_ms = (time.monotonic() - start) * 1000

        # Should be near-instant (no retry for drop_on_full=True)
        assert elapsed_ms < 50
        assert logger._dropped == 1


class TestProtectedLevelsBypassRetry:
    """AC2: Protected levels go to protected queue, bypass backpressure."""

    def test_protected_levels_enqueue_to_protected_queue(self) -> None:
        """Protected events (ERROR, CRITICAL) go to protected queue, not main."""
        logger = _make_logger(
            queue_capacity=2,
            backpressure_wait_ms=100,
            protected_levels=["ERROR", "CRITICAL"],
            sink_write=_blocking_sink(),
        )

        # Fill the MAIN queue
        for i in range(2):
            logger._queue.try_enqueue({"level": "INFO", "message": f"fill_{i}"})

        start = time.monotonic()
        logger._enqueue("ERROR", "critical_event")
        elapsed_ms = (time.monotonic() - start) * 1000

        # Protected events go to protected queue — no backpressure wait.
        # The enqueue should succeed quickly (DualQueue routes to protected queue).
        assert logger._dropped == 0
        # Should not have waited the full backpressure budget
        assert elapsed_ms < 50


class TestBackpressureRetryCounter:
    """AC6: Backpressure retries tracked in DrainResult."""

    def test_drain_result_has_backpressure_retries_field(self) -> None:
        """DrainResult includes backpressure_retries with default 0."""
        result = DrainResult(
            submitted=10,
            processed=10,
            dropped=0,
            retried=0,
            queue_depth_high_watermark=5,
            flush_latency_seconds=0.1,
        )
        assert result.backpressure_retries == 0

    @pytest.mark.asyncio
    async def test_backpressure_retries_zero_when_no_pressure(self) -> None:
        """DrainResult.backpressure_retries == 0 when queue never full."""
        logger = _make_logger(queue_capacity=100, backpressure_wait_ms=50)

        logger._enqueue("INFO", "normal_event")

        result = await logger.stop_and_drain()
        assert result.backpressure_retries == 0

    @pytest.mark.asyncio
    async def test_backpressure_retries_wired_to_drain_result(self) -> None:
        """DrainResult reflects the internal _backpressure_retries counter."""
        logger = _make_logger(queue_capacity=100, backpressure_wait_ms=50)
        logger._backpressure_retries = 42  # Simulate retries

        result = await logger.stop_and_drain()
        assert result.backpressure_retries == 42
