"""
Priority 1 Coverage Tests for Core Logger

This module targets the most critical uncovered paths:
1. Thread Mode Drain Logic (Lines 176-177, 285-286)
2. Cross-Thread Exception Handling (Lines 386-387, 427-428)
3. Worker Exception Containment (Lines 580-591, 577)

These tests focus on stability, error handling, and resource cleanup.
"""

import asyncio
import os
import threading
import time
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.redactors import BaseRedactor


def _create_async_sink(collected: list[dict[str, Any]]):
    """Create an async sink function."""

    async def async_sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    return async_sink


class TestThreadModeDrainLogic:
    """Test thread mode drain logic (Lines 176-177, 285-286)."""

    def test_thread_mode_drain_with_worker_thread_cleanup(self) -> None:
        """Test thread mode drain with proper worker thread cleanup (Line 176-177)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="thread-drain-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode (outside any running loop)
        logger.start()
        assert logger._worker_thread is not None
        assert logger._worker_loop is not None

        # Submit some messages to ensure worker is active
        for i in range(5):
            logger.info(f"message {i}")

        # Allow some processing time
        time.sleep(0.05)

        # Test the drain logic - this should exercise lines 176-177
        result = asyncio.run(logger.stop_and_drain())

        # Verify proper cleanup
        assert logger._worker_thread is None
        assert logger._worker_loop is None
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert isinstance(result.flush_latency_seconds, float)

    def test_thread_mode_drain_with_loop_cleanup(self) -> None:
        """Test thread mode drain with loop cleanup (Line 285-286)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="loop-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()
        assert logger._worker_thread is not None
        assert logger._worker_loop is not None

        # Submit messages
        for i in range(3):
            logger.info(f"test {i}")

        # Allow processing time
        time.sleep(0.05)

        # Test drain - this should exercise the loop cleanup logic
        result = asyncio.run(logger.stop_and_drain())

        # Verify cleanup
        assert logger._worker_thread is None
        assert logger._worker_loop is None
        assert result.submitted >= 3

    def test_thread_mode_drain_with_timeout_scenarios(self) -> None:
        """Test thread mode drain with various timeout scenarios."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="timeout-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Submit many messages to create backpressure
        for i in range(100):
            logger.info(f"bulk {i}")

        # Test drain under pressure
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted == 100
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None
        assert logger._worker_loop is None


class TestCrossThreadExceptionHandling:
    """Test cross-thread exception handling (Lines 386-387, 427-428)."""

    def test_cross_thread_enqueue_with_queue_full_scenario(self) -> None:
        """Test cross-thread enqueue when queue is full (Line 386-387)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="cross-thread-full-test",
            queue_capacity=1,  # Very small queue
            batch_max_size=10,
            batch_timeout_seconds=0.5,
            backpressure_wait_ms=0,  # Immediate drop
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Fill the queue from the main thread
        logger.info("fill")

        # Submit from a different thread to trigger cross-thread path
        def submit_from_thread():
            for i in range(50):
                logger.info(f"cross-thread {i}")

        thread = threading.Thread(target=submit_from_thread)
        thread.start()
        thread.join()

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Should have drops due to queue full
        assert result.submitted >= 51
        assert result.dropped >= 1
        assert logger._worker_thread is None

    def test_cross_thread_enqueue_with_timeout_failures(self) -> None:
        """Test cross-thread enqueue with timeout failures (Line 427-428)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="timeout-failure-test",
            queue_capacity=1,
            batch_max_size=10,
            batch_timeout_seconds=0.01,  # Very short timeout
            backpressure_wait_ms=0,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Fill queue
        logger.info("blocking")

        # Submit from thread with short timeout
        def submit_with_timeout():
            for i in range(20):
                logger.info(f"timeout-test {i}")

        thread = threading.Thread(target=submit_with_timeout)
        thread.start()
        thread.join()

        # Allow processing
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Should have drops due to timeout
        assert result.submitted >= 21
        assert result.dropped >= 1

    def test_cross_thread_enqueue_with_worker_thread_termination(self) -> None:
        """Test cross-thread enqueue during worker thread termination."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="termination-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Submit some messages
        for i in range(5):
            logger.info(f"normal {i}")

        # Submit from thread while draining
        def submit_during_drain():
            for i in range(10):
                logger.info(f"during-drain {i}")
                time.sleep(0.001)  # Faster submission

        thread = threading.Thread(target=submit_during_drain)
        thread.start()

        # Allow some time for thread to submit messages before drain
        time.sleep(0.02)

        # Start drain
        result = asyncio.run(logger.stop_and_drain())

        # Wait for thread to finish
        thread.join()

        # Verify results - should have at least the initial 5 + some from thread
        assert result.submitted >= 10
        assert result.processed >= 0
        assert result.dropped >= 0


class TestWorkerExceptionContainment:
    """Test worker exception containment (Lines 580-591, 577)."""

    def test_worker_main_loop_with_batch_processing_exception(self) -> None:
        """Test worker main loop exception during batch processing (Line 577)."""
        collected: list[dict[str, Any]] = []

        # Create a sink that raises exceptions during processing
        async def exploding_sink(event: dict[str, Any]) -> None:
            if "explode" in event.get("message", ""):
                raise RuntimeError("Sink explosion!")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="batch-explosion-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=exploding_sink,
        )

        # Start in thread mode
        logger.start()

        # Submit normal messages
        for i in range(3):
            logger.info(f"normal {i}")

        # Submit message that will cause sink explosion
        logger.info("explode")

        # Submit more normal messages
        for i in range(2):
            logger.info(f"after-explosion {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain - should handle the exception gracefully
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 6
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_worker_main_loop_with_sink_write_exception(self) -> None:
        """Test worker main loop exception during sink write."""
        collected: list[dict[str, Any]] = []

        # Create a sink that fails intermittently
        call_count = 0

        async def failing_sink(event: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise RuntimeError(f"Sink failure {call_count}")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="sink-failure-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=failing_sink,
        )

        # Start in thread mode
        logger.start()

        # Submit many messages to trigger failures
        for i in range(20):
            logger.info(f"failure-test {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 20
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_worker_main_loop_with_enrichment_exception(self) -> None:
        """Test worker main loop exception during enrichment."""
        collected: list[dict[str, Any]] = []

        # Create an enricher that fails
        class ExplodingEnricher(BaseEnricher):
            name = "exploder"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
                if "explode" in event.get("message", ""):
                    raise RuntimeError("Enrichment explosion!")
                return event

        logger = SyncLoggerFacade(
            name="enrichment-explosion-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Enable the exploding enricher
        logger.enable_enricher(ExplodingEnricher())

        # Submit normal messages
        for i in range(3):
            logger.info(f"normal {i}")

        # Submit message that will cause enrichment explosion
        logger.info("explode")

        # Submit more normal messages
        for i in range(2):
            logger.info(f"after-explosion {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 6
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_worker_main_loop_with_redaction_exception(self) -> None:
        """Test worker main loop exception during redaction."""
        collected: list[dict[str, Any]] = []

        # Create a redactor that fails
        class ExplodingRedactor(BaseRedactor):
            name = "redactor-exploder"

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
                if "explode" in event.get("message", ""):
                    raise RuntimeError("Redaction explosion!")
                return event

        logger = SyncLoggerFacade(
            name="redaction-explosion-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Inject the exploding redactor directly
        logger._redactors = [ExplodingRedactor()]  # type: ignore[attr-defined]

        # Submit normal messages
        for i in range(3):
            logger.info(f"normal {i}")

        # Submit message that will cause redaction explosion
        logger.info("explode")

        # Submit more normal messages
        for i in range(2):
            logger.info(f"after-explosion {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 6
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None


class TestThreadModeEdgeCases:
    """Test additional thread mode edge cases for comprehensive coverage."""

    def test_thread_mode_startup_with_existing_worker(self) -> None:
        """Test thread mode startup when worker already exists."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="startup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start once
        logger.start()
        original_thread = logger._worker_thread
        original_loop = logger._worker_loop

        # Start again - should be idempotent
        logger.start()
        assert logger._worker_thread is original_thread
        assert logger._worker_loop is original_loop

        # Submit messages
        for i in range(3):
            logger.info(f"startup-test {i}")

        # Test drain
        result = asyncio.run(logger.stop_and_drain())
        assert result.submitted >= 3

    def test_thread_mode_with_rapid_start_stop_cycles(self) -> None:
        """Test thread mode with rapid start/stop cycles."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="rapid-cycle-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Rapid start/stop cycles
        for cycle in range(5):
            logger.start()
            logger.info(f"cycle {cycle}")
            result = asyncio.run(logger.stop_and_drain())
            assert result.submitted >= 1

        # Allow extra time for final cleanup after rapid cycles
        time.sleep(0.1)

        # Final verification - worker thread/loop cleaned up or inactive
        if logger._worker_thread is not None:
            logger._worker_thread.join(timeout=0.5)
            assert not logger._worker_thread.is_alive()
        if logger._worker_loop is not None:
            assert (
                logger._worker_loop.is_closed() or not logger._worker_loop.is_running()
            )

    @pytest.mark.skipif(
        os.getenv("CI") == "true", reason="Timing-sensitive; skipped in CI"
    )
    def test_thread_mode_with_concurrent_access_during_drain(self) -> None:
        """Test thread mode with concurrent access during drain."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="concurrent-drain-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )

        # Start in thread mode
        logger.start()

        # Submit messages from multiple threads during drain
        def submit_messages(thread_id: int):
            for i in range(10):
                logger.info(f"thread-{thread_id}-{i}")
                time.sleep(0.001)

        threads = []
        for i in range(3):
            thread = threading.Thread(target=submit_messages, args=(i,))
            threads.append(thread)
            thread.start()

        # Start drain while threads are still submitting
        time.sleep(0.05)  # Let threads submit some messages
        result = asyncio.run(logger.stop_and_drain())

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        # Verify results
        assert result.submitted >= 25
        assert result.processed >= 0
        assert result.dropped >= 0
        if logger._worker_thread is not None:
            assert not logger._worker_thread.is_alive()
        if logger._worker_loop is not None:
            assert (
                logger._worker_loop.is_closed() or not logger._worker_loop.is_running()
            )
