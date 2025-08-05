"""
Unit tests for AsyncLogger.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from fapilog.core.events import EventCategory, LogEvent
from fapilog.core.logger import AsyncLogger
from fapilog.core.settings import UniversalSettings


class TestAsyncLogger:
    """Test AsyncLogger functionality."""

    @pytest.fixture  # type: ignore[misc]
    async def logger_settings(self) -> UniversalSettings:
        """Create test settings."""
        return UniversalSettings(
            level="DEBUG",
            sinks=["stdout"],
            async_processing=True,
            zero_copy_operations=True,
            parallel_processing=True,
            max_workers=2,
        )

    @pytest.fixture  # type: ignore[misc]
    async def logger(self, logger_settings: UniversalSettings) -> AsyncLogger:
        """Create test logger."""
        return await AsyncLogger.create(logger_settings)

    async def test_logger_creation(self, logger_settings: UniversalSettings) -> None:
        """Test logger creation and initialization."""
        logger = await AsyncLogger.create(logger_settings)

        assert logger.settings == logger_settings
        assert logger._running is True
        assert logger._queue is not None
        assert len(logger._workers) == 2

        await logger.shutdown()

    async def test_logger_context_manager(
        self, logger_settings: UniversalSettings
    ) -> None:
        """Test logger as async context manager."""
        async with await AsyncLogger.create(logger_settings) as logger:
            assert logger._running is True
            assert logger._queue is not None

    async def test_info_logging(self, logger: AsyncLogger) -> None:
        """Test info level logging."""
        with patch.object(logger, "_log", new_callable=AsyncMock) as mock_log:
            await logger.info("Test message", source="test")
            mock_log.assert_called_once_with("INFO", "Test message", source="test")

    async def test_debug_logging(self, logger: AsyncLogger) -> None:
        """Test debug level logging."""
        with patch.object(logger, "_log", new_callable=AsyncMock) as mock_log:
            await logger.debug("Debug message")
            mock_log.assert_called_once_with("DEBUG", "Debug message")

    async def test_warning_logging(self, logger: AsyncLogger) -> None:
        """Test warning level logging."""
        with patch.object(logger, "_log", new_callable=AsyncMock) as mock_log:
            await logger.warning("Warning message")
            mock_log.assert_called_once_with("WARNING", "Warning message")

    async def test_error_logging(self, logger: AsyncLogger) -> None:
        """Test error level logging."""
        with patch.object(logger, "_log", new_callable=AsyncMock) as mock_log:
            await logger.error("Error message")
            mock_log.assert_called_once_with("ERROR", "Error message")

    async def test_critical_logging(self, logger: AsyncLogger) -> None:
        """Test critical level logging."""
        with patch.object(logger, "_log", new_callable=AsyncMock) as mock_log:
            await logger.critical("Critical message")
            mock_log.assert_called_once_with("CRITICAL", "Critical message")

    async def test_log_with_metadata(self, logger: AsyncLogger) -> None:
        """Test logging with rich metadata."""
        with patch.object(logger._queue, "put", new_callable=AsyncMock) as mock_put:
            await logger.info(
                "Test message",
                source="test_source",
                category=EventCategory.BUSINESS,
                tags={"key": "value"},
                context={"request_id": "123"},
                metrics={"duration": 1.5},
                correlation_id="corr-123",
            )

            # Verify the LogEvent was created with correct metadata
            mock_put.assert_called_once()
            event = mock_put.call_args[0][0]

            assert isinstance(event, LogEvent)
            assert event.message == "Test message"
            assert event.level == "INFO"
            assert event.source == "test_source"
            assert event.category == EventCategory.BUSINESS
            assert event.tags == {"key": "value"}
            assert event.context == {"request_id": "123"}
            assert event.metrics == {"duration": 1.5}
            assert event.correlation_id == "corr-123"

    async def test_log_with_custom_context(self, logger: AsyncLogger) -> None:
        """Test logging with custom context fields."""
        with patch.object(logger._queue, "put", new_callable=AsyncMock) as mock_put:
            await logger.info(
                "Test message", custom_field="custom_value", another_field=42
            )

            event = mock_put.call_args[0][0]
            assert event.context["custom_field"] == "custom_value"
            assert event.context["another_field"] == 42

    async def test_synchronous_processing_when_no_queue(self) -> None:
        """Test fallback to synchronous processing when queue is not running."""
        settings = UniversalSettings(async_processing=False)
        logger = AsyncLogger(settings)

        with patch.object(
            logger, "_process_event", new_callable=AsyncMock
        ) as mock_process:
            await logger.info("Test message")
            mock_process.assert_called_once()

    async def test_zero_copy_processing(self, logger: AsyncLogger) -> None:
        """Test zero-copy operations."""
        with patch.object(
            logger, "_process_zero_copy", new_callable=AsyncMock
        ) as mock_zero_copy:
            event = LogEvent(message="test", level="INFO", timestamp=datetime.now())
            await logger._process_event(event)
            mock_zero_copy.assert_called_once_with(event)

    async def test_standard_processing(self) -> None:
        """Test standard (non-zero-copy) processing."""
        settings = UniversalSettings(zero_copy_operations=False)
        logger = await AsyncLogger.create(settings)

        with patch.object(
            logger, "_process_standard", new_callable=AsyncMock
        ) as mock_standard:
            event = LogEvent(message="test", level="INFO", timestamp=datetime.now())
            await logger._process_event(event)
            mock_standard.assert_called_once_with(event)

        await logger.shutdown()

    async def test_parallel_sink_writing(self, logger: AsyncLogger) -> None:
        """Test parallel writing to multiple sinks."""
        logger.settings.sinks = ["sink1", "sink2", "sink3"]

        with patch.object(
            logger, "_write_to_sink", new_callable=AsyncMock
        ) as mock_write:
            event_dict = {"message": "test"}
            await logger._write_to_sinks_parallel(event_dict)

            assert mock_write.call_count == 3
            call_args = [call[0] for call in mock_write.call_args_list]
            assert ("sink1", event_dict) in call_args
            assert ("sink2", event_dict) in call_args
            assert ("sink3", event_dict) in call_args

    async def test_sequential_sink_writing(self, logger: AsyncLogger) -> None:
        """Test sequential writing to multiple sinks."""
        logger.settings.sinks = ["sink1", "sink2"]

        with patch.object(
            logger, "_write_to_sink", new_callable=AsyncMock
        ) as mock_write:
            event_dict = {"message": "test"}
            await logger._write_to_sinks_sequential(event_dict)

            assert mock_write.call_count == 2

    async def test_sink_writing(self, logger: AsyncLogger) -> None:
        """Test writing to a specific sink."""
        with patch("builtins.print") as mock_print:
            await logger._write_to_sink("test_sink", {"message": "test"})
            mock_print.assert_called_once_with(
                "Writing to sink test_sink: {'message': 'test'}"
            )

    async def test_worker_error_handling(
        self, logger_settings: UniversalSettings
    ) -> None:
        """Test worker error handling."""
        logger = await AsyncLogger.create(logger_settings)

        # Simulate worker error
        with patch.object(
            logger, "_process_event", side_effect=Exception("Test error")
        ):
            with patch("builtins.print") as mock_print:
                # Put an event in the queue
                if logger._queue is not None:
                    await logger._queue.put(
                        LogEvent(message="test", level="INFO", timestamp=datetime.now())
                    )

                    # Let worker process the event
                    await asyncio.sleep(0.1)

                    # Check that error was printed
                    mock_print.assert_called_with("Worker error: Test error")

        await logger.shutdown()

    async def test_shutdown_graceful(self, logger: AsyncLogger) -> None:
        """Test graceful shutdown."""
        # Add some events to the queue
        if logger._queue is not None:
            for i in range(3):
                await logger._queue.put(
                    LogEvent(
                        message=f"test {i}", level="INFO", timestamp=datetime.now()
                    )
                )

        with patch.object(
            logger, "_process_event", new_callable=AsyncMock
        ) as mock_process:
            await logger.shutdown()

            # Should process remaining events
            assert mock_process.call_count >= 3
            assert logger._running is False

    async def test_shutdown_cancels_workers(self, logger: AsyncLogger) -> None:
        """Test that shutdown cancels all workers."""
        workers_before = logger._workers.copy()

        await logger.shutdown()

        # All workers should be cancelled
        for worker in workers_before:
            assert worker.cancelled() or worker.done()

    async def test_async_processing_disabled(self) -> None:
        """Test logger with async processing disabled."""
        settings = UniversalSettings(async_processing=False)
        logger = AsyncLogger(settings)
        await logger._initialize()

        assert logger._queue is None
        assert logger._workers == []
        assert logger._running is False

    async def test_non_zero_copy_operations(self) -> None:
        """Test processing without zero-copy operations."""
        settings = UniversalSettings(
            zero_copy_operations=False, parallel_processing=False
        )
        logger = await AsyncLogger.create(settings)

        with patch.object(
            logger, "_write_to_sinks_sequential", new_callable=AsyncMock
        ) as mock_sequential:
            event = LogEvent(message="test", level="INFO", timestamp=datetime.now())
            await logger._process_standard(event)
            mock_sequential.assert_called_once()

        await logger.shutdown()

    async def test_parallel_processing_disabled(self) -> None:
        """Test zero-copy operations with parallel processing disabled."""
        settings = UniversalSettings(
            zero_copy_operations=True, parallel_processing=False
        )
        logger = await AsyncLogger.create(settings)

        with patch.object(
            logger, "_write_to_sinks_sequential", new_callable=AsyncMock
        ) as mock_sequential:
            event = LogEvent(message="test", level="INFO", timestamp=datetime.now())
            await logger._process_zero_copy(event)
            mock_sequential.assert_called_once()

        await logger.shutdown()
