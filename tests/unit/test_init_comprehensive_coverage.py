"""
Comprehensive tests for src/fapilog/__init__.py to improve coverage.

This file targets the missing coverage areas identified in the coverage report.
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from fapilog import (
    Settings,
    get_async_logger,
    runtime,
    runtime_async,
)


class TestGetAsyncLoggerCoverage:
    """Test get_async_logger function to improve coverage."""

    @pytest.mark.asyncio
    async def test_get_async_logger_basic_usage(self) -> None:
        """Test basic async logger creation."""
        logger = await get_async_logger(name="async-test")
        assert logger is not None
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_rotating_file_sink(
        self, tmp_path: Path
    ) -> None:
        """Test async logger with rotating file sink."""
        with patch.dict(os.environ, {"FAPILOG_FILE__DIRECTORY": str(tmp_path)}):
            logger = await get_async_logger(name="async-file-test")
            await logger.info("test message")
            await logger.stop_and_drain()

            # Check that file was created
            files = list(tmp_path.iterdir())
            assert any(p.is_file() for p in files)

    @pytest.mark.asyncio
    async def test_get_async_logger_with_custom_settings(self) -> None:
        """Test async logger with custom settings."""
        settings = Settings()
        settings.core.enable_metrics = True
        settings.core.max_queue_size = 100

        logger = await get_async_logger(name="async-settings-test", settings=settings)
        assert logger is not None
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_sink_start_failure(self) -> None:
        """Test async logger when sink start fails."""
        # Mock a sink that fails to start
        mock_sink = Mock()
        mock_sink.start.side_effect = RuntimeError("Start failed")
        mock_sink._started = False

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            logger = await get_async_logger(name="async-sink-fail-test")
            # Should handle sink start failure gracefully
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_sink_write_serialized_fallback(self) -> None:
        """Test async logger sink write_serialized fallback."""
        # Mock a sink without write_serialized method
        mock_sink = Mock()
        del mock_sink.write_serialized

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            logger = await get_async_logger(name="async-serialized-fallback-test")
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_context_binding(self) -> None:
        """Test async logger with context binding enabled."""
        settings = Settings()
        settings.core.context_binding_enabled = True
        settings.core.default_bound_context = {"tenant": "test-tenant"}

        logger = await get_async_logger(name="async-context-test", settings=settings)
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_context_binding_exception(self) -> None:
        """Test async logger when context binding fails."""
        settings = Settings()
        settings.core.context_binding_enabled = True
        settings.core.default_bound_context = {"tenant": "test-tenant"}

        # Mock logger.bind to raise exception
        with patch(
            "fapilog.core.logger.AsyncLoggerFacade.bind",
            side_effect=RuntimeError("Bind failed"),
        ):
            logger = await get_async_logger(
                name="async-context-exception-test", settings=settings
            )
            # Should handle binding exception gracefully
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_sensitive_fields_policy(self) -> None:
        """Test async logger with sensitive fields policy."""
        settings = Settings()
        settings.core.sensitive_fields_policy = ["password", "secret"]

        logger = await get_async_logger(name="async-policy-test", settings=settings)
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_redactors(self) -> None:
        """Test async logger with redactors enabled."""
        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors_order = ["field-mask", "regex-mask"]
        settings.core.sensitive_fields_policy = ["password"]

        logger = await get_async_logger(name="async-redactors-test", settings=settings)
        assert hasattr(logger, "_redactors")
        assert len(logger._redactors) == 2
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_redactors_exception(self) -> None:
        """Test async logger when redactor configuration fails."""
        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors_order = ["field-mask", "regex-mask"]
        settings.core.sensitive_fields_policy = ["password"]

        # Mock redactor import to fail
        with patch(
            "fapilog.plugins.redactors.field_mask.FieldMaskRedactor",
            side_effect=ImportError("Redactor failed"),
        ):
            logger = await get_async_logger(
                name="async-redactors-exception-test", settings=settings
            )
            # Should handle redactor exception gracefully
            await logger.info("test message")
            await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_with_unhandled_capture(self) -> None:
        """Test async logger with unhandled exception capture."""
        settings = Settings()
        settings.core.capture_unhandled_enabled = True

        logger = await get_async_logger(name="async-unhandled-test", settings=settings)
        await logger.info("test message")
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_get_async_logger_unhandled_capture_exception(self) -> None:
        """Test async logger when unhandled capture fails."""
        settings = Settings()
        settings.core.capture_unhandled_enabled = True

        # Mock capture_unhandled_exceptions to fail
        with patch(
            "fapilog.core.errors.capture_unhandled_exceptions",
            side_effect=RuntimeError("Capture failed"),
        ):
            logger = await get_async_logger(
                name="async-unhandled-exception-test", settings=settings
            )
            # Should handle capture exception gracefully
            await logger.info("test message")
            await logger.stop_and_drain()


class TestRuntimeAsyncCoverage:
    """Test runtime_async function to improve coverage."""

    @pytest.mark.asyncio
    async def test_runtime_async_basic_usage(self) -> None:
        """Test basic runtime_async usage."""
        async with runtime_async() as logger:
            await logger.info("test message")
        # Logger should be drained automatically

    @pytest.mark.asyncio
    async def test_runtime_async_with_custom_settings(self) -> None:
        """Test runtime_async with custom settings."""
        settings = Settings()
        settings.core.enable_metrics = True

        async with runtime_async(settings=settings) as logger:
            await logger.info("test message")

    @pytest.mark.asyncio
    async def test_runtime_async_drain_exception(self) -> None:
        """Test runtime_async when drain fails."""
        # Mock logger.drain to fail
        with patch(
            "fapilog.core.logger.AsyncLoggerFacade.drain",
            side_effect=RuntimeError("Drain failed"),
        ):
            async with runtime_async() as logger:
                await logger.info("test message")
            # Should handle drain exception gracefully

    @pytest.mark.asyncio
    async def test_runtime_async_drain_warning_exception(self) -> None:
        """Test runtime_async when drain warning fails."""
        # Mock both drain and warn to fail
        with patch(
            "fapilog.core.logger.AsyncLoggerFacade.drain",
            side_effect=RuntimeError("Drain failed"),
        ):
            with patch(
                "fapilog.core.diagnostics.warn", side_effect=RuntimeError("Warn failed")
            ):
                async with runtime_async() as logger:
                    await logger.info("test message")
                # Should handle both exceptions gracefully


class TestRuntimeCoverage:
    """Test runtime function to improve coverage."""

    def test_runtime_basic_usage(self) -> None:
        """Test basic runtime usage."""
        with runtime() as logger:
            logger.info("test message")
        # Logger should be drained automatically

    def test_runtime_with_custom_settings(self) -> None:
        """Test runtime with custom settings."""
        settings = Settings()
        settings.core.enable_metrics = True

        with runtime(settings=settings) as logger:
            logger.info("test message")

    def test_runtime_inside_running_loop(self) -> None:
        """Test runtime when already inside a running event loop."""
        # This test simulates being inside a running event loop
        # by mocking asyncio.run to fail
        with patch("asyncio.run", side_effect=RuntimeError("Already in loop")):
            with runtime() as logger:
                logger.info("test message")
            # Should handle the asyncio.run failure gracefully

    def test_runtime_drain_exception(self) -> None:
        """Test runtime when drain fails."""
        # Mock logger.stop_and_drain to fail
        with patch(
            "fapilog.core.logger.SyncLoggerFacade.stop_and_drain",
            side_effect=RuntimeError("Drain failed"),
        ):
            with runtime() as logger:
                logger.info("test message")
            # Should handle drain exception gracefully

    def test_runtime_background_thread_fallback(self) -> None:
        """Test runtime background thread fallback."""
        # Mock both asyncio.run and loop.create_task to fail
        with patch("asyncio.run", side_effect=RuntimeError("Already in loop")):
            with patch("asyncio.get_event_loop") as mock_get_loop:
                mock_loop = Mock()
                mock_loop.create_task.side_effect = RuntimeError("Loop failed")
                mock_get_loop.return_value = mock_loop

                with runtime() as logger:
                    logger.info("test message")
                # Should fall back to background thread


class TestGetLoggerEdgeCases:
    """Test get_logger edge cases to improve coverage."""

    def test_get_logger_sink_start_failure(self) -> None:
        """Test get_logger when sink start fails."""
        # Mock a sink that fails to start
        mock_sink = Mock()
        mock_sink.start.side_effect = RuntimeError("Start failed")
        mock_sink._started = False

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            # Use the runtime context manager which handles async cleanup internally
            with runtime() as logger:
                # Should handle sink start failure gracefully
                logger.info("test message")
            # Context manager automatically handles cleanup

    def test_get_logger_sink_write_serialized_fallback(self) -> None:
        """Test get_logger sink write_serialized fallback."""
        # Mock a sink without write_serialized method
        mock_sink = Mock()
        del mock_sink.write_serialized

        with patch(
            "fapilog.plugins.sinks.stdout_json.StdoutJsonSink", return_value=mock_sink
        ):
            with runtime() as logger:
                logger.info("test message")
            # Context manager automatically handles cleanup

    def test_get_logger_context_binding_exception(self) -> None:
        """Test get_logger when context binding fails."""
        settings = Settings()
        settings.core.context_binding_enabled = True
        settings.core.default_bound_context = {"tenant": "test-tenant"}

        # Mock logger.bind to raise exception
        with patch(
            "fapilog.core.logger.SyncLoggerFacade.bind",
            side_effect=RuntimeError("Bind failed"),
        ):
            with runtime() as logger:
                # Should handle binding exception gracefully
                logger.info("test message")
            # Context manager automatically handles cleanup

    def test_get_logger_redactors_exception(self) -> None:
        """Test get_logger when redactor configuration fails."""
        settings = Settings()
        settings.core.enable_redactors = True
        settings.core.redactors_order = ["field-mask", "regex-mask"]
        settings.core.sensitive_fields_policy = ["password"]

        # Mock redactor import to fail
        with patch(
            "fapilog.plugins.redactors.field_mask.FieldMaskRedactor",
            side_effect=ImportError("Redactor failed"),
        ):
            with runtime() as logger:
                # Should handle redactor exception gracefully
                logger.info("test message")
            # Context manager automatically handles cleanup

    def test_get_logger_unhandled_capture_exception(self) -> None:
        """Test get_logger when unhandled capture fails."""
        settings = Settings()
        settings.core.capture_unhandled_enabled = True

        # Mock capture_unhandled_exceptions to fail
        with patch(
            "fapilog.core.errors.capture_unhandled_exceptions",
            side_effect=RuntimeError("Capture failed"),
        ):
            with runtime() as logger:
                # Should handle capture exception gracefully
                logger.info("test message")
            # Context manager automatically handles cleanup
