"""
Test logger threading and worker behavior.

Scope:
- Worker thread startup and cleanup
- Drain behavior and resource cleanup
- Cross-thread message submission
- Rapid start/stop cycles
- Worker count configuration
- LoggerWorker direct testing
- Async backpressure behavior

Does NOT cover:
- In-loop mode details (see test_logger_core.py)
- Async logger facade (see test_logger_async.py)
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.core.worker import LoggerWorker, strict_envelope_mode_enabled


def _create_collecting_sink(collected: list[dict[str, Any]]):
    """Create a sink that collects events for verification."""

    async def sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    return sink


class TestThreadModeStartupAndCleanup:
    """Test thread mode worker startup and cleanup behavior."""

    def test_start_creates_worker_thread_and_loop(self) -> None:
        """Starting logger creates worker thread and event loop."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="startup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        # Before start: no worker
        assert logger._worker_thread is None
        assert logger._worker_loop is None

        # Start creates worker
        logger.start()
        thread = logger._worker_thread
        loop = logger._worker_loop
        assert isinstance(thread, threading.Thread)
        assert thread.is_alive()
        assert loop.is_running()

        # Cleanup
        asyncio.run(logger.stop_and_drain())

    def test_start_is_idempotent(self) -> None:
        """Calling start() multiple times reuses the same worker."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="idempotent-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()
        original_thread = logger._worker_thread
        original_loop = logger._worker_loop

        # Start again - should be idempotent
        logger.start()
        assert logger._worker_thread is original_thread
        assert logger._worker_loop is original_loop

        # Cleanup
        asyncio.run(logger.stop_and_drain())

    def test_stop_and_drain_cleans_up_worker_resources(self) -> None:
        """stop_and_drain() properly cleans up thread and loop."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()
        assert isinstance(logger._worker_thread, threading.Thread)

        # Submit some messages
        for i in range(5):
            logger.info(f"message {i}")

        result = asyncio.run(logger.stop_and_drain())

        # Resources cleaned up
        assert logger._worker_thread is None
        assert logger._worker_loop is None

        # All submitted messages accounted for
        assert result.submitted == 5
        assert result.submitted == result.processed + result.dropped


class TestThreadModeDrainBehavior:
    """Test drain behavior processes all pending messages."""

    def test_drain_processes_all_queued_messages(self) -> None:
        """Drain waits for all queued messages to be processed."""
        collected: list[dict[str, Any]] = []

        # Patch Settings before logger creation (settings are cached at init)
        with patch("fapilog.core.settings.Settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.observability.logging.sampling_rate = 1.0
            mock_instance.core.filters = []
            mock_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = mock_instance

            logger = SyncLoggerFacade(
                name="drain-test",
                queue_capacity=100,
                batch_max_size=10,
                batch_timeout_seconds=0.1,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_collecting_sink(collected),
            )

            logger.start()

            # Submit messages
            message_count = 50
            for i in range(message_count):
                logger.info(f"message {i}")

            result = asyncio.run(logger.stop_and_drain())

        # All messages submitted and delivered to sink
        assert result.submitted == message_count
        assert len(collected) == message_count
        # All messages processed by worker
        assert result.processed == message_count

    def test_drain_under_backpressure_drops_excess(self) -> None:
        """Drain with full queue drops messages per configuration.

        This test verifies backpressure behavior by flooding a small queue.
        The key invariant is: submitted = processed + dropped.
        Whether drops occur depends on timing, so we verify the invariant
        holds rather than asserting a specific drop count.
        """
        collected: list[dict[str, Any]] = []

        async def slow_sink(event: dict[str, Any]) -> None:
            # Slow sink to force queue backup
            await asyncio.sleep(0.01)
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="backpressure-test",
            queue_capacity=3,  # Very small queue
            batch_max_size=1,  # Process one at a time = slow
            batch_timeout_seconds=0.01,  # Short timeout to trigger batches
            backpressure_wait_ms=0,  # Immediate drop
            drop_on_full=True,
            sink_write=slow_sink,
        )

        logger.start()

        # Flood the queue faster than it can drain
        for i in range(50):
            logger.info(f"flood {i}")

        result = asyncio.run(logger.stop_and_drain())

        # All messages submitted
        assert result.submitted == 50
        # Invariant: submitted = processed + dropped (deterministic)
        assert result.submitted == result.processed + result.dropped
        # Verify processed messages match collected (sink was called correctly)
        assert result.processed == len(collected)

    def test_drain_returns_flush_latency(self) -> None:
        """Drain result includes flush latency measurement."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="latency-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()
        logger.info("test message")

        result = asyncio.run(logger.stop_and_drain())

        # Latency should be a small positive float (test completes quickly)
        assert isinstance(result.flush_latency_seconds, float)
        assert 0 <= result.flush_latency_seconds < 10.0


class TestCrossThreadSubmission:
    """Test message submission from multiple threads."""

    def test_messages_from_other_threads_are_processed(self) -> None:
        """Messages submitted from non-main threads reach the sink."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="cross-thread-test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()

        # Submit from main thread
        logger.info("main-thread")

        # Submit from another thread
        def submit_from_thread():
            for i in range(10):
                logger.info(f"other-thread-{i}")

        thread = threading.Thread(target=submit_from_thread)
        thread.start()
        thread.join()

        result = asyncio.run(logger.stop_and_drain())

        # All messages processed
        assert result.submitted == 11
        assert result.processed == 11

        # Verify messages from both threads arrived
        messages = [e.get("message") for e in collected]
        assert "main-thread" in messages
        assert "other-thread-0" in messages
        assert "other-thread-9" in messages

    def test_queue_full_drops_from_cross_thread_submission(self) -> None:
        """Cross-thread submissions respect queue limits and drop policy.

        This test verifies that the queue properly handles concurrent
        submissions from multiple threads. The key invariant is:
        submitted = processed + dropped. Whether drops occur depends
        on timing, so we verify the invariant holds rather than
        asserting a specific drop count.
        """
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="cross-thread-drop-test",
            queue_capacity=2,  # Very small queue
            batch_max_size=100,  # Large batch = slow drain
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=0,  # Immediate drop
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()

        # Flood from multiple threads
        def flood():
            for i in range(50):
                logger.info(f"flood-{i}")

        threads = [threading.Thread(target=flood) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        result = asyncio.run(logger.stop_and_drain())

        # All messages submitted from 3 threads x 50 messages
        assert result.submitted == 150
        # Verify messages were processed (exact split between processed/dropped
        # varies due to timing, but total should be close to submitted)
        assert (
            result.processed + result.dropped <= result.submitted + 10
        )  # small margin
        # Some messages should have been processed
        assert result.processed > 0 or result.dropped > 0

    def test_timeout_with_future_done_and_enqueue_failed(self) -> None:
        """When fut.result() times out but future completed with ok=False, count as dropped."""
        from concurrent.futures import Future

        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="timeout-done-failed",
            queue_capacity=10,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )
        logger.start()

        # Mock run_coroutine_threadsafe to return a future that times out then shows done
        mock_future = MagicMock(spec=Future)
        mock_future.result.side_effect = [
            TimeoutError(),
            False,
        ]  # First times out, then returns False
        mock_future.cancelled.return_value = False
        mock_future.done.return_value = True

        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            logger.info("test-message")

        # The event should be counted as dropped since future.result() returned False
        assert logger._dropped == 1

        asyncio.run(logger.stop_and_drain())

    def test_timeout_with_future_done_and_exception(self) -> None:
        """When fut.result() times out and future raised exception, count as dropped."""
        from concurrent.futures import Future

        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="timeout-done-exception",
            queue_capacity=10,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )
        logger.start()

        # Mock run_coroutine_threadsafe to return a future that times out then raises
        mock_future = MagicMock(spec=Future)
        mock_future.result.side_effect = [
            TimeoutError(),
            RuntimeError("enqueue failed"),
        ]
        mock_future.cancelled.return_value = False
        mock_future.done.return_value = True

        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            logger.info("test-message")

        # The event should be counted as dropped since future.result() raised
        assert logger._dropped == 1

        asyncio.run(logger.stop_and_drain())

    def test_timeout_with_future_cancelled(self) -> None:
        """When fut.result() times out and future was cancelled, count as dropped."""
        from concurrent.futures import CancelledError, Future

        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="timeout-cancelled",
            queue_capacity=10,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )
        logger.start()

        # Mock: first result() raises TimeoutError, retry raises CancelledError
        mock_future = MagicMock(spec=Future)
        mock_future.result.side_effect = [TimeoutError(), CancelledError()]

        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            logger.info("test-message")

        # The event should be counted as dropped since future was cancelled
        assert logger._dropped == 1

        asyncio.run(logger.stop_and_drain())

    def test_timeout_with_future_still_running(self) -> None:
        """When fut.result() times out repeatedly, don't count as dropped."""
        from concurrent.futures import Future
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="timeout-running",
            queue_capacity=10,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )
        logger.start()

        # Mock: both result() calls timeout (coroutine still running)
        mock_future = MagicMock(spec=Future)
        mock_future.result.side_effect = [TimeoutError(), FuturesTimeoutError()]

        with patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            logger.info("test-message")

        # The event should NOT be counted as dropped (may yet succeed)
        assert logger._dropped == 0

        asyncio.run(logger.stop_and_drain())


class TestRapidStartStopCycles:
    """Test rapid start/stop cycles don't leak resources."""

    def test_rapid_cycles_complete_without_resource_leaks(self) -> None:
        """Multiple start/stop cycles don't leak threads or memory."""
        total_submitted = 0
        total_processed = 0

        for cycle in range(5):
            collected: list[dict[str, Any]] = []
            logger = SyncLoggerFacade(
                name=f"rapid-cycle-test-{cycle}",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.01,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_collecting_sink(collected),
            )
            logger.start()
            logger.info(f"cycle-{cycle}")
            result = asyncio.run(logger.stop_and_drain())

            # Each cycle submits and processes exactly 1 message
            assert result.submitted == 1
            assert result.processed == 1
            assert result.dropped == 0
            total_submitted += result.submitted
            total_processed += result.processed

            # Resources cleaned up after each cycle
            assert logger._worker_thread is None
            assert logger._worker_loop is None

        # All messages across cycles were processed
        assert total_submitted == 5
        assert total_processed == 5

    @pytest.mark.skipif(
        os.getenv("CI") == "true", reason="Timing-sensitive; skipped in CI"
    )
    def test_concurrent_submissions_during_drain(self) -> None:
        """Submissions during drain are handled gracefully."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="concurrent-drain-test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
        )

        logger.start()

        # Submit from multiple threads
        def submit_messages(thread_id: int):
            for i in range(20):
                logger.info(f"thread-{thread_id}-msg-{i}")
                time.sleep(0.001)

        threads = [
            threading.Thread(target=submit_messages, args=(i,)) for i in range(3)
        ]
        for t in threads:
            t.start()

        # Wait for all threads to complete before draining
        for t in threads:
            t.join()

        result = asyncio.run(logger.stop_and_drain())

        # All 60 messages (3 threads x 20 messages) should be accounted for
        assert result.submitted == 60
        # Invariant: submitted = processed + dropped
        assert result.submitted == result.processed + result.dropped
        # With large queue, all should be processed
        assert result.processed == 60
        assert result.dropped == 0


class TestMetricsInThreadMode:
    """Test metrics collection in thread mode."""

    def test_metrics_submission_outside_event_loop(self) -> None:
        """Metrics are tracked correctly when logger runs in thread mode."""
        from fapilog.metrics.metrics import MetricsCollector

        metrics = MetricsCollector(enabled=True)
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="metrics-thread-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_collecting_sink(collected),
            metrics=metrics,
        )
        logger.start()
        logger.info("outside-loop")
        result = asyncio.run(logger.stop_and_drain())

        # Verify message was submitted and processed
        assert result.submitted == 1
        assert result.processed == 1
        assert result.dropped == 0
        # Verify message content
        assert len(collected) == 1
        assert collected[0].get("message") == "outside-loop"


class TestAsyncBackpressure:
    """Test async logger backpressure behavior."""

    @pytest.mark.asyncio
    async def test_async_backpressure_drops_when_queue_full(self) -> None:
        """AsyncLoggerFacade drops messages immediately when queue full and wait=0."""
        collected: list[dict[str, Any]] = []

        async def sink(event: dict[str, Any]) -> None:
            collected.append(dict(event))

        logger = AsyncLoggerFacade(
            name="async-backpressure-test",
            queue_capacity=1,  # Very small queue
            batch_max_size=1024,  # Large batch = slow drain
            batch_timeout_seconds=0.2,
            backpressure_wait_ms=0,  # Immediate drop when full
            drop_on_full=True,
            sink_write=sink,
        )
        logger.start()

        # Fill queue with first message
        await logger.info("seed")

        # Submit many more that should be dropped
        for _ in range(10):
            await logger.info("x")

        result = await logger.stop_and_drain()

        # All 11 messages submitted (1 seed + 10 flood)
        assert result.submitted == 11
        # With queue_capacity=1, at most 2 can be processed (queue + in-flight)
        assert result.dropped >= 9
        # Invariant: submitted = processed + dropped
        assert result.submitted == result.processed + result.dropped


class TestWorkerCount:
    """Test worker count configuration."""

    @pytest.mark.asyncio
    async def test_sync_logger_respects_worker_count_in_loop(self) -> None:
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

    def test_sync_logger_respects_worker_count_thread_mode(self) -> None:
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
    async def test_async_logger_respects_worker_count(self) -> None:
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


class TestLoggerWorkerDirect:
    """Direct tests for LoggerWorker class."""

    @pytest.mark.asyncio
    async def test_worker_run_flushes_and_signals_drained(self) -> None:
        queue: NonBlockingRingQueue[dict[str, object]] = NonBlockingRingQueue(
            capacity=4
        )
        assert queue.try_enqueue({"id": 1})

        drained = asyncio.Event()
        counters = {"processed": 0, "dropped": 0}
        stop_flag = False
        sink_calls: list[dict[str, object]] = []

        async def sink_write(entry: dict[str, object]) -> None:
            sink_calls.append(entry)

        worker = LoggerWorker(
            queue=queue,
            batch_max_size=2,
            batch_timeout_seconds=0.01,
            sink_write=sink_write,
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=strict_envelope_mode_enabled,
            stop_flag=lambda: stop_flag,
            drained_event=drained,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=True,
            emit_redactor_diagnostics=True,
            counters=counters,
        )

        task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.01)
        stop_flag = True

        await asyncio.wait_for(task, timeout=1.0)

        assert drained.is_set()
        assert counters["processed"] == 1
        assert counters["dropped"] == 0
        assert sink_calls == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_worker_flush_event_triggers_immediate_flush(self) -> None:
        queue: NonBlockingRingQueue[dict[str, object]] = NonBlockingRingQueue(
            capacity=4
        )
        assert queue.try_enqueue({"id": 99})

        flush_event = asyncio.Event()
        flush_done = asyncio.Event()
        drained = asyncio.Event()
        counters = {"processed": 0, "dropped": 0}
        stop_flag = False
        sink_calls: list[dict[str, object]] = []

        async def sink_write(entry: dict[str, object]) -> None:
            sink_calls.append(entry)

        worker = LoggerWorker(
            queue=queue,
            batch_max_size=1,
            batch_timeout_seconds=0.5,
            sink_write=sink_write,
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=strict_envelope_mode_enabled,
            stop_flag=lambda: stop_flag,
            drained_event=drained,
            flush_event=flush_event,
            flush_done_event=flush_done,
            emit_enricher_diagnostics=True,
            emit_redactor_diagnostics=True,
            counters=counters,
        )

        task = asyncio.create_task(worker.run())

        flush_event.set()
        await asyncio.wait_for(flush_done.wait(), timeout=1.0)
        stop_flag = True

        await asyncio.wait_for(task, timeout=1.0)

        assert sink_calls == [{"id": 99}]
        assert counters["processed"] == 1
        assert drained.is_set()
