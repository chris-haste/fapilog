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
    """Verify that multi-worker drain processes all queued messages.

    Original bug: with worker_count=2, a single message would result in
    processed=0 because the empty-batch worker would finish first and
    trigger drain completion.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("num_workers", "num_messages", "batch_max_size"),
        [
            pytest.param(2, 1, 10, id="2-workers-1-msg"),
            pytest.param(2, 5, 10, id="2-workers-5-msgs"),
            pytest.param(4, 20, 5, id="4-workers-20-msgs"),
        ],
    )
    async def test_workers_process_all_messages(
        self, num_workers: int, num_messages: int, batch_max_size: int
    ) -> None:
        """All queued messages should be processed regardless of worker count."""
        sink_calls: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            sink_calls.append(entry)

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=batch_max_size,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink_write,
            num_workers=num_workers,
        )
        logger.start()

        for i in range(num_messages):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

        assert result.submitted == num_messages
        assert result.processed == num_messages
        assert len(sink_calls) == num_messages


class TestMultiWorkerDrainWaitsForAllWorkers:
    """Verify drain waits for ALL workers, not just the first to finish."""

    @pytest.mark.asyncio
    async def test_drain_waits_for_slow_worker(self) -> None:
        """Drain should wait for a slow worker even if fast workers finish first.

        This test creates a scenario where one worker has data (slow path)
        and another has none (fast path). Drain must wait for the slow one.

        Uses threading.Event for cross-thread coordination since the worker
        runs in a dedicated thread.
        """
        import threading

        sink_calls: list[dict[str, Any]] = []
        slow_sink_started = threading.Event()
        slow_sink_proceed = threading.Event()

        async def slow_sink_write(entry: dict[str, Any]) -> None:
            slow_sink_started.set()
            # Poll the threading event from the async worker
            while not slow_sink_proceed.is_set():
                await asyncio.sleep(0.01)
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
        slow_sink_started.wait(timeout=2.0)
        assert slow_sink_started.is_set()

        # Drain should NOT be done yet - slow worker is still processing
        await asyncio.sleep(0.05)
        assert not drain_task.done(), "Drain completed before slow worker finished"

        # Release the slow worker
        slow_sink_proceed.set()

        # Now drain should complete
        result = await asyncio.wait_for(drain_task, timeout=2.0)

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
        """Drain should complete even if a worker is stuck.

        With the unified thread architecture, drain joins the worker
        thread with a timeout. If a worker is stuck, the thread join
        times out but drain still returns a result.
        """
        import threading

        stuck = threading.Event()

        async def stuck_sink_write(entry: dict[str, Any]) -> None:
            stuck.set()
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

        # Wait for sink to start processing
        stuck.wait(timeout=2.0)
        await asyncio.sleep(0.05)

        # Drain via thread mode — should not hang indefinitely
        result = await asyncio.wait_for(
            logger.stop_and_drain(),
            timeout=10.0,
        )

        # Drain completed, didn't hang — message was submitted but stuck in sink
        assert result.submitted == 1
        assert result.processed + result.dropped == 1
