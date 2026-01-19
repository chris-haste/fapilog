"""
Tests for logger execution modes and worker lifecycle.

Scope:
- Thread vs event loop execution modes
- Async logger in event loop mode
- Sync logger thread mode
- Worker lifecycle (startup, run, cleanup)
- Worker task cancellation
- Flush functionality
- Worker exception containment
- Context binding and metadata handling
"""

import asyncio
import threading
import time
from typing import Any
from unittest.mock import patch

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


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
        # v1.1 schema: user_id and request_id are context fields, session is data
        context = event.get("context", {})
        data = event.get("data", {})

        assert context.get("user_id") == "67890"  # extra overrides bound_context
        assert data.get("session") == "abc"  # session is not a context field
        assert context.get("request_id") == "xyz"

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
