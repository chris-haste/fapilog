"""Tests for multi-worker drain behavior.

This module tests that drain() correctly waits for ALL workers to complete,
not just the first one. This prevents a race condition where a worker with
an empty batch finishes before a worker processing actual messages.

Bug fixed: With multiple workers sharing a single drained_event, the first
worker to finish would set the event, causing drain to return before other
workers completed. This resulted in processed=0 even when messages were queued.

Fix: drain() now uses asyncio.gather() to wait for all worker tasks.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


class TestMultiWorkerDrainProcessesAllMessages:
    """Verify that multi-worker drain processes all queued messages."""

    @pytest.mark.asyncio
    async def test_two_workers_process_single_message(self) -> None:
        """With 2 workers and 1 message, drain should report processed=1.

        This was the original bug: with worker_count=2, a single message
        would result in processed=0 because the empty-batch worker would
        finish first and trigger drain completion.
        """
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=2,
        )
        logger.start()

        await logger.info("test message")
        result = await logger.stop_and_drain()

        assert result.submitted == 1
        assert result.processed == 1
        assert len(sink_calls) == 1

    @pytest.mark.asyncio
    async def test_two_workers_process_multiple_messages(self) -> None:
        """With 2 workers and multiple messages, all should be processed."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=2,
        )
        logger.start()

        for i in range(5):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

        assert result.submitted == 5
        assert result.processed == 5
        assert len(sink_calls) == 5

    @pytest.mark.asyncio
    async def test_four_workers_process_all_messages(self) -> None:
        """With 4 workers and many messages, all should be processed."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=5,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=4,
        )
        logger.start()

        for i in range(20):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

        assert result.submitted == 20
        assert result.processed == 20
        assert len(sink_calls) == 20


class TestMultiWorkerDrainWaitsForAllWorkers:
    """Verify drain waits for ALL workers, not just the first to finish."""

    @pytest.mark.asyncio
    async def test_drain_waits_for_slow_worker(self) -> None:
        """Drain should wait for a slow worker even if fast workers finish first.

        This test creates a scenario where one worker has data (slow path)
        and another has none (fast path). Drain must wait for the slow one.
        """
        sink_calls: list[dict[str, Any]] = []
        slow_sink_started = asyncio.Event()
        slow_sink_proceed = asyncio.Event()

        async def slow_sink_write(entry: dict[str, Any]) -> None:
            slow_sink_started.set()
            await slow_sink_proceed.wait()  # Wait for test to release
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=slow_sink_write,
            num_workers=2,
        )
        logger.start()

        await logger.info("slow message")

        # Start drain in background
        drain_task = asyncio.create_task(logger.stop_and_drain())

        # Wait for slow sink to start processing
        await asyncio.wait_for(slow_sink_started.wait(), timeout=1.0)

        # Drain should NOT be done yet - slow worker is still processing
        await asyncio.sleep(0.05)
        assert not drain_task.done(), "Drain completed before slow worker finished"

        # Release the slow worker
        slow_sink_proceed.set()

        # Now drain should complete
        result = await asyncio.wait_for(drain_task, timeout=1.0)

        assert result.processed == 1
        assert len(sink_calls) == 1

    @pytest.mark.asyncio
    async def test_counters_accurate_after_multiworker_drain(self) -> None:
        """Counters should reflect all workers' processing, not just first."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            # Add small delay to increase chance of race condition
            await asyncio.sleep(0.001)
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=2,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=3,
        )
        logger.start()

        # Log enough messages to distribute across workers
        for i in range(10):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

        # The key assertion: processed should equal submitted
        assert result.processed == result.submitted
        assert result.processed == 10
        assert len(sink_calls) == 10


class TestSyncLoggerMultiWorkerDrain:
    """Test multi-worker drain with sync logger facade."""

    @pytest.mark.asyncio
    async def test_sync_logger_two_workers_process_all(self) -> None:
        """Sync logger with 2 workers should process all messages."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=2,
        )
        logger.start()

        logger.info("message 1")
        logger.info("message 2")
        logger.info("message 3")

        result = await logger.stop_and_drain()

        assert result.submitted == 3
        assert result.processed == 3
        assert len(sink_calls) == 3


class TestMultiWorkerQueueDraining:
    """Test that queue is fully drained by workers during shutdown."""

    @pytest.mark.asyncio
    async def test_all_workers_drain_shared_queue(self) -> None:
        """Multiple workers should collectively drain the entire queue."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=5,
            batch_timeout_seconds=0.5,  # Long timeout to ensure drain handles it
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=2,
        )
        logger.start()

        # Enqueue messages
        for i in range(8):
            await logger.info(f"message {i}")

        # Drain immediately - workers should drain remaining queue items
        result = await logger.stop_and_drain()

        assert result.submitted == 8
        assert result.processed == 8
        # Queue should be empty
        assert logger._queue.is_empty()

    @pytest.mark.asyncio
    async def test_rapid_drain_after_burst(self) -> None:
        """Rapid drain after message burst should not lose messages."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        for _ in range(5):  # Run multiple times to catch race conditions
            logger = AsyncLoggerFacade(
                name="test",
                queue_capacity=100,
                batch_max_size=10,
                batch_timeout_seconds=0.1,
                backpressure_wait_ms=10,
                drop_on_full=True,
                sink_write=sink_write,
                num_workers=2,
            )
            logger.start()
            sink_calls.clear()

            # Burst of messages
            for i in range(10):
                await logger.info(f"burst message {i}")

            # Immediate drain
            result = await logger.stop_and_drain()

            assert result.submitted == 10, (
                f"Expected 10 submitted, got {result.submitted}"
            )
            assert result.processed == 10, (
                f"Expected 10 processed, got {result.processed}"
            )
            assert len(sink_calls) == 10, (
                f"Expected 10 sink calls, got {len(sink_calls)}"
            )


class TestMultiWorkerDrainTimeout:
    """Test drain timeout behavior with multiple workers."""

    @pytest.mark.asyncio
    async def test_drain_timeout_with_stuck_worker(self) -> None:
        """Drain should respect timeout even if a worker is stuck."""
        stuck_event = asyncio.Event()

        async def stuck_sink_write(entry: dict[str, Any]) -> None:
            stuck_event.set()
            await asyncio.sleep(10)  # Stuck for 10 seconds

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=stuck_sink_write,
            num_workers=2,
        )
        logger.start()

        await logger.info("will get stuck")

        # Wait for sink to start
        await asyncio.wait_for(stuck_event.wait(), timeout=1.0)

        # Drain with short timeout - should not hang
        result = await asyncio.wait_for(
            logger._drain_on_loop(timeout=0.1, warn_on_timeout=False),
            timeout=1.0,
        )

        # Drain completed (possibly with timeout), didn't hang
        assert result is not None  # noqa: WA003
        assert result.submitted == 1
