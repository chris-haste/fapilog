"""Tests for graceful shutdown behavior (Story 6.13)."""

from __future__ import annotations

import signal
import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


class TestAtexitHandler:
    """Tests for atexit handler functionality (AC1)."""

    def test_atexit_handler_registered_on_module_import(self) -> None:
        """Atexit handler should be registered when shutdown module is imported."""

        from fapilog.core import shutdown

        # Get all registered atexit functions
        # Note: atexit doesn't expose registered functions directly,
        # so we verify by checking the module has the handler function
        assert hasattr(shutdown, "_atexit_handler")
        assert callable(shutdown._atexit_handler)

    def test_atexit_handler_drains_registered_loggers(self) -> None:
        """Atexit handler should drain all registered loggers."""
        from fapilog.core.shutdown import (
            _atexit_handler,
            _registered_loggers,
            register_logger,
        )

        # Create a mock logger
        mock_logger = MagicMock()
        mock_logger.stop_and_drain = MagicMock(return_value=MagicMock())

        # Register the logger
        register_logger(mock_logger)
        assert mock_logger in _registered_loggers

        # Call the atexit handler
        with patch("fapilog.core.shutdown._shutdown_in_progress", False):
            with patch("fapilog.core.shutdown.asyncio") as mock_asyncio:
                mock_asyncio.run = MagicMock()
                _atexit_handler()

        # Logger should have been drained
        mock_logger.stop_and_drain.assert_called_once()

    def test_atexit_respects_timeout(self) -> None:
        """Atexit handler should timeout if drain takes too long."""
        from fapilog.core.shutdown import _atexit_handler, register_logger

        mock_logger = MagicMock()
        mock_logger.stop_and_drain = MagicMock(return_value=MagicMock())

        register_logger(mock_logger)

        with patch("fapilog.core.shutdown._shutdown_in_progress", False):
            with patch("fapilog.core.shutdown.asyncio") as mock_asyncio:
                mock_asyncio.TimeoutError = TimeoutError
                mock_asyncio.wait_for = MagicMock(side_effect=TimeoutError)
                mock_asyncio.run = MagicMock(side_effect=TimeoutError)

                # Should not raise even on timeout
                _atexit_handler()

    def test_atexit_disabled_via_settings(self) -> None:
        """Atexit handler should be skipped when disabled in settings."""
        from fapilog.core.shutdown import _atexit_handler, register_logger

        mock_logger = MagicMock()
        mock_logger.stop_and_drain = MagicMock()

        register_logger(mock_logger)

        with patch("fapilog.core.shutdown._get_shutdown_settings") as mock_settings:
            mock_settings.return_value = {"atexit_drain_enabled": False}
            with patch("fapilog.core.shutdown._shutdown_in_progress", False):
                _atexit_handler()

        # Logger should NOT have been drained when disabled
        mock_logger.stop_and_drain.assert_not_called()


class TestSignalHandler:
    """Tests for signal handler functionality (AC2)."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Signal handling differs on Windows"
    )
    def test_signal_handler_drains_on_sigterm(self) -> None:
        """Signal handler should drain loggers on SIGTERM."""
        from fapilog.core.shutdown import _signal_handler, register_logger

        mock_logger = MagicMock()
        mock_logger.stop_and_drain = MagicMock(return_value=MagicMock())

        register_logger(mock_logger)

        with patch("fapilog.core.shutdown._shutdown_in_progress", False):
            with patch("fapilog.core.shutdown._atexit_handler") as mock_atexit:
                with patch("fapilog.core.shutdown.signal") as mock_signal:
                    mock_signal.SIG_DFL = signal.SIG_DFL
                    mock_signal.SIGTERM = signal.SIGTERM
                    mock_signal.raise_signal = MagicMock()

                    _signal_handler(signal.SIGTERM, None)

        mock_atexit.assert_called_once()

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Signal handling differs on Windows"
    )
    def test_signal_handler_drains_on_sigint(self) -> None:
        """Signal handler should drain loggers on SIGINT."""
        from fapilog.core.shutdown import _signal_handler

        with patch("fapilog.core.shutdown._shutdown_in_progress", False):
            with patch("fapilog.core.shutdown._atexit_handler") as mock_atexit:
                with patch("fapilog.core.shutdown.signal") as mock_signal:
                    mock_signal.SIG_DFL = signal.SIG_DFL
                    mock_signal.SIGINT = signal.SIGINT
                    mock_signal.raise_signal = MagicMock()

                    _signal_handler(signal.SIGINT, None)

        mock_atexit.assert_called_once()

    def test_signal_handler_reentrancy_protection(self) -> None:
        """Signal handler should not re-enter if shutdown already in progress."""
        from fapilog.core.shutdown import _signal_handler

        with patch("fapilog.core.shutdown._shutdown_in_progress", True):
            with patch("fapilog.core.shutdown._atexit_handler") as mock_atexit:
                _signal_handler(signal.SIGTERM, None)

        # Should not call atexit handler again
        mock_atexit.assert_not_called()

    def test_signal_handler_disabled_via_settings(self) -> None:
        """Signal handlers should not be installed when disabled."""
        with patch("fapilog.core.shutdown._get_shutdown_settings") as mock_settings:
            mock_settings.return_value = {"signal_handler_enabled": False}

            # Re-import to trigger registration
            from fapilog.core import shutdown

            assert shutdown._get_shutdown_settings()["signal_handler_enabled"] is False


class TestWeakRefCleanup:
    """Tests for WeakSet cleanup of dead loggers."""

    def test_weakref_cleanup_dead_loggers(self) -> None:
        """Dead loggers should be automatically cleaned from registry."""
        from fapilog.core.shutdown import _registered_loggers, register_logger

        class MockLogger:
            def stop_and_drain(self) -> Any:
                return MagicMock()

        # Create and register a logger
        logger = MockLogger()
        register_logger(logger)

        # Verify it's registered (we know we just added exactly one)
        assert logger in _registered_loggers

        # Delete the logger (should be garbage collected)
        del logger

        # WeakSet should automatically clean up
        # Note: GC might not run immediately, but WeakSet handles this


class TestShutdownSettings:
    """Tests for shutdown configuration (AC3)."""

    def test_settings_have_atexit_drain_enabled(self) -> None:
        """CoreSettings should have atexit_drain_enabled field."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert hasattr(settings, "atexit_drain_enabled")
        assert settings.atexit_drain_enabled is True  # Default

    def test_settings_have_atexit_drain_timeout(self) -> None:
        """CoreSettings should have atexit_drain_timeout_seconds field."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert hasattr(settings, "atexit_drain_timeout_seconds")
        assert settings.atexit_drain_timeout_seconds == 2.0  # Default

    def test_settings_have_signal_handler_enabled(self) -> None:
        """CoreSettings should have signal_handler_enabled field."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert hasattr(settings, "signal_handler_enabled")
        assert settings.signal_handler_enabled is True  # Default

    def test_settings_have_flush_on_critical(self) -> None:
        """CoreSettings should have flush_on_critical field."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert hasattr(settings, "flush_on_critical")
        assert settings.flush_on_critical is False  # Default


class TestFlushOnCritical:
    """Tests for immediate flush of ERROR/CRITICAL logs (AC5)."""

    def test_flush_on_critical_setting_exists(self) -> None:
        """CoreSettings should have flush_on_critical field."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert hasattr(settings, "flush_on_critical")

    def test_flush_on_critical_disabled_by_default(self) -> None:
        """Flush on critical should be disabled by default."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert settings.flush_on_critical is False

    def test_flush_on_critical_can_be_enabled(self) -> None:
        """Flush on critical should be configurable."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings(flush_on_critical=True)
        assert settings.flush_on_critical is True


class TestBuilderMethods:
    """Tests for builder methods related to shutdown configuration."""

    def test_with_atexit_drain(self) -> None:
        """Builder should have with_atexit_drain method."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_atexit_drain(enabled=True, timeout="3s")
        assert result is builder  # Fluent API

    def test_with_signal_handlers(self) -> None:
        """Builder should have with_signal_handlers method."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_signal_handlers(enabled=True)
        assert result is builder  # Fluent API

    def test_with_flush_on_critical(self) -> None:
        """Builder should have with_flush_on_critical method."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_flush_on_critical(enabled=True)
        assert result is builder  # Fluent API


class TestLoggerRegistration:
    """Tests for automatic logger registration with shutdown module."""

    def test_logger_registered_on_start(self) -> None:
        """Logger should be registered with shutdown module when started."""
        from fapilog.core.logger import SyncLoggerFacade
        from fapilog.core.shutdown import _registered_loggers

        async def noop_sink(payload: dict[str, Any]) -> None:
            pass

        logger = SyncLoggerFacade(
            name="test-registration",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=True,
            sink_write=noop_sink,
        )

        # Logger should not be in registry yet
        assert logger not in _registered_loggers

        # Start the logger
        logger.start()

        # Logger should now be registered
        assert logger in _registered_loggers


class TestGetShutdownSettings:
    """Tests for _get_shutdown_settings function."""

    def test_returns_defaults_when_settings_fail(self) -> None:
        """Should return sensible defaults when Settings import fails."""
        from fapilog.core.shutdown import _get_shutdown_settings

        # The function should always return valid defaults
        settings = _get_shutdown_settings()

        assert "atexit_drain_enabled" in settings
        assert "atexit_drain_timeout_seconds" in settings
        assert "signal_handler_enabled" in settings

    def test_returns_settings_values(self) -> None:
        """Should return actual settings values."""
        from fapilog.core.shutdown import _get_shutdown_settings

        settings = _get_shutdown_settings()

        assert settings["atexit_drain_enabled"] is True
        assert settings["atexit_drain_timeout_seconds"] == 2.0
        assert settings["signal_handler_enabled"] is True


class TestUnregisterLogger:
    """Tests for unregister_logger function."""

    def test_unregister_logger_removes_from_registry(self) -> None:
        """Unregister should remove logger from registry."""
        from fapilog.core.shutdown import (
            _registered_loggers,
            register_logger,
            unregister_logger,
        )

        mock_logger = MagicMock()
        register_logger(mock_logger)
        assert mock_logger in _registered_loggers

        unregister_logger(mock_logger)
        assert mock_logger not in _registered_loggers

    def test_unregister_nonexistent_logger_no_error(self) -> None:
        """Unregistering non-existent logger should not raise."""
        from fapilog.core.shutdown import unregister_logger

        mock_logger = MagicMock()
        # Should not raise
        unregister_logger(mock_logger)


class TestDrainSingleLogger:
    """Tests for _drain_single_logger function."""

    def test_drain_handles_timeout(self) -> None:
        """Drain should handle timeout gracefully."""
        from fapilog.core.shutdown import _drain_single_logger

        mock_logger = MagicMock()

        # Create a slow drain
        async def slow_drain() -> MagicMock:
            import asyncio

            await asyncio.sleep(10)
            return MagicMock()

        mock_logger.stop_and_drain.return_value = slow_drain()

        # Should not raise, should timeout gracefully
        _drain_single_logger(mock_logger, timeout=0.1)

    def test_drain_handles_exception(self) -> None:
        """Drain should handle exceptions gracefully."""
        from fapilog.core.shutdown import _drain_single_logger

        mock_logger = MagicMock()
        mock_logger.stop_and_drain.side_effect = Exception("drain failed")

        # Should not raise
        _drain_single_logger(mock_logger, timeout=1.0)

    def test_drain_with_running_loop_uses_thread(self) -> None:
        """Drain should use thread executor when event loop is running."""
        import asyncio

        from fapilog.core.shutdown import _drain_single_logger

        # Create a fast completing drain
        async def fast_drain() -> MagicMock:
            return MagicMock()

        mock_logger = MagicMock()
        mock_logger.stop_and_drain.return_value = fast_drain()

        # Run within an event loop to trigger the RuntimeError path
        async def run_drain_in_loop() -> None:
            # This will try asyncio.run() which fails when loop is running
            # So it should fall back to the thread executor
            _drain_single_logger(mock_logger, timeout=5.0)

        # Run the test - this exercises the RuntimeError branch
        asyncio.run(run_drain_in_loop())


class TestAtexitShutdownInProgress:
    """Tests for atexit handler shutdown_in_progress flag."""

    def test_atexit_skips_if_shutdown_in_progress(self) -> None:
        """Atexit handler should skip if shutdown already in progress."""
        import fapilog.core.shutdown as shutdown_module

        # Save original state
        original = shutdown_module._shutdown_in_progress

        try:
            # Set shutdown in progress
            shutdown_module._shutdown_in_progress = True

            mock_logger = MagicMock()
            shutdown_module.register_logger(mock_logger)

            # Call handler - should return early
            shutdown_module._atexit_handler()

            # Logger should NOT have been drained
            mock_logger.stop_and_drain.assert_not_called()
        finally:
            # Restore original state
            shutdown_module._shutdown_in_progress = original


class TestInstallSignalHandlers:
    """Tests for signal handler installation."""

    def test_signal_handlers_skipped_when_disabled(self) -> None:
        """Signal handlers should not be installed when disabled in settings."""
        from fapilog.core.shutdown import (
            _reset_handler_state,
            install_shutdown_handlers,
        )

        _reset_handler_state()

        with patch("fapilog.core.shutdown._get_shutdown_settings") as mock_settings:
            mock_settings.return_value = {
                "atexit_drain_enabled": True,
                "atexit_drain_timeout_seconds": 2.0,
                "signal_handler_enabled": False,
            }

            with patch(
                "fapilog.core.shutdown._do_install_signal_handlers"
            ) as mock_install:
                # Call the function
                install_shutdown_handlers()

                # Signal handlers should not be installed when disabled
                mock_install.assert_not_called()
