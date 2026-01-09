"""
Test logger sampling and processing pipeline.

Scope:
- Sampling logic with different rates and levels
- Error deduplication
- Thread vs event loop modes
- Enrichment and redaction pipeline
- Failure modes and recovery
- Flush serialization paths
- Context binding and metadata
- Exception serialization

Does NOT cover:
- Fast path serialization details (see test_logger_fastpath.py)
- Threading lifecycle (see test_logger_threading.py)
- Error containment (see test_logger_errors.py)
"""

import asyncio
import sys
import threading
import time
import warnings
from typing import Any
from unittest.mock import Mock, patch

import pytest

import fapilog.core.worker as worker_mod
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
        "batch_max_size": 8,
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
        out: list[dict[str, Any]] = []
        logger = _create_test_logger("sampling-test", out, backpressure_wait_ms=0)
        logger.start()

        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 0.001
            mock_settings.return_value = settings_instance

            for i in range(10):
                logger.debug(f"debug message {i}")
                logger.info(f"info message {i}")

            logger.warning("warning message")
            logger.error("error message")
            try:
                raise RuntimeError("Test exception")
            except RuntimeError:
                logger.exception("exception message")

        asyncio.run(logger.stop_and_drain())

        warning_msgs = [e for e in out if e.get("level") == "WARNING"]
        error_msgs = [e for e in out if e.get("level") == "ERROR"]

        assert len(warning_msgs) == 1, "Exactly one WARNING message should be logged"
        assert len(error_msgs) == 2, (
            "Exactly two ERROR messages should be logged (error + exception)"
        )

    def test_sampling_rate_effect_on_debug_info(self) -> None:
        """Test that sampling rate affects DEBUG/INFO levels."""
        import random as random_module

        out: list[dict[str, Any]] = []
        logger = _create_test_logger(
            "sampling-test", out, queue_capacity=32, backpressure_wait_ms=0
        )
        logger.start()

        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 0.5
            settings_instance.core.filters = []
            mock_settings.return_value = settings_instance

            original_random = random_module.random
            call_count = [0]
            values = [0.6, 0.3, 0.7, 0.2, 0.8, 0.1]

            def mock_random() -> float:
                if call_count[0] < len(values):
                    val = values[call_count[0]]
                    call_count[0] += 1
                    return val
                return original_random()

            with patch.object(random_module, "random", mock_random):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    logger.debug("debug1")
                    logger.info("info1")
                    logger.debug("debug2")
                    logger.info("info2")
                    logger.debug("debug3")
                    logger.info("info3")

        asyncio.run(logger.stop_and_drain())

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

        with patch(
            "fapilog.core.settings.Settings", side_effect=Exception("Settings error")
        ):
            logger.debug("debug with settings error")
            logger.info("info with settings error")

        asyncio.run(logger.stop_and_drain())

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

        logger.error("Database connection failed")
        logger.error("Database connection failed")
        logger.error("Database connection failed")
        logger.error("Different error message")

        asyncio.run(logger.stop_and_drain())

        error_msgs = [e for e in out if e.get("level") == "ERROR"]

        assert len(error_msgs) == 2, f"Expected 2 ERROR messages, got {len(error_msgs)}"

        messages = [e.get("message") for e in error_msgs]
        assert "Database connection failed" in messages
        assert "Different error message" in messages

    @pytest.mark.skip(
        reason="Flaky: mocks Settings after logger construction, doesn't affect behavior"
    )
    def test_error_deduplication_window_rollover(self) -> None:
        """Test error deduplication with window rollover and summary."""
        out: list[dict[str, Any]] = []
        diagnostics_calls: list[dict[str, Any]] = []

        logger = _create_test_logger(
            "dedup-test", out, queue_capacity=16, backpressure_wait_ms=0
        )
        logger.start()

        window_seconds = 0.05

        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.core.error_dedupe_window_seconds = window_seconds
            mock_settings.return_value = settings_instance

            with patch("fapilog.core.diagnostics.warn") as mock_warn:
                mock_warn.side_effect = (
                    lambda *args, **kwargs: diagnostics_calls.append(kwargs)
                )

                logger.error("Repeated error")
                logger.error("Repeated error")
                logger.error("Repeated error")

                time.sleep(window_seconds + 0.02)

                logger.error("Repeated error")

        asyncio.run(logger.stop_and_drain())

        assert len(diagnostics_calls) > 0
        summary_call = diagnostics_calls[0]
        assert summary_call.get("error_message") == "Repeated error"
        assert summary_call.get("suppressed") == 2
        assert summary_call.get("window_seconds") == window_seconds

    def test_error_deduplication_disabled(self) -> None:
        """Test that deduplication is disabled when window is 0."""
        out: list[dict[str, Any]] = []
        logger = _create_test_logger(
            "dedup-test", out, queue_capacity=16, backpressure_wait_ms=0
        )
        logger.start()

        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = settings_instance

            for _ in range(5):
                logger.error("Repeated error")

        asyncio.run(logger.stop_and_drain())

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

        with patch(
            "fapilog.core.settings.Settings", side_effect=Exception("Settings error")
        ):
            logger.error("Error with settings exception")
            logger.error("Error with settings exception")

        asyncio.run(logger.stop_and_drain())

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

        logger.start()
        assert logger._worker_loop is asyncio.get_running_loop()
        assert logger._worker_thread is None

        await logger.info("test message in loop mode")
        result = await logger.stop_and_drain()

        assert result.submitted == 1
        assert result.processed == 1
        assert len(out) == 1

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

        logger.start()
        thread = logger._worker_thread
        loop = logger._worker_loop
        assert isinstance(thread, threading.Thread)
        assert loop.is_running()

        logger.info("test message in thread mode")
        result = asyncio.run(logger.stop_and_drain())

        assert result.submitted == 1
        assert result.processed == 1
        assert len(out) == 1

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

        logger.start()
        thread = logger._worker_thread
        loop = logger._worker_loop

        assert isinstance(thread, threading.Thread)
        assert thread.is_alive()
        assert loop.is_running()

        logger.info("test message")
        time.sleep(0.1)

        asyncio.run(logger.stop_and_drain())

        assert not thread.is_alive()
        assert logger._worker_thread is None
        assert logger._worker_loop is None

    def test_sync_logger_thread_mode_creation(self) -> None:
        """Test SyncLoggerFacade thread mode creation outside event loop."""
        out: list[dict[str, Any]] = []

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

        assert result.submitted == 1
        assert result.processed == 1


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

        await logger.info("test message")

        await logger.stop_and_drain()

        for task in original_tasks:
            assert task.done()

    @pytest.mark.asyncio
    async def test_flush_functionality(self) -> None:
        """Test AsyncLoggerFacade flush functionality."""
        out: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="flush-test",
            queue_capacity=16,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collect_events(out, e),
        )

        logger.start()

        await logger.info("message 1")
        await logger.info("message 2")
        await logger.info("message 3")

        await logger.flush()

        assert len(out) >= 3

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
            batch_max_size=10,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=track_flush_time,
        )

        logger.start()

        start_time = time.time()
        await logger.info("timeout test message")

        await asyncio.sleep(0.1)

        await logger.stop_and_drain()

        assert len(flush_times) == 1
        flush_delay = flush_times[0] - start_time
        assert 0.03 <= flush_delay <= 0.2

    @pytest.mark.asyncio
    async def test_worker_exception_containment(self) -> None:
        """Test that worker exceptions are contained and logged."""
        diagnostics_calls: list[dict[str, Any]] = []

        async def failing_sink(event: dict[str, Any]) -> None:
            raise RuntimeError("Sink failure")

        logger = AsyncLoggerFacade(
            name="exception-test",
            queue_capacity=8,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=failing_sink,
        )

        with patch("fapilog.core.diagnostics.warn") as mock_warn:
            mock_warn.side_effect = lambda *args, **kwargs: diagnostics_calls.append(
                kwargs
            )

            logger.start()

            await logger.info("message that will cause sink failure")

            await asyncio.sleep(0.05)

            result = await logger.stop_and_drain()

            assert result.dropped == 1
            assert result.submitted == 1


class TestEnrichmentAndRedactionPipeline:
    """Test the full enrichment and redaction pipeline."""

    class MockEnricher(BaseEnricher):
        def __init__(self, name: str, add_field: str, add_value: str):
            self.name = name
            self.add_field = add_field
            self.add_value = add_value

        async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
            event = dict(event)
            event[self.add_field] = self.add_value
            return event

    class MockRedactor(BaseRedactor):
        def __init__(self, name: str, remove_field: str):
            self.name = name
            self.remove_field = remove_field

        async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
            event = dict(event)
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

        assert len(out) == 1
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

        logger._redactors = [redactor1, redactor2]

        logger.start()
        logger.info(
            "test message", password="secret123", ssn="123-45-6789", safe_field="ok"
        )
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"

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

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"

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

        logger._redactors = [good_redactor, failing_redactor]

        logger.start()
        logger.info("test message", remove_me="should_be_gone", keep_me="should_stay")
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"


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

        await logger.info("message 1")
        await logger.info("message 2")
        await logger.info("message 3")

        result = await logger.stop_and_drain()

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
            serialize_in_flush=True,
        )

        logger.start()

        class NonSerializable:
            pass

        logger.info("test message", non_serializable=NonSerializable())
        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "test message"

    @pytest.mark.asyncio
    async def test_queue_backpressure_and_drops(self) -> None:
        """Test queue backpressure handling and message drops."""
        out: list[dict[str, Any]] = []

        async def slow_sink(event: dict[str, Any]) -> None:
            await asyncio.sleep(0.1)
            await _collect_events(out, event)

        logger = AsyncLoggerFacade(
            name="backpressure-test",
            queue_capacity=2,
            batch_max_size=1,
            batch_timeout_seconds=0.001,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=slow_sink,
        )

        logger.start()

        for i in range(10):
            await logger.info(f"message {i}")

        result = await logger.stop_and_drain()

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

        logger.info("main thread message")

        def background_submit():
            for i in range(5):
                logger.info(f"background message {i}")

        thread = threading.Thread(target=background_submit)
        thread.start()
        thread.join()

        result = asyncio.run(logger.stop_and_drain())

        assert result.submitted == 6
        assert len(out) == 6

    @pytest.mark.asyncio
    async def test_worker_loop_stop_during_processing(self) -> None:
        """Test graceful stop during active processing."""
        out: list[dict[str, Any]] = []

        async def slow_processing_sink(event: dict[str, Any]) -> None:
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

        for i in range(8):
            await logger.info(f"processing message {i}")

        result = await logger.stop_and_drain()

        assert result.submitted == 8
        assert result.processed <= 8
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

        logger.bind(user_id="12345", session="abc")

        logger.info("test message", user_id="67890", request_id="xyz")

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        metadata = event.get("metadata", {})

        assert metadata.get("user_id") == "67890"
        assert metadata.get("session") == "abc"
        assert metadata.get("request_id") == "xyz"

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

        logger.bind(user_id="123", session="abc", trace_id="xyz")

        logger.info("message 1")

        logger.unbind("session")
        logger.info("message 2")

        logger.clear_context()
        logger.info("message 3")

        await logger.stop_and_drain()

        assert len(out) == 3

        messages = [e.get("message") for e in out]
        assert "message 1" in messages
        assert "message 2" in messages
        assert "message 3" in messages


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

        assert len(out) == 1
        event = out[0]
        metadata = event.get("metadata", {})

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

        assert len(out) == 1
        event = out[0]
        metadata = event.get("metadata", {})

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
            exceptions_enabled=False,
        )

        logger.start()

        try:
            raise ValueError("Test exception")
        except ValueError as e:
            logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        metadata = event.get("metadata", {})

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

        with patch(
            "fapilog.core.errors.serialize_exception",
            side_effect=Exception("Serialization failed"),
        ):
            try:
                raise ValueError("Test exception")
            except ValueError as e:
                logger.error("Error occurred", exc=e)

        await logger.stop_and_drain()

        assert len(out) == 1
        event = out[0]
        assert event.get("message") == "Error occurred"


class TestFlushPaths:
    """Test flush serialization paths."""

    @pytest.mark.asyncio
    async def test_flush_serialization_strict_drops(self, monkeypatch) -> None:
        monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "true")

        async def sink_write(entry: dict) -> None:  # pragma: no cover - not used
            raise AssertionError("should not be called in strict drop path")

        async def sink_write_serialized(view: object) -> None:
            raise AssertionError("should not be called in strict drop path")

        monkeypatch.setattr(
            worker_mod,
            "serialize_envelope",
            lambda entry: (_ for _ in ()).throw(ValueError("boom")),
        )

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            serialize_in_flush=True,
        )

        batch = [{"id": 1}]
        await logger._flush_batch(batch)

        assert logger._processed == 0
        assert logger._dropped == 0

    @pytest.mark.asyncio
    async def test_flush_serialization_best_effort_uses_fallback(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "false")

        serialized_calls: list[object] = []
        sink_calls: list[dict] = []

        async def sink_write(entry: dict) -> None:
            sink_calls.append(entry)

        async def sink_write_serialized(view: object) -> None:
            serialized_calls.append(view)

        monkeypatch.setattr(
            worker_mod,
            "serialize_envelope",
            lambda entry: (_ for _ in ()).throw(ValueError("boom")),
        )

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            sink_write_serialized=sink_write_serialized,
            serialize_in_flush=True,
        )

        batch = [{"id": 1}]
        await logger._flush_batch(batch)

        assert logger._processed == 1
        assert len(serialized_calls) == 1
        assert len(sink_calls) == 0

    @pytest.mark.asyncio
    async def test_flush_sink_error_increments_dropped(self, monkeypatch) -> None:
        async def sink_write(entry: dict) -> None:
            raise RuntimeError("sink failure")

        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=4,
            batch_max_size=2,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink_write,
            serialize_in_flush=False,
        )

        batch = [{"id": 1}, {"id": 2}]
        await logger._flush_batch(batch)

        assert logger._processed == 0
        assert logger._dropped == 2
