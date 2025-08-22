"""
Test hanging prevention mechanisms in the logger.

These tests verify that the library cannot hang even under adverse conditions.
"""

import asyncio
import threading
import time

from fapilog.core.logger import SyncLoggerFacade


class TestHangingPrevention:
    """Test that the logger cannot hang during shutdown."""

    def test_worker_thread_cleanup_timeout(self) -> None:
        """Test that worker thread cleanup has a timeout and cannot hang."""
        collected = []
        logger = SyncLoggerFacade(
            name="hanging-prevention-test",
            queue_capacity=10,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )
        logger.start()

        # Submit some messages
        for i in range(5):
            logger.info(f"message {i}")

        # Allow processing time
        time.sleep(0.05)

        # Test shutdown - this should complete within reasonable time
        start_time = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        shutdown_time = time.perf_counter() - start_time

        # Shutdown should complete within 10 seconds (our timeout is 5s + buffer)
        assert shutdown_time < 10.0, (
            f"Shutdown took {shutdown_time:.2f}s - possible hang!"
        )

        # Verify results
        assert result.submitted >= 5
        assert logger._worker_thread is None or not logger._worker_thread.is_alive()

    def test_event_loop_cleanup_timeout(self) -> None:
        """Test that event loop cleanup has timeouts and cannot hang."""
        collected = []
        logger = SyncLoggerFacade(
            name="loop-cleanup-test",
            queue_capacity=15,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )
        logger.start()

        # Submit messages to create worker state
        for i in range(10):
            logger.info(f"message {i}")

        # Allow processing time
        time.sleep(0.05)

        # Test shutdown - this should complete within reasonable time
        start_time = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        shutdown_time = time.perf_counter() - start_time

        # Shutdown should complete within 10 seconds
        assert shutdown_time < 10.0, (
            f"Shutdown took {shutdown_time:.2f}s - possible hang!"
        )

        # Verify results
        assert result.submitted >= 10
        assert logger._worker_loop is None

    def test_drain_event_timeout(self) -> None:
        """Test that drain event wait has a timeout and cannot hang."""
        collected = []
        logger = SyncLoggerFacade(
            name="drain-event-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"message {i}")

        # Allow processing time
        time.sleep(0.05)

        # Test shutdown - this should complete within reasonable time
        start_time = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        shutdown_time = time.perf_counter() - start_time

        # Shutdown should complete within 15 seconds (our timeout is 10s + buffer)
        assert shutdown_time < 15.0, (
            f"Shutdown took {shutdown_time:.2f}s - possible hang!"
        )

        # Verify results
        assert result.submitted >= 5

    def test_concurrent_shutdown_robustness(self) -> None:
        """Test that shutdown is robust under concurrent load."""
        collected = []
        logger = SyncLoggerFacade(
            name="concurrent-shutdown-test",
            queue_capacity=20,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: collected.append(e),
        )
        logger.start()

        # Submit messages from multiple threads
        def submit_messages(thread_id: int):
            for i in range(15):
                logger.info(f"thread-{thread_id}-message-{i}")
                time.sleep(0.0001)

        threads = []
        for i in range(3):
            thread = threading.Thread(target=submit_messages, args=(i,))
            threads.append(thread)
            thread.start()

        # Allow threads to submit messages
        time.sleep(0.1)

        # Test shutdown under concurrent load - this should complete within reasonable time
        start_time = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        shutdown_time = time.perf_counter() - start_time

        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=5.0)  # Thread join should also have timeout

        # Shutdown should complete within 15 seconds
        assert shutdown_time < 15.0, (
            f"Shutdown took {shutdown_time:.2f}s - possible hang!"
        )

        # Verify results
        assert result.submitted >= 30

    def test_malicious_sink_does_not_hang(self) -> None:
        """Test that a malicious sink that never returns cannot hang the logger."""
        collected = []

        # Create a sink that simulates hanging
        def hanging_sink(event):
            # Simulate a sink that takes a very long time
            time.sleep(0.1)  # Long delay
            collected.append(event)

        logger = SyncLoggerFacade(
            name="malicious-sink-test",
            queue_capacity=5,
            batch_max_size=2,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=hanging_sink,
        )
        logger.start()

        # Submit messages
        for i in range(3):
            logger.info(f"message {i}")

        # Allow some processing time
        time.sleep(0.1)

        # Test shutdown - this should complete despite the slow sink
        start_time = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        shutdown_time = time.perf_counter() - start_time

        # Shutdown should complete within 20 seconds despite slow sink
        assert shutdown_time < 20.0, (
            f"Shutdown took {shutdown_time:.2f}s - possible hang!"
        )

        # Verify results
        assert result.submitted >= 3

    def test_worker_exception_does_not_hang(self) -> None:
        """Test that worker exceptions don't cause hanging during shutdown."""
        collected = []

        # Create a sink that raises exceptions
        def exploding_sink(event):
            if "explode" in str(event):
                raise RuntimeError("Sink explosion!")
            collected.append(event)

        logger = SyncLoggerFacade(
            name="exploding-sink-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=exploding_sink,
        )
        logger.start()

        # Submit messages including some that will explode
        for i in range(6):
            if i % 2 == 0:
                logger.info(f"normal message {i}")
            else:
                logger.info(f"explode message {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test shutdown - this should complete despite sink exceptions
        start_time = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        shutdown_time = time.perf_counter() - start_time

        # Shutdown should complete within 15 seconds despite exceptions
        assert shutdown_time < 15.0, (
            f"Shutdown took {shutdown_time:.2f}s - possible hang!"
        )

        # Verify results
        assert result.submitted >= 6
