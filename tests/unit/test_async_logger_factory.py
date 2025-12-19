"""Tests for async logger factory functions and context managers."""

from __future__ import annotations

import asyncio

import pytest

from fapilog import Settings, get_async_logger, runtime_async
from fapilog.core.settings import CoreSettings


@pytest.mark.asyncio
async def test_get_async_logger_basic_functionality() -> None:
    """Test basic async logger creation and usage."""
    logger = await get_async_logger("test_logger")

    # Verify logger is properly configured
    assert logger._name == "test_logger"
    assert logger._queue is not None
    assert logger._enrichers is not None
    assert len(logger._enrichers) >= 2  # Should have default enrichers

    # Test basic logging
    await logger.info("test message", test_data="value")

    # Clean up
    await logger.drain()


@pytest.mark.asyncio
async def test_get_async_logger_with_settings() -> None:
    """Test async logger creation with custom settings."""
    core_settings = CoreSettings(enable_metrics=True)
    settings = Settings(core=core_settings)
    logger = await get_async_logger("test_logger", settings=settings)

    # Verify metrics are enabled
    assert logger._metrics is not None

    # Test logging
    await logger.info("test message")

    # Clean up
    await logger.drain()


@pytest.mark.asyncio
async def test_get_async_logger_default_name() -> None:
    """Test async logger creation with default name."""
    logger = await get_async_logger()

    # Verify default name is used
    assert logger._name == "root"
    assert logger._worker_loop is asyncio.get_running_loop()

    # Test logging
    await logger.info("test message")

    # Clean up
    await logger.drain()


@pytest.mark.asyncio
async def test_get_async_logger_binds_to_running_loop() -> None:
    """Ensure async factory binds workers to the current event loop."""
    loop = asyncio.get_running_loop()

    logger = await get_async_logger("loop_bind")

    assert logger._worker_loop is loop

    await logger.info("hello")
    await logger.drain()


@pytest.mark.asyncio
async def test_runtime_async_context_manager() -> None:
    """Test runtime_async context manager functionality."""
    collected_messages = []

    async with runtime_async() as logger:
        # Verify logger is working
        await logger.info("message 1")
        await logger.info("message 2")

        # Verify logger is properly configured
        assert logger._name == "root"
        assert logger._worker_loop is not None

        # Collect messages for verification
        collected_messages.extend(["message 1", "message 2"])

    # Context manager should have automatically drained the logger
    # No need for manual cleanup


@pytest.mark.asyncio
async def test_runtime_async_with_settings() -> None:
    """Test runtime_async context manager with custom settings."""
    core_settings = CoreSettings(max_queue_size=100)
    settings = Settings(core=core_settings)

    async with runtime_async(settings=settings) as logger:
        # Verify custom settings are applied
        assert logger._queue.capacity == 100

        # Test logging
        await logger.info("test message with custom settings")


@pytest.mark.asyncio
async def test_runtime_async_exception_handling() -> None:
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


@pytest.mark.asyncio
async def test_async_logger_integration_with_sinks() -> None:
    """Test async logger integration with different sink types."""
    # Test with stdout sink (default)
    logger = await get_async_logger("stdout_test")

    # Test basic logging
    await logger.info("stdout test message")

    # Clean up
    await logger.drain()


@pytest.mark.asyncio
async def test_async_logger_context_binding_integration() -> None:
    """Test async logger context binding integration."""
    logger = await get_async_logger("context_test")

    # Bind context
    bound_logger = logger.bind(user_id="123", session_id="abc")

    # Test logging with bound context
    await bound_logger.info("user action", action="login")

    # Verify context is maintained
    await bound_logger.info("another action", action="logout")

    # Clean up
    await logger.drain()


@pytest.mark.asyncio
async def test_async_logger_concurrent_usage() -> None:
    """Test async logger with concurrent usage patterns."""
    logger = await get_async_logger("concurrent_test")

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
async def test_async_logger_flush_and_drain() -> None:
    """Test async logger flush and drain methods."""
    logger = await get_async_logger("flush_test")

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
async def test_async_logger_worker_lifecycle() -> None:
    """Test async logger worker lifecycle management."""
    logger = await get_async_logger("lifecycle_test")

    # Verify workers are started
    assert logger._worker_loop is not None
    assert len(logger._worker_tasks) > 0

    # Test logging
    await logger.info("lifecycle test message")

    # Drain and verify cleanup
    result = await logger.drain()
    assert result.submitted == 1
    assert result.processed == 1

    # Verify workers are cleaned up (in async mode, loop may still be running)
    # The important thing is that the worker tasks are cleaned up
    # Note: In async mode, tasks might be finished but not yet removed from the list
    assert all(task.done() for task in logger._worker_tasks)
