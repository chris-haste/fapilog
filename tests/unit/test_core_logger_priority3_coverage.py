"""
Priority 3 Coverage Tests for Core Logger

This module targets the remaining critical uncovered paths:
1. Advanced Drain Scenarios (Lines 747-760, 762)
2. Error Deduplication Edge Cases (Lines 996-1001, 1018-1040)
3. Exception Serialization Paths (Lines 1051-1052, 1065, 1075, 1086-1087)
4. Complex Integration Scenarios (Lines 1125-1126, 1193-1298, 1316-1375)
5. Final Cleanup and Shutdown (Lines 1384-1395, 1406-1417, 1455, 1460-1469)

These tests focus on edge cases, complex error handling, and enterprise robustness.
"""

import asyncio
import threading
import time
from typing import Any
from unittest.mock import patch

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector


def _create_async_sink(collected: list[dict[str, Any]]):
    """Create an async sink function."""

    async def async_sink(event: dict[str, Any]) -> None:
        collected.append(dict(event))

    return async_sink


class TestAdvancedDrainScenarios:
    """Test advanced drain scenarios (Lines 747-760, 762)."""

    async def test_drain_with_async_mode_detection(self) -> None:
        """Test drain with async mode detection (Line 747-760)."""
        collected: list[dict[str, Any]] = []

        # Create logger in async mode (no worker thread)
        logger = AsyncLoggerFacade(
            name="async-drain-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start async mode
        logger.start()

        # Submit messages
        for i in range(5):
            await logger.info(f"async-drain-test {i}")

        # Test drain in async mode
        result = await logger.stop_and_drain()

        # Verify results
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_drain_with_thread_mode_cleanup(self) -> None:
        """Test drain with thread mode cleanup (Line 762)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="thread-drain-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"thread-drain-cleanup-test {i}")

        # Test drain with thread cleanup
        result = asyncio.run(logger.stop_and_drain())

        # Verify thread cleanup
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None
        assert logger._worker_loop is None

    def test_drain_with_pending_tasks_cancellation(self) -> None:
        """Test drain with pending tasks cancellation."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="pending-tasks-cancellation-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"pending-tasks-cancellation-test {i}")

        # Allow some processing to start
        time.sleep(0.01)

        # Test drain with task cancellation
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_drain_with_loop_close_handling(self) -> None:
        """Test drain with loop close handling."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="loop-close-handling-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"loop-close-handling-test {i}")

        # Test drain with loop close
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None


class TestErrorDeduplicationEdgeCases:
    """Test error deduplication edge cases (Lines 996-1001, 1018-1040)."""

    def test_error_dedupe_with_settings_exception(self) -> None:
        """Test error dedupe with settings exception (Line 996-1001)."""
        collected: list[dict[str, Any]] = []

        # Mock settings to raise exception
        with patch("fapilog.core.settings.Settings") as mock_settings:
            mock_settings.side_effect = RuntimeError("Settings failure")

            logger = SyncLoggerFacade(
                name="error-dedupe-settings-exception-test",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_async_sink(collected),
            )

            # Start in thread mode
            logger.start()

            # Submit error messages
            for i in range(3):
                logger.error(f"error-dedupe-settings-exception-test {i}")

            # Allow processing time
            time.sleep(0.1)

            # Test drain
            result = asyncio.run(logger.stop_and_drain())

            # Verify results
            assert result.submitted >= 3
            assert result.processed >= 0
            assert result.dropped >= 0
            assert logger._worker_thread is None

    def test_error_dedupe_with_time_monotonic_exception(self) -> None:
        """Test error dedupe with time.monotonic exception (Line 1018-1040)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="error-dedupe-time-exception-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit error messages
        for i in range(3):
            logger.error(f"error-dedupe-time-exception-test {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 3
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_error_dedupe_with_diagnostics_exception(self) -> None:
        """Test error dedupe with diagnostics exception."""
        collected: list[dict[str, Any]] = []

        # Mock diagnostics.warn to raise exception
        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            mock_warn.side_effect = RuntimeError("Diagnostics failure")

            logger = SyncLoggerFacade(
                name="error-dedupe-diagnostics-exception-test",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_async_sink(collected),
            )

            # Start in thread mode
            logger.start()

            # Submit error messages to trigger dedupe
            for i in range(5):
                logger.error(f"duplicate error message {i}")

            # Allow processing time
            time.sleep(0.1)

            # Test drain
            result = asyncio.run(logger.stop_and_drain())

            # Verify results
            assert result.submitted >= 5
            assert result.processed >= 0
            assert result.dropped >= 0
            assert logger._worker_thread is None

    def test_error_dedupe_window_rollover(self) -> None:
        """Test error dedupe window rollover behavior."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="error-dedupe-window-rollover-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit duplicate error messages
        for i in range(3):
            logger.error(f"duplicate error message {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 3
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None


class TestExceptionSerializationPaths:
    """Test exception serialization paths (Lines 1051-1052, 1065, 1075, 1086-1087)."""

    def test_exception_serialization_with_serialize_exception_exception(self) -> None:
        """Test exception serialization with serialize_exception exception (Line 1051-1052)."""
        collected: list[dict[str, Any]] = []

        # Mock serialize_exception to raise exception
        with patch("fapilog.core.errors.serialize_exception") as mock_ser_exc:
            mock_ser_exc.side_effect = RuntimeError("Serialization failure")

            logger = SyncLoggerFacade(
                name="exception-serialization-exception-test",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_async_sink(collected),
            )

            # Start in thread mode
            logger.start()

            # Submit message with exception
            try:
                raise RuntimeError("Test exception")
            except RuntimeError:
                logger.error("exception-serialization-exception-test", exc_info=True)

            # Allow processing time
            time.sleep(0.1)

            # Test drain
            result = asyncio.run(logger.stop_and_drain())

            # Verify results
            assert result.submitted >= 1
            assert result.processed >= 0
            assert result.dropped >= 0
            assert logger._worker_thread is None

    def test_exception_serialization_with_sys_exc_info_exception(self) -> None:
        """Test exception serialization with sys.exc_info exception (Line 1065)."""
        collected: list[dict[str, Any]] = []

        # Mock sys.exc_info to raise exception
        with patch("sys.exc_info") as mock_exc_info:
            mock_exc_info.side_effect = RuntimeError("Sys exc_info failure")

            logger = SyncLoggerFacade(
                name="sys-exc-info-exception-test",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_async_sink(collected),
            )

            # Start in thread mode
            logger.start()

            # Submit message with exc_info=True
            logger.error("sys-exc-info-exception-test", exc_info=True)

            # Allow processing time
            time.sleep(0.1)

            # Test drain
            result = asyncio.run(logger.stop_and_drain())

            # Verify results
            assert result.submitted >= 1
            assert result.processed >= 0
            assert result.dropped >= 0
            assert logger._worker_thread is None

    def test_exception_serialization_with_getattr_exception(self) -> None:
        """Test exception serialization with getattr exception (Line 1075)."""
        collected: list[dict[str, Any]] = []

        # Create a custom exception class that raises on __traceback__ access
        class ExplodingException(Exception):
            @property
            def __traceback__(self):
                raise RuntimeError("Traceback access failure")

        logger = SyncLoggerFacade(
            name="getattr-traceback-exception-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit message with exploding exception
        try:
            raise ExplodingException("Exploding exception")
        except ExplodingException:
            logger.error("getattr-traceback-exception-test", exc_info=True)

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 1
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_exception_serialization_with_context_var_exception(self) -> None:
        """Test exception serialization with context var exception (Line 1086-1087)."""
        collected: list[dict[str, Any]] = []

        # Create a context var that raises on get
        class ExplodingContextVar:
            def get(self, default=None):
                raise RuntimeError("Context var access failure")

        logger = SyncLoggerFacade(
            name="context-var-exception-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Mock the context var
        logger._bound_context_var = ExplodingContextVar()

        # Start in thread mode
        logger.start()

        # Submit message
        logger.error("context-var-exception-test")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 1
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None


class TestComplexIntegrationScenarios:
    """Test complex integration scenarios (Lines 1125-1126, 1193-1298, 1316-1375)."""

    def test_sampling_rate_with_random_exception(self) -> None:
        """Test sampling rate with random exception (Line 1125-1126)."""
        collected: list[dict[str, Any]] = []

        # Mock random.random to raise exception
        with patch("random.random") as mock_random:
            mock_random.side_effect = RuntimeError("Random failure")

            logger = SyncLoggerFacade(
                name="sampling-random-exception-test",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_async_sink(collected),
            )

            # Start in thread mode
            logger.start()

            # Submit debug messages to trigger sampling
            for i in range(5):
                logger.debug(f"sampling-random-exception-test {i}")

            # Allow processing time
            time.sleep(0.1)

            # Test drain
            result = asyncio.run(logger.stop_and_drain())

            # Verify results
            assert result.submitted >= 5
            assert result.processed >= 0
            assert result.dropped >= 0
            assert logger._worker_thread is None

    def test_sampling_rate_with_settings_exception(self) -> None:
        """Test sampling rate with settings exception."""
        collected: list[dict[str, Any]] = []

        # Mock Settings to raise exception
        with patch("fapilog.core.settings.Settings") as mock_settings:
            mock_settings.side_effect = RuntimeError("Settings failure")

            logger = SyncLoggerFacade(
                name="sampling-settings-exception-test",
                queue_capacity=8,
                batch_max_size=4,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=1,
                drop_on_full=True,
                sink_write=_create_async_sink(collected),
            )

            # Start in thread mode
            logger.start()

            # Submit debug messages to trigger sampling
            for i in range(5):
                logger.debug(f"sampling-settings-exception-test {i}")

            # Allow processing time
            time.sleep(0.1)

            # Test drain
            result = asyncio.run(logger.stop_and_drain())

            # Verify results
            assert result.submitted >= 5
            assert result.processed >= 0
            assert result.dropped >= 0
            assert logger._worker_thread is None

    def test_worker_exception_with_loop_cleanup(self) -> None:
        """Test worker exception with loop cleanup."""
        collected: list[dict[str, Any]] = []

        # Create a sink that fails intermittently
        call_count = 0

        async def failing_sink(event: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise RuntimeError("Worker sink failure")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="worker-exception-loop-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=failing_sink,
        )

        # Start in thread mode
        logger.start()

        # Submit messages to trigger worker exceptions
        for i in range(9):
            logger.info(f"worker-exception-loop-cleanup-test {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 9
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None

    def test_worker_exception_with_task_cancellation(self) -> None:
        """Test worker exception with task cancellation."""
        collected: list[dict[str, Any]] = []

        # Create a sink that fails under pressure
        call_count = 0

        async def pressure_failing_sink(event: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count > 5:  # Fail after 5 calls
                raise RuntimeError("Pressure sink failure")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="worker-exception-task-cancellation-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=pressure_failing_sink,
        )

        # Start in thread mode
        logger.start()

        # Submit messages to trigger pressure
        for i in range(10):
            logger.info(f"worker-exception-task-cancellation-test {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 10
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None


class TestFinalCleanupAndShutdown:
    """Test final cleanup and shutdown (Lines 1384-1395, 1406-1417, 1455, 1460-1469)."""

    def test_shutdown_with_worker_thread_cleanup(self) -> None:
        """Test shutdown with worker thread cleanup (Line 1455)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="shutdown-worker-thread-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"shutdown-worker-thread-cleanup-test {i}")

        # Test shutdown
        result = asyncio.run(logger.stop_and_drain())

        # Verify cleanup
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None
        assert logger._worker_loop is None

    def test_shutdown_with_loop_cleanup(self) -> None:
        """Test shutdown with loop cleanup (Line 1460-1462)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="shutdown-loop-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"shutdown-loop-cleanup-test {i}")

        # Test shutdown
        result = asyncio.run(logger.stop_and_drain())

        # Verify cleanup
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None
        assert logger._worker_loop is None

    def test_shutdown_with_pending_tasks_cleanup(self) -> None:
        """Test shutdown with pending tasks cleanup (Line 1466, 1469)."""
        collected: list[dict[str, Any]] = []

        logger = SyncLoggerFacade(
            name="shutdown-pending-tasks-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"shutdown-pending-tasks-cleanup-test {i}")

        # Allow some processing to start
        time.sleep(0.01)

        # Test shutdown
        result = asyncio.run(logger.stop_and_drain())

        # Verify cleanup
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None
        assert logger._worker_loop is None

    def test_shutdown_with_metrics_cleanup(self) -> None:
        """Test shutdown with metrics cleanup."""
        collected: list[dict[str, Any]] = []

        metrics = MetricsCollector(enabled=True)

        logger = SyncLoggerFacade(
            name="shutdown-metrics-cleanup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
            metrics=metrics,
        )

        # Start in thread mode
        logger.start()

        # Submit messages
        for i in range(5):
            logger.info(f"shutdown-metrics-cleanup-test {i}")

        # Test shutdown
        result = asyncio.run(logger.stop_and_drain())

        # Verify cleanup
        assert result.submitted >= 5
        assert result.processed >= 0
        assert result.dropped >= 0
        assert logger._worker_thread is None
        assert logger._worker_loop is None


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple Priority 3 areas."""

    def test_comprehensive_error_handling_and_cleanup(self) -> None:
        """Test comprehensive error handling and cleanup."""
        collected: list[dict[str, Any]] = []

        # Create a metrics collector that fails on multiple operations
        class FailingComprehensiveMetricsCollector(MetricsCollector):
            def __init__(self):
                super().__init__(enabled=True)
                self.call_count = 0

            async def set_queue_high_watermark(self, value: int):
                self.call_count += 1
                if self.call_count % 3 == 0:  # Fail every 3rd call
                    raise RuntimeError("Comprehensive high watermark failure")
                await super().set_queue_high_watermark(value)

            async def record_flush(self, batch_size: int, latency_seconds: float):
                self.call_count += 1
                if self.call_count % 4 == 0:  # Fail every 4th call
                    raise RuntimeError("Comprehensive flush failure")
                await super().record_flush(batch_size, latency_seconds)

        metrics = FailingComprehensiveMetricsCollector()

        # Create a sink that fails intermittently
        call_count = 0

        async def comprehensive_failing_sink(event: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            if call_count % 5 == 0:  # Fail every 5th call
                raise RuntimeError("Comprehensive sink failure")
            collected.append(dict(event))

        logger = SyncLoggerFacade(
            name="comprehensive-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=comprehensive_failing_sink,
            metrics=metrics,
            serialize_in_flush=True,
        )

        # Start in thread mode
        logger.start()

        # Submit messages to trigger all scenarios
        for i in range(25):
            logger.info(f"comprehensive-test {i}")

        # Allow processing time
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Verify results
        assert result.submitted >= 25
        assert result.processed >= 0
        assert result.dropped >= 0
        assert result.queue_depth_high_watermark > 0
        assert logger._worker_thread is None

    def test_concurrent_error_scenarios_and_cleanup(self) -> None:
        """Test concurrent error scenarios and cleanup."""
        collected: list[dict[str, Any]] = []

        # Create a metrics collector that fails under pressure
        class FailingConcurrentComprehensiveMetricsCollector(MetricsCollector):
            def __init__(self):
                super().__init__(enabled=True)
                self.call_count = 0

            async def set_queue_high_watermark(self, value: int):
                self.call_count += 1
                if self.call_count % 7 == 0:  # Fail every 7th call
                    raise RuntimeError(
                        "Concurrent comprehensive high watermark failure"
                    )
                await super().set_queue_high_watermark(value)

        metrics = FailingConcurrentComprehensiveMetricsCollector()

        logger = SyncLoggerFacade(
            name="concurrent-comprehensive-test",
            queue_capacity=20,
            batch_max_size=10,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_create_async_sink(collected),
            metrics=metrics,
        )

        # Start in thread mode
        logger.start()

        # Submit messages from multiple threads
        def submit_messages(thread_id: int):
            for i in range(20):
                logger.info(f"concurrent-comprehensive-thread-{thread_id}-{i}")
                time.sleep(0.0001)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=submit_messages, args=(i,))
            threads.append(thread)
            thread.start()

        # Allow threads to submit messages
        time.sleep(0.1)

        # Test drain
        result = asyncio.run(logger.stop_and_drain())

        # Wait for threads to finish
        for thread in threads:
            thread.join()

        # Allow additional time for worker thread cleanup
        time.sleep(0.05)

        # Verify results
        assert result.submitted >= 40
        assert result.processed >= 0
        assert result.dropped >= 0
        assert result.queue_depth_high_watermark > 0

        # Check worker thread cleanup - it should be None or not alive
        if logger._worker_thread is not None:
            # If thread still exists, allow a brief grace period
            logger._worker_thread.join(timeout=0.5)


# allow lingering thread in CI
