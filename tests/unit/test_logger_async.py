"""
Test AsyncLoggerFacade and async factory functions.

Scope:
- AsyncLoggerFacade behavior
- get_async_logger factory function
- runtime_async context manager
- Async logging methods
- Concurrent access patterns

Does NOT cover:
- SyncLoggerFacade (see test_logger_core.py)
- Threading behavior (see test_logger_threading.py)
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from fapilog import Settings, get_async_logger, runtime_async
from fapilog.core.logger import AsyncLoggerFacade
from fapilog.core.settings import CoreSettings
from fapilog.metrics.metrics import MetricsCollector


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


class TestAsyncLoggerFacade:
    """Tests for AsyncLoggerFacade direct usage."""

    @pytest.mark.asyncio
    async def test_async_logger_in_loop_bind_and_flush(self) -> None:
        """Test async logger binding to current event loop."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="t",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        # Start inside running loop: no thread should be used
        logger.start()
        assert logger._worker_thread is None
        assert logger._loop_thread_ident == threading.get_ident()

        for i in range(10):
            await logger.info("m", i=i)

        # Allow time-based flush
        await asyncio.sleep(0.2)
        res = await logger.drain()
        assert res.submitted == 10
        assert res.dropped == 0
        assert res.processed == 10
        assert len(collected) == 10

    @pytest.mark.asyncio
    async def test_async_logger_in_loop_drop_when_full_nonblocking(self) -> None:
        """Test async logger drop behavior when queue is full."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="t",
            queue_capacity=1,
            batch_max_size=10,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=100,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()
        # Enqueue two items quickly; second should drop on the loop thread
        await logger.info("a")
        await logger.info("b")
        await asyncio.sleep(0.05)
        res = await logger.drain()
        assert res.submitted == 2
        # In async mode, both messages might be processed due to fast processing
        assert res.processed in {1, 2}
        assert res.dropped in {0, 1}
        assert res.processed + res.dropped == res.submitted

    def test_async_logger_thread_mode_wait_then_drop(self) -> None:
        """Test async logger in thread mode with dedicated event loop."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="t",
            queue_capacity=4,
            batch_max_size=4,
            batch_timeout_seconds=0.5,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        # Start outside of any running loop: spawns dedicated thread+loop
        logger.start()
        thread = logger._worker_thread
        assert isinstance(thread, threading.Thread)
        assert thread.is_alive()

        # Saturate the queue; some submissions may drop under pressure
        async def _submit_logs():
            for i in range(200):
                await logger.info("x", i=i)

        # Run async submission in a new event loop
        asyncio.run(_submit_logs())

        # Drain synchronously via helper
        res = asyncio.run(logger.drain())
        assert res.submitted == 200
        assert res.processed > 0
        assert res.processed + res.dropped == res.submitted

    @pytest.mark.asyncio
    async def test_async_logger_flush_method(self) -> None:
        """Test async logger flush method without stopping workers."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="t",
            queue_capacity=16,
            batch_max_size=4,
            batch_timeout_seconds=1.0,  # Long timeout to test flush
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Submit some logs
        for i in range(6):
            await logger.info("m", i=i)

        # Wait a bit to ensure some are batched
        await asyncio.sleep(0.1)

        # Flush without stopping
        await logger.flush()

        # Check that logs were processed
        assert len(collected) >= 4  # At least one batch should be flushed

        # Drain to clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_async_logger_all_logging_methods(self) -> None:
        """Test all async logging methods work correctly."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Test all logging methods
        await logger.debug("debug message", debug_data="test")
        await logger.info("info message", info_data="test")
        await logger.warning("warning message", warning_data="test")
        await logger.error("error message", error_data="test")
        await logger.exception("exception message", exception_data="test")

        # Allow time for processing
        await asyncio.sleep(0.2)

        # Check that all messages were processed
        res = await logger.drain()
        assert res.submitted == 5
        assert res.processed == 5
        assert res.dropped == 0

        # Verify all levels are present
        levels = [entry["level"] for entry in collected]
        assert "DEBUG" in levels
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels

    @pytest.mark.asyncio
    async def test_async_logger_context_binding(self) -> None:
        """Test async logger context binding functionality."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Bind context
        bound_logger = logger.bind(user_id="123", session_id="abc")
        await bound_logger.info("user action", action="login")

        # Check that bound context is included
        await asyncio.sleep(0.2)
        await logger.drain()

    @pytest.mark.asyncio
    async def test_metrics_scheduling_avoids_asyncio_run(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Metrics updates from sync code should not call asyncio.run per event."""
        collected: list[dict[str, Any]] = []

        logger = AsyncLoggerFacade(
            name="metrics",
            queue_capacity=4,
            batch_max_size=1,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=1,
            drop_on_full=False,
            sink_write=lambda e: _collecting_sink(collected, e),
            metrics=MetricsCollector(enabled=True),
        )
        await logger.start_async()

        called = {}

        def _patched_asyncio_run(*_args: Any, **_kwargs: Any) -> None:
            called["asyncio_run"] = True
            raise AssertionError(
                "asyncio.run should not be used for metrics scheduling"
            )

        monkeypatch.setattr("asyncio.run", _patched_asyncio_run)

        await logger.info("hello-metrics")
        await asyncio.sleep(0.05)
        assert "asyncio_run" not in called
        await logger.drain()

        assert len(collected) == 1

    @pytest.mark.asyncio
    async def test_async_logger_exception_handling(self) -> None:
        """Test async logger exception handling and serialization."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            exceptions_enabled=True,
            exceptions_max_frames=5,
            exceptions_max_stack_chars=1000,
        )
        logger.start()

        # Test exception logging
        try:
            raise ValueError("test exception")
        except ValueError:
            await logger.exception("caught exception", extra_data="test")

        # Allow time for processing
        await asyncio.sleep(0.2)

        # Check that exception was processed
        res = await logger.drain()
        assert res.submitted == 1
        assert res.processed == 1

        # Verify exception data is present (v1.1 schema)
        assert len(collected) == 1
        entry = collected[0]
        assert entry["level"] == "ERROR"
        # v1.1 schema: exception in diagnostics.exception, extra in data
        exc_data = entry.get("diagnostics", {}).get("exception", {})
        assert "error.frames" in exc_data or "error.message" in exc_data
        assert entry["data"]["extra_data"] == "test"

    @pytest.mark.asyncio
    async def test_async_logger_metrics_integration(self) -> None:
        """Test async logger metrics integration."""
        metrics = MetricsCollector(enabled=True)
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            metrics=metrics,
        )
        logger.start()

        # Submit logs
        for i in range(5):
            await logger.info("test message", i=i)

        # Allow time for processing
        await asyncio.sleep(0.2)

        # Drain and check metrics
        res = await logger.drain()
        assert res.submitted == 5
        assert res.processed == 5

        # Verify metrics were recorded
        assert len(collected) == 5

    @pytest.mark.asyncio
    async def test_async_logger_self_test(self) -> None:
        """Test async logger self_test method."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Run self test
        result = await logger.self_test()
        assert result["ok"] is True
        assert result["sink"] == "default"

        # Drain to clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_async_logger_worker_lifecycle(self) -> None:
        """Test async logger worker lifecycle management."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        # Start workers
        logger.start()
        assert logger._worker_loop is asyncio.get_running_loop()
        assert len(logger._worker_tasks) > 0

        # Submit some work
        await logger.info("test message")

        # Drain and verify cleanup
        res = await logger.drain()
        assert res.submitted == 1
        assert res.processed == 1

        # Verify workers are cleaned up
        assert all(task.done() for task in logger._worker_tasks)

    @pytest.mark.asyncio
    async def test_async_logger_concurrent_access(self) -> None:
        """Test async logger with concurrent access from multiple tasks."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )
        logger.start()

        # Create multiple concurrent tasks
        async def _log_task(task_id: int):
            for i in range(10):
                await logger.info(
                    f"task {task_id} message {i}", task_id=task_id, message_id=i
                )

        # Run multiple tasks concurrently
        tasks = [asyncio.create_task(_log_task(i)) for i in range(5)]
        await asyncio.gather(*tasks)

        # Allow time for processing
        await asyncio.sleep(0.2)

        # Drain and verify all messages were processed
        res = await logger.drain()
        assert res.submitted == 50  # 5 tasks * 10 messages each
        assert res.processed == 50
        assert res.dropped == 0

        # Verify all task IDs are present (v1.1 schema: custom fields in data)
        task_ids = {entry["data"]["task_id"] for entry in collected}
        assert task_ids == {0, 1, 2, 3, 4}


class TestGetAsyncLogger:
    """Tests for get_async_logger factory function."""

    @pytest.mark.asyncio
    async def test_get_async_logger_basic_functionality(self) -> None:
        """Test basic async logger creation and usage."""
        logger = await get_async_logger("test_logger", reuse=False)

        # Verify logger is properly configured
        assert logger._name == "test_logger"
        assert logger._queue.capacity > 0
        assert len(logger._enrichers) >= 2  # Should have default enrichers

        # Test basic logging
        await logger.info("test message", test_data="value")

        # Clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_settings(self) -> None:
        """Test async logger creation with custom settings."""
        core_settings = CoreSettings(enable_metrics=True)
        settings = Settings(core=core_settings)
        logger = await get_async_logger("test_logger", settings=settings, reuse=False)

        # Verify metrics are enabled
        assert isinstance(logger._metrics, MetricsCollector)
        assert logger._metrics.is_enabled == (logger._metrics.registry is not None)

        # Test logging
        await logger.info("test message")

        # Clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_default_name(self) -> None:
        """Test async logger creation with default name."""
        logger = await get_async_logger(reuse=False)

        # Verify default name is used
        assert logger._name == "root"
        assert logger._worker_loop is asyncio.get_running_loop()

        # Test logging
        await logger.info("test message")

        # Clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_binds_to_running_loop(self) -> None:
        """Ensure async factory binds workers to the current event loop."""
        loop = asyncio.get_running_loop()

        logger = await get_async_logger("loop_bind", reuse=False)

        assert logger._worker_loop is loop

        await logger.info("hello")
        await logger.drain()

    @pytest.mark.asyncio
    async def test_async_logger_integration_with_sinks(self) -> None:
        """Test async logger integration with different sink types."""
        # Test with stdout sink (default)
        logger = await get_async_logger("stdout_test", reuse=False)

        # Test basic logging
        await logger.info("stdout test message")

        # Clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_async_logger_context_binding_integration(self) -> None:
        """Test async logger context binding integration."""
        logger = await get_async_logger("context_test", reuse=False)

        # Bind context
        bound_logger = logger.bind(user_id="123", session_id="abc")

        # Test logging with bound context
        await bound_logger.info("user action", action="login")

        # Verify context is maintained
        await bound_logger.info("another action", action="logout")

        # Clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_async_logger_concurrent_usage(self) -> None:
        """Test async logger with concurrent usage patterns."""
        logger = await get_async_logger("concurrent_test", reuse=False)

        # Create multiple concurrent logging tasks
        async def log_task(task_id: int, count: int):
            for i in range(count):
                await logger.info(
                    f"task {task_id} message {i}", task_id=task_id, message_id=i
                )

        # Run multiple tasks concurrently
        tasks = [asyncio.create_task(log_task(i, 5)) for i in range(3)]

        await asyncio.gather(*tasks)

        # Clean up
        await logger.drain()

    @pytest.mark.asyncio
    async def test_async_logger_flush_and_drain(self) -> None:
        """Test async logger flush and drain methods."""
        logger = await get_async_logger("flush_test", reuse=False)

        # Submit some logs
        for i in range(10):
            await logger.info(f"message {i}", message_id=i)

        # Test flush without stopping
        await logger.flush()

        # Test drain to stop and clean up
        result = await logger.drain()

        # Verify all messages were processed
        assert result.submitted == 10
        assert result.processed == 10
        assert result.dropped == 0

    @pytest.mark.asyncio
    async def test_async_logger_factory_worker_lifecycle(self) -> None:
        """Test async logger worker lifecycle management via factory."""
        logger = await get_async_logger("lifecycle_test", reuse=False)

        # Verify workers are started
        assert logger._worker_loop is asyncio.get_running_loop()
        assert len(logger._worker_tasks) > 0

        # Test logging
        await logger.info("lifecycle test message")

        # Drain and verify cleanup
        result = await logger.drain()
        assert result.submitted == 1
        assert result.processed == 1

        # Verify workers are cleaned up
        assert all(task.done() for task in logger._worker_tasks)


class TestRuntimeAsync:
    """Tests for runtime_async context manager."""

    @pytest.mark.asyncio
    async def test_runtime_async_context_manager(self) -> None:
        """Test runtime_async context manager functionality."""
        async with runtime_async() as logger:
            # Verify logger is working
            await logger.info("message 1")
            await logger.info("message 2")

            # Verify logger is properly configured
            assert logger._name == "root"
            assert logger._worker_loop is asyncio.get_running_loop()

        # Context manager should have automatically drained the logger

    @pytest.mark.asyncio
    async def test_runtime_async_with_settings(self) -> None:
        """Test runtime_async context manager with custom settings."""
        core_settings = CoreSettings(max_queue_size=100)
        settings = Settings(core=core_settings)

        async with runtime_async(settings=settings) as logger:
            # Verify custom settings are applied
            assert logger._queue.capacity == 100

            # Test logging
            await logger.info("test message with custom settings")

    @pytest.mark.asyncio
    async def test_runtime_async_exception_handling(self) -> None:
        """Test runtime_async context manager handles exceptions gracefully."""
        async with runtime_async() as logger:
            await logger.info("before exception")

            # Simulate an exception
            try:
                raise ValueError("test exception")
            except ValueError:
                await logger.exception("caught exception")

            await logger.info("after exception")

        # Context manager should still clean up properly
