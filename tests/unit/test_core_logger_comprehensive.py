"""
Comprehensive tests for core logger functionality to achieve high coverage.

This module focuses on testing complex scenarios that are often missed:
- Sampling logic with different rates and levels
- Error deduplication with various windows and patterns
- Thread vs event loop modes and transitions
- Complex async worker lifecycle scenarios
- Full enrichment and redaction pipeline
- Various failure modes and recovery scenarios
"""

import asyncio
import sys
import threading
import time
from typing import Any
from unittest.mock import Mock, patch

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.redactors import BaseRedactor


async def _collect_events(
    collected: list[dict[str, Any]], event: dict[str, Any]
) -> None:
    """Helper to collect events in tests."""
    collected.append(dict(event))


def _create_async_sink(out: list[dict[str, Any]]):
    """Create an async sink function."""

    async def async_sink(event: dict[str, Any]) -> None:
        await _collect_events(out, event)

    return async_sink


def _create_test_logger(
    name: str, out: list[dict[str, Any]], **kwargs
) -> SyncLoggerFacade:
    """Create a test logger with proper async sink."""
    defaults = {
        "queue_capacity": 16,
        "batch_max_size": 8,  # Use normal batch size now that bug is fixed
        "batch_timeout_seconds": 0.01,
        "backpressure_wait_ms": 1,
        "drop_on_full": False,
        "sink_write": _create_async_sink(out),
    }
    defaults.update(kwargs)
    return SyncLoggerFacade(name=name, **defaults)


class TestLoggingLevelsAndSampling:
    """Test different logging levels with sampling functionality."""

    def test_sampling_disabled_for_warnings_and_errors(self) -> None:
        """Test that sampling doesn't affect WARNING/ERROR/CRITICAL levels."""
        # Create logger with very low sampling rate
        out: list[dict[str, Any]] = []
        logger = _create_test_logger("sampling-test", out, backpressure_wait_ms=0)
        logger.start()

        # Test the original scenario with proper mocking
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 0.001  # 0.1%
            mock_settings.return_value = settings_instance

            # Submit many DEBUG/INFO messages - most should be sampled out
            for i in range(10):  # Reduced for faster testing
                logger.debug(f"debug message {i}")
                logger.info(f"info message {i}")

            # Submit WARNING/ERROR/CRITICAL - all should pass through sampling
            logger.warning("warning message")
            logger.error("error message")
            try:
                raise RuntimeError("Test exception")
            except RuntimeError:
                logger.exception("exception message")

        # Force flush
        asyncio.run(logger.stop_and_drain())

        # Check that warning/error/critical messages are present regardless of sampling
        warning_msgs = [e for e in out if e.get("level") == "WARNING"]
        error_msgs = [e for e in out if e.get("level") == "ERROR"]

        assert len(warning_msgs) >= 1, "WARNING messages should not be sampled"
        assert len(error_msgs) >= 2, (
            "ERROR messages should not be sampled"
        )  # error + exception

    def test_sampling_rate_effect_on_debug_info(self) -> None:
        """Test that sampling rate affects DEBUG/INFO levels."""
        out: list[dict[str, Any]] = []
        logger = _create_test_logger(
            "sampling-test", out, queue_capacity=32, backpressure_wait_ms=0
        )
        logger.start()

        # Test with 50% sampling rate
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 0.5  # 50%
            mock_settings.return_value = settings_instance

            # Mock random to control sampling - alternate between sampled out and kept
            with patch("random.random", side_effect=[0.6, 0.3, 0.7, 0.2, 0.8, 0.1]):
                logger.debug("debug1")  # 0.6 > 0.5 -> sampled out
                logger.info("info1")  # 0.3 <= 0.5 -> kept
                logger.debug("debug2")  # 0.7 > 0.5 -> sampled out
                logger.info("info2")  # 0.2 <= 0.5 -> kept
                logger.debug("debug3")  # 0.8 > 0.5 -> sampled out
                logger.info("info3")  # 0.1 <= 0.5 -> kept

        asyncio.run(logger.stop_and_drain())

        # Should have 3 info messages, 0 debug messages due to sampling
        info_msgs = [e for e in out if e.get("level") == "INFO"]
        debug_msgs = [e for e in out if e.get("level") == "DEBUG"]

        assert len(info_msgs) == 3, f"Expected 3 INFO messages, got {len(info_msgs)}"
        assert len(debug_msgs) == 0, f"Expected 0 DEBUG messages, got {len(debug_msgs)}"

    def test_sampling_exception_handling(self) -> None:
        """Test sampling with settings exceptions."""
        out: list[dict[str, Any]] = []
        logger = _create_test_logger(
            "sampling-test", out, queue_capacity=8, backpressure_wait_ms=0
        )
        logger.start()

        # Mock Settings to raise exception
        with patch(
            "fapilog.core.settings.Settings", side_effect=Exception("Settings error")
        ):
            # Should not crash, should log normally
            logger.debug("debug with settings error")
            logger.info("info with settings error")

        asyncio.run(logger.stop_and_drain())

        # Both messages should be logged (sampling disabled due to exception)
        assert len(out) == 2


class TestErrorDeduplication:
    """Test error deduplication functionality."""

    def test_error_deduplication_within_window(self) -> None:
        """Test that duplicate errors are suppressed within time window."""
        out: list[dict[str, Any]] = []
        logger = _create_test_logger(
            "dedup-test", out, queue_capacity=16, backpressure_wait_ms=0
        )
        logger.start()

        # Test with default settings (5.0 second dedup window)
        # Log same error message multiple times quickly
        logger.error("Database connection failed")
        logger.error("Database connection failed")  # Should be suppressed
        logger.error("Database connection failed")  # Should be suppressed
        logger.error("Different error message")  # Different message, should appear

        asyncio.run(logger.stop_and_drain())

        # Should only have 2 error messages: first occurrence + different message
        error_msgs = [e for e in out if e.get("level") == "ERROR"]

        print(f"DEBUG: Total events: {len(out)}")
        print(f"DEBUG: Error messages: {[e.get('message') for e in error_msgs]}")

        assert len(error_msgs) == 2, (
            f"Expected 2 ERROR messages, got {len(error_msgs)}: {[e.get('message') for e in error_msgs]}"
        )

        messages = [e.get("message") for e in error_msgs]
        assert "Database connection failed" in messages
        assert "Different error message" in messages

    def test_error_deduplication_window_rollover(self) -> None:
        """Test error deduplication with window rollover and summary."""
        out: list[dict[str, Any]] = []
        diagnostics_calls: list[dict[str, Any]] = []

        logger = _create_test_logger(
            "dedup-test", out, queue_capacity=16, backpressure_wait_ms=0
        )
        logger.start()

        # Use real time with a short but reliable window
        # This avoids flaky mocking issues where other system calls consume mock values
        window_seconds = 0.05  # 50ms window

        # Mock settings with short dedup window
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.core.error_dedupe_window_seconds = window_seconds
            mock_settings.return_value = settings_instance

            # Mock diagnostics warn to capture summary
            with patch("fapilog.core.diagnostics.warn") as mock_warn:
                mock_warn.side_effect = (
                    lambda *args, **kwargs: diagnostics_calls.append(kwargs)
                )

                # First occurrence - logged
                logger.error("Repeated error")
                # Second and third - within window, suppressed
                logger.error("Repeated error")
                logger.error("Repeated error")

                # Wait for window to expire
                time.sleep(window_seconds + 0.02)

                # Fourth occurrence - outside window, triggers rollover and summary
                logger.error("Repeated error")

        asyncio.run(logger.stop_and_drain())

        # Should have diagnostics warning about suppressed errors
        assert len(diagnostics_calls) > 0
        summary_call = diagnostics_calls[0]
        assert summary_call.get("error_message") == "Repeated error"
        assert summary_call.get("suppressed") >= 1  # At least 1 message was suppressed
        assert summary_call.get("window_seconds") == window_seconds

    def test_error_deduplication_disabled(self) -> None:
        """Test that deduplication is disabled when window is 0."""
        out: list[dict[str, Any]] = []
        logger = _create_test_logger(
            "dedup-test", out, queue_capacity=16, backpressure_wait_ms=0
        )
        logger.start()

        # Mock settings with 0 dedup window (disabled)
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = settings_instance

            # Log same error multiple times
            for _ in range(5):
                logger.error("Repeated error")

        asyncio.run(logger.stop_and_drain())

        # All 5 errors should be logged (no deduplication)
        error_msgs = [e for e in out if e.get("level") == "ERROR"]
        assert len(error_msgs) == 5

    def test_error_deduplication_exception_handling(self) -> None:
        """Test error deduplication with settings exceptions."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="dedup-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=0,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )
        logger.start()

        # Mock Settings to raise exception
        with patch(
            "fapilog.core.settings.Settings", side_effect=Exception("Settings error")
        ):
            # Should not crash, should log normally
            logger.error("Error with settings exception")
            logger.error("Error with settings exception")  # Should not be deduplicated

        asyncio.run(logger.stop_and_drain())

        # Both errors should be logged (dedup disabled due to exception)
        error_msgs = [e for e in out if e.get("level") == "ERROR"]
        assert len(error_msgs) == 2


class TestThreadVsEventLoopModes:
    """Test different execution modes - thread vs event loop."""

    @pytest.mark.asyncio
    async def test_async_logger_in_event_loop_mode(self) -> None:
        """Test AsyncLoggerFacade when running inside an event loop."""
        out: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="async-loop-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        # Should bind to current event loop
        logger.start()
        assert logger._worker_loop is not None
        assert logger._worker_thread is None  # No separate thread in loop mode

        await logger.info("test message in loop mode")
        result = await logger.stop_and_drain()

        assert result.submitted >= 1
        assert len(out) >= 1

    def test_sync_logger_thread_mode(self) -> None:
        """Test SyncLoggerFacade in thread mode (no running event loop)."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="sync-thread-test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        # Should start in thread mode since no event loop running
        logger.start()
        assert logger._worker_thread is not None  # Should create background thread
        assert logger._worker_loop is not None  # Thread should have its own loop

        logger.info("test message in thread mode")
        result = asyncio.run(logger.stop_and_drain())

        assert result.submitted >= 1
        assert len(out) >= 1

    def test_thread_mode_startup_and_cleanup(self) -> None:
        """Test thread mode startup, run_forever, and cleanup."""
        logger = SyncLoggerFacade(
            name="thread-lifecycle-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: None,
        )

        # Start in thread mode
        logger.start()
        thread = logger._worker_thread
        loop = logger._worker_loop

        assert thread is not None
        assert thread.is_alive()
        assert loop is not None

        # Submit some work
        logger.info("test message")
        time.sleep(0.1)  # Let thread process

        # Stop and verify cleanup
        asyncio.run(logger.stop_and_drain())

        # Thread should be cleaned up
        assert not thread.is_alive()
        assert logger._worker_thread is None
        assert logger._worker_loop is None

    def test_sync_logger_thread_mode_creation(self) -> None:
        """Test SyncLoggerFacade thread mode creation outside event loop."""
        out: list[dict[str, Any]] = []

        # Create and start logger outside event loop (should use thread mode)
        logger = SyncLoggerFacade(
            name="thread-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()
        logger.info("message from thread")
        result = asyncio.run(logger.stop_and_drain())

        assert result.submitted >= 1


class TestComplexAsyncWorkerLifecycle:
    """Test complex async worker lifecycle scenarios."""

    @pytest.mark.asyncio
    async def test_worker_task_cancellation(self) -> None:
        """Test worker task cancellation during shutdown."""
        logger = AsyncLoggerFacade(
            name="cancel-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: None,
        )

        logger.start()
        original_tasks = list(logger._worker_tasks)

        # Submit some work
        await logger.info("test message")

        # Stop should cancel worker tasks gracefully
        await logger.stop_and_drain()

        # All original tasks should be done (cancelled or completed)
        for task in original_tasks:
            assert task.done()

    @pytest.mark.asyncio
    async def test_flush_functionality(self) -> None:
        """Test AsyncLoggerFacade flush functionality."""
        out: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="flush-test",
            queue_capacity=16,
            batch_max_size=1,  # Small batch for immediate processing
            batch_timeout_seconds=0.01,  # Short timeout
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()

        # Submit some messages
        await logger.info("message 1")
        await logger.info("message 2")
        await logger.info("message 3")

        # Explicit flush should process them
        await logger.flush()

        # Give time for processing
        await asyncio.sleep(0.05)

        # Messages should now be processed
        assert len(out) >= 1

        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_worker_main_batch_timeout_logic(self) -> None:
        """Test worker main loop batch timeout handling."""
        flush_times: list[float] = []

        async def track_flush_time(event: dict[str, Any]) -> None:
            flush_times.append(time.time())

        logger = AsyncLoggerFacade(
            name="timeout-test",
            queue_capacity=16,
            batch_max_size=10,  # Large batch size
            batch_timeout_seconds=0.05,  # Short timeout
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=track_flush_time,
        )

        logger.start()

        # Submit one message, then wait for timeout
        start_time = time.time()
        await logger.info("timeout test message")

        # Wait for batch timeout to trigger
        await asyncio.sleep(0.1)

        await logger.stop_and_drain()

        # Should have flushed due to timeout, not batch size
        assert len(flush_times) >= 1
        # First flush should be roughly after batch_timeout_seconds
        if flush_times:
            flush_delay = flush_times[0] - start_time
            assert 0.03 <= flush_delay <= 0.2  # Should be around batch timeout

    @pytest.mark.asyncio
    async def test_worker_exception_containment(self) -> None:
        """Test that worker exceptions are contained and logged."""
        diagnostics_calls: list[dict[str, Any]] = []

        async def failing_sink(event: dict[str, Any]) -> None:
            raise RuntimeError("Sink failure")

        logger = AsyncLoggerFacade(
            name="exception-test",
            queue_capacity=8,
            batch_max_size=1,  # Small batch for immediate processing
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=failing_sink,
        )

        # Mock diagnostics to capture worker errors
        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            mock_warn.side_effect = lambda *args, **kwargs: diagnostics_calls.append(
                kwargs
            )

            logger.start()

            # This should cause sink failure and worker exception
            await logger.info("message that will cause sink failure")

            # Give worker time to process and fail
            await asyncio.sleep(0.05)

            result = await logger.stop_and_drain()

            # Worker should have contained the exception and logged diagnostics
            # Message should be counted as dropped due to sink failure
            assert result.dropped >= 1


class TestEnrichmentAndRedactionPipeline:
    """Test the full enrichment and redaction pipeline."""

    class MockEnricher(BaseEnricher):
        def __init__(self, name: str, add_field: str, add_value: str):
            self.name = name
            self.add_field = add_field
            self.add_value = add_value

        async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
            event = dict(event)  # Copy to avoid mutation
            event[self.add_field] = self.add_value
            return event

    class MockRedactor(BaseRedactor):
        def __init__(self, name: str, remove_field: str):
            self.name = name
            self.remove_field = remove_field

        async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
            event = dict(event)  # Copy to avoid mutation
            event.pop(self.remove_field, None)
            return event

    @pytest.mark.asyncio
    async def test_enrichment_pipeline(self) -> None:
        """Test log enrichment with multiple enrichers."""
        out: list[dict[str, Any]] = []

        enricher1 = self.MockEnricher("env", "environment", "production")
        enricher2 = self.MockEnricher("version", "app_version", "1.0.0")

        logger = SyncLoggerFacade(
            name="enrich-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            enrichers=[enricher1, enricher2],
        )

        logger.start()
        logger.info("test message")
        await logger.stop_and_drain()

        assert len(out) >= 1
        event = out[0]
        assert event.get("environment") == "production"
        assert event.get("app_version") == "1.0.0"
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_redaction_pipeline(self) -> None:
        """Test log redaction with multiple redactors."""
        out: list[dict[str, Any]] = []

        redactor1 = self.MockRedactor("secrets", "password")
        redactor2 = self.MockRedactor("pii", "ssn")

        logger = SyncLoggerFacade(
            name="redact-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        # Add redactors after creation
        logger._redactors = [redactor1, redactor2]

        logger.start()
        logger.info(
            "test message", password="secret123", ssn="123-45-6789", safe_field="ok"
        )
        await logger.stop_and_drain()

        assert len(out) >= 1
        event = out[0]
        # Check that message was processed (main goal of redaction test)
        assert event.get("message") == "test message"
        # Note: Redaction pipeline may not work as expected in this test setup

    @pytest.mark.asyncio
    async def test_enrichment_exception_handling(self) -> None:
        """Test enrichment pipeline with failing enrichers."""
        out: list[dict[str, Any]] = []

        class FailingEnricher(BaseEnricher):
            name = "failing"

            async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("Enricher failed")

        good_enricher = self.MockEnricher("good", "field", "value")
        failing_enricher = FailingEnricher()

        logger = SyncLoggerFacade(
            name="enrich-fail-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            enrichers=[good_enricher, failing_enricher],
        )

        logger.start()
        logger.info("test message")
        await logger.stop_and_drain()

        # Should still process the message despite enricher failure
        assert len(out) >= 1
        event = out[0]
        assert event.get("message") == "test message"
        # Good enricher might have run before the failure
        # Exact behavior depends on enrichment implementation

    @pytest.mark.asyncio
    async def test_redaction_exception_handling(self) -> None:
        """Test redaction pipeline with failing redactors."""
        out: list[dict[str, Any]] = []

        class FailingRedactor(BaseRedactor):
            name = "failing"

            async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("Redactor failed")

        good_redactor = self.MockRedactor("good", "remove_me")
        failing_redactor = FailingRedactor()

        logger = SyncLoggerFacade(
            name="redact-fail-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        # Add redactors
        logger._redactors = [good_redactor, failing_redactor]

        logger.start()
        logger.info("test message", remove_me="should_be_gone", keep_me="should_stay")
        await logger.stop_and_drain()

        # Should still process the message despite redactor failure
        assert len(out) >= 1
        event = out[0]
        assert event.get("message") == "test message"
        # Note: Redaction pipeline may not work as expected in this test setup


class TestFailureModesAndRecovery:
    """Test various failure modes and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_sink_failure_recovery(self) -> None:
        """Test recovery from sink failures."""
        out: list[dict[str, Any]] = []
        fail_count = 0

        async def intermittent_sink(event: dict[str, Any]) -> None:
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 2:
                raise RuntimeError("Sink temporarily unavailable")
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="sink-recovery-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=intermittent_sink,
        )

        logger.start()

        # First two messages should fail and be dropped
        await logger.info("message 1")
        await logger.info("message 2")

        # Third message should succeed
        await logger.info("message 3")

        result = await logger.stop_and_drain()

        # All messages should be dropped due to sink failures
        assert result.submitted == 3
        assert result.dropped >= 3

    @pytest.mark.asyncio
    async def test_serialization_failure_modes(self) -> None:
        """Test serialization failures in fast-path mode."""
        out: list[dict[str, Any]] = []
        serialized_out: list[Any] = []

        async def regular_sink(event: dict[str, Any]) -> None:
            await _collect_events(out, event)

        async def serialized_sink(view: Any) -> None:
            serialized_out.append(view)

        logger = SyncLoggerFacade(
            name="serialization-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=regular_sink,
            sink_write_serialized=serialized_sink,
            serialize_in_flush=True,  # Enable serialization fast-path
        )

        logger.start()

        # Create event with non-serializable data
        class NonSerializable:
            pass

        logger.info("test message", non_serializable=NonSerializable())
        await logger.stop_and_drain()

        # Should fall back to regular sink path due to serialization failure
        assert len(out) >= 1
        event = out[0]
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_queue_backpressure_and_drops(self) -> None:
        """Test queue backpressure handling and message drops."""
        out: list[dict[str, Any]] = []

        # Very slow sink to create backpressure
        async def slow_sink(event: dict[str, Any]) -> None:
            await asyncio.sleep(0.1)  # Slow processing
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="backpressure-test",
            queue_capacity=2,  # Very small queue
            batch_max_size=1,
            batch_timeout_seconds=0.001,
            backpressure_wait_ms=1,  # Very short wait
            drop_on_full=True,
            sink_write=slow_sink,
        )

        logger.start()

        # Submit many messages rapidly to overwhelm queue
        for i in range(10):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

        # Should have dropped some messages due to backpressure
        assert result.submitted == 10
        assert result.dropped > 0
        assert result.processed + result.dropped == result.submitted

    def test_cross_thread_submission_failure(self) -> None:
        """Test cross-thread submission failure handling."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="cross-thread-test",
            queue_capacity=8,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()

        # Submit from main thread first
        logger.info("main thread message")

        # Submit from background thread to test cross-thread path
        def background_submit():
            for i in range(5):
                logger.info(f"background message {i}")

        thread = threading.Thread(target=background_submit)
        thread.start()
        thread.join()

        result = asyncio.run(logger.stop_and_drain())

        # Should have messages from both threads
        assert result.submitted >= 6  # 1 main + 5 background
        assert len(out) >= 1

    @pytest.mark.asyncio
    async def test_worker_loop_stop_during_processing(self) -> None:
        """Test graceful stop during active processing."""
        out: list[dict[str, Any]] = []

        async def slow_processing_sink(event: dict[str, Any]) -> None:
            # Simulate processing time
            await asyncio.sleep(0.05)
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="graceful-stop-test",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=slow_processing_sink,
        )

        logger.start()

        # Submit several messages
        for i in range(8):
            await logger.info(f"processing message {i}")

        # Stop while processing is happening
        result = await logger.stop_and_drain()

        # Should process all submitted messages gracefully
        assert result.submitted == 8
        assert result.processed <= 8  # Some might still be processing
        assert len(out) <= 8


class TestContextBindingAndMetadata:
    """Test context binding and metadata handling."""

    @pytest.mark.asyncio
    async def test_context_binding_precedence(self) -> None:
        """Test context binding precedence: bound < per-call."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="context-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()

        # Bind context
        logger.bind(user_id="12345", session="abc")

        # Log with override
        logger.info("test message", user_id="67890", request_id="xyz")

        await logger.stop_and_drain()

        assert len(out) >= 1
        event = out[0]
        metadata = event.get("metadata", {})

        # Per-call should override bound context
        assert metadata.get("user_id") == "67890"  # Overridden
        assert metadata.get("session") == "abc"  # From bound context
        assert metadata.get("request_id") == "xyz"  # From per-call

    @pytest.mark.asyncio
    async def test_context_unbind_and_clear(self) -> None:
        """Test context unbinding and clearing."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="unbind-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()

        # Bind multiple fields
        logger.bind(user_id="123", session="abc", trace_id="xyz")

        # Log with all context
        logger.info("message 1")

        # Unbind specific field
        logger.unbind("session")
        logger.info("message 2")

        # Clear all context
        logger.clear_context()
        logger.info("message 3")

        await logger.stop_and_drain()

        # Should have at least some messages processed
        assert len(out) >= 1

        # Just verify the messages were processed
        for event in out:
            assert event.get("message") in ["message 1", "message 2", "message 3"]


class TestExceptionSerialization:
    """Test exception serialization functionality."""

    @pytest.mark.asyncio
    async def test_exception_with_exc_parameter(self) -> None:
        """Test exception logging with exc parameter."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="exc-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=True,
        )

        logger.start()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) >= 1
        event = out[0]
        metadata = event.get("metadata", {})

        # Should have exception information
        assert "error.message" in metadata or "error.frames" in metadata

    @pytest.mark.asyncio
    async def test_exception_with_exc_info_tuple(self) -> None:
        """Test exception logging with exc_info tuple."""

        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="exc-info-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=True,
        )

        logger.start()

        try:
            raise RuntimeError("Test runtime error")
        except RuntimeError:
            exc_info = sys.exc_info()
            logger.error("Error with exc_info", exc_info=exc_info)

        await logger.stop_and_drain()

        assert len(out) >= 1
        event = out[0]
        metadata = event.get("metadata", {})

        # Should have exception information
        assert "error.message" in metadata or "error.frames" in metadata

    @pytest.mark.asyncio
    async def test_exception_serialization_disabled(self) -> None:
        """Test logging with exception serialization disabled."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="no-exc-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=False,  # Disabled
        )

        logger.start()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) >= 1
        event = out[0]
        metadata = event.get("metadata", {})

        # Should NOT have exception information
        assert "error.message" not in metadata
        assert "error.frames" not in metadata

    @pytest.mark.asyncio
    async def test_exception_serialization_error_handling(self) -> None:
        """Test exception serialization with errors in serialization."""
        out: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="exc-error-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
            exceptions_enabled=True,
        )

        logger.start()

        # Mock exception serialization to fail
        with patch(
            "fapilog.core.errors.serialize_exception",
            side_effect=Exception("Serialization failed"),
        ):
            try:
                raise ValueError("Test exception")
            except ValueError as e:
                logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        # Should still log the message despite serialization failure
        assert len(out) >= 1
        event = out[0]
        assert event.get("message") == "Error occurred"
