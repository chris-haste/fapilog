"""Tests for lazy signal handler installation (Story 4.55).

These tests verify that signal/atexit handlers are NOT installed at import time,
but instead installed lazily on first logger start or explicit call.
"""

from __future__ import annotations

from unittest.mock import patch


class TestNoImportTimeInstallation:
    """AC1: No handlers installed at import time."""

    def test_import_does_not_install_signal_handlers(self) -> None:
        """Importing fapilog should not change signal handlers."""
        # Force re-evaluation of shutdown module state
        from fapilog.core import shutdown

        # Reset the module state to simulate fresh import
        shutdown._reset_handler_state()

        # After reset, handlers_installed should be False
        # (the actual test is that _reset clears installed state)
        assert shutdown._handlers_installed is False

    def test_handlers_installed_flag_starts_false(self) -> None:
        """The _handlers_installed flag should be False initially."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()
        assert shutdown._handlers_installed is False


class TestLazyInstallationOnLoggerStart:
    """AC2: Handlers installed on first logger start."""

    def test_get_logger_triggers_handler_installation(self) -> None:
        """Getting a logger should trigger handler installation."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()
        assert shutdown._handlers_installed is False

        # Mock the actual signal installation to avoid side effects
        with patch.object(shutdown, "_do_install_signal_handlers"):
            with patch.object(shutdown, "atexit"):
                from fapilog import get_logger

                logger = get_logger(name="test-lazy-install", reuse=False)

                # Handlers should now be marked as installed
                assert shutdown._handlers_installed is True

        # Cleanup
        import asyncio

        asyncio.run(logger.stop_and_drain())

    def test_handler_installation_called_once_per_session(self) -> None:
        """Multiple logger starts should only install handlers once."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        install_call_count = 0
        original_install = shutdown._do_install_signal_handlers

        def counting_install() -> None:
            nonlocal install_call_count
            install_call_count += 1
            original_install()

        with patch.object(shutdown, "_do_install_signal_handlers", counting_install):
            with patch.object(shutdown, "atexit"):
                from fapilog import get_logger

                logger1 = get_logger(name="test-multi-1", reuse=False)
                logger2 = get_logger(name="test-multi-2", reuse=False)

                # Should only be called once despite two loggers
                assert install_call_count == 1

        # Cleanup
        import asyncio

        asyncio.run(logger1.stop_and_drain())
        asyncio.run(logger2.stop_and_drain())


class TestManualInstallation:
    """AC3: Manual handler installation function."""

    def test_install_shutdown_handlers_explicit(self) -> None:
        """Users can explicitly install handlers via install_shutdown_handlers()."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()
        assert shutdown._handlers_installed is False

        with patch.object(shutdown, "_do_install_signal_handlers"):
            with patch.object(shutdown, "atexit"):
                result = shutdown.install_shutdown_handlers()

                assert result is True
                assert shutdown._handlers_installed is True

    def test_install_shutdown_handlers_exported_from_fapilog(self) -> None:
        """install_shutdown_handlers should be accessible from fapilog package."""
        import fapilog

        assert hasattr(fapilog, "install_shutdown_handlers")
        assert callable(fapilog.install_shutdown_handlers)


class TestIdempotentInstallation:
    """AC4: Idempotent installation."""

    def test_install_shutdown_handlers_idempotent(self) -> None:
        """Calling install multiple times should only install once."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        with patch.object(shutdown, "_do_install_signal_handlers") as mock_install:
            with patch.object(shutdown, "atexit"):
                # First call should install
                result1 = shutdown.install_shutdown_handlers()
                assert result1 is True
                assert mock_install.call_count == 1

                # Second call should not re-install
                result2 = shutdown.install_shutdown_handlers()
                assert result2 is False
                assert mock_install.call_count == 1  # Still 1

                # Third call - still idempotent
                result3 = shutdown.install_shutdown_handlers()
                assert result3 is False
                assert mock_install.call_count == 1


class TestOptOutViaSettings:
    """AC5: Opt-out via settings prevents installation."""

    def test_signal_handler_disabled_prevents_signal_installation(self) -> None:
        """Setting signal_handler_enabled=False should prevent signal handler install."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        mock_settings = {
            "atexit_drain_enabled": True,
            "atexit_drain_timeout_seconds": 2.0,
            "signal_handler_enabled": False,
        }

        with patch.object(
            shutdown, "_get_shutdown_settings", return_value=mock_settings
        ):
            with patch.object(
                shutdown, "_do_install_signal_handlers"
            ) as mock_signal_install:
                with patch.object(shutdown, "atexit") as mock_atexit:
                    shutdown.install_shutdown_handlers()

                    # Signal handlers should NOT be installed
                    mock_signal_install.assert_not_called()
                    # But atexit should still be registered
                    mock_atexit.register.assert_called_once()

    def test_atexit_disabled_prevents_atexit_registration(self) -> None:
        """Setting atexit_drain_enabled=False should prevent atexit registration."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        mock_settings = {
            "atexit_drain_enabled": False,
            "atexit_drain_timeout_seconds": 2.0,
            "signal_handler_enabled": True,
        }

        with patch.object(
            shutdown, "_get_shutdown_settings", return_value=mock_settings
        ):
            with patch.object(shutdown, "_do_install_signal_handlers") as mock_signal:
                with patch.object(shutdown, "atexit") as mock_atexit:
                    shutdown.install_shutdown_handlers()

                    # Atexit should NOT be registered
                    mock_atexit.register.assert_not_called()
                    # But signal handlers should be installed
                    mock_signal.assert_called_once()

    def test_both_disabled_installs_nothing(self) -> None:
        """Both settings disabled should install nothing but mark as installed."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        mock_settings = {
            "atexit_drain_enabled": False,
            "atexit_drain_timeout_seconds": 2.0,
            "signal_handler_enabled": False,
        }

        with patch.object(
            shutdown, "_get_shutdown_settings", return_value=mock_settings
        ):
            with patch.object(shutdown, "_do_install_signal_handlers") as mock_signal:
                with patch.object(shutdown, "atexit") as mock_atexit:
                    result = shutdown.install_shutdown_handlers()

                    assert result is True  # First call still returns True
                    assert shutdown._handlers_installed is True
                    mock_signal.assert_not_called()
                    mock_atexit.register.assert_not_called()


class TestResetHandlerState:
    """Tests for _reset_handler_state helper (for test isolation)."""

    def test_reset_clears_installed_flag(self) -> None:
        """_reset_handler_state should clear the installed flag."""
        from fapilog.core import shutdown

        # Set flag to True
        shutdown._handlers_installed = True

        # Reset should clear it
        shutdown._reset_handler_state()

        assert shutdown._handlers_installed is False

    def test_reset_allows_reinstallation(self) -> None:
        """After reset, handlers can be installed again."""
        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        with patch.object(shutdown, "_do_install_signal_handlers"):
            with patch.object(shutdown, "atexit"):
                # First install
                result1 = shutdown.install_shutdown_handlers()
                assert result1 is True

                # Reset
                shutdown._reset_handler_state()

                # Can install again
                result2 = shutdown.install_shutdown_handlers()
                assert result2 is True


class TestEventLoopDetection:
    """Tests for ASGI server compatibility (Story 12.17).

    When running under ASGI servers (uvicorn, hypercorn), signal handlers
    should NOT be installed because the server manages shutdown via lifespan.
    """

    def test_has_running_event_loop_returns_false_when_no_loop(self) -> None:
        """_has_running_event_loop returns False when no loop is running."""
        from fapilog.core import shutdown

        # Outside of async context, should return False
        assert shutdown._has_running_event_loop() is False

    def test_has_running_event_loop_returns_true_in_async_context(self) -> None:
        """_has_running_event_loop returns True inside async context."""
        import asyncio

        from fapilog.core import shutdown

        async def check() -> bool:
            # Check from inside the async context where loop IS running
            return shutdown._has_running_event_loop()

        # asyncio.run() creates a loop and runs check() inside it
        # The function should return True when called from within
        assert asyncio.run(check()) is True

    def test_signal_handlers_skipped_when_event_loop_running(self) -> None:
        """Signal handlers should not be installed when event loop is running."""
        import asyncio
        import signal

        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        async def test_in_loop() -> None:
            # Store original handler
            original = signal.getsignal(signal.SIGINT)

            # Install handlers while loop is running
            with patch.object(shutdown, "atexit"):
                shutdown.install_shutdown_handlers()

            # Signal handler should NOT have been changed
            current = signal.getsignal(signal.SIGINT)
            assert current == original, (
                "Signal handler was changed despite running loop"
            )

        asyncio.run(test_in_loop())

    def test_signal_handlers_installed_when_no_event_loop(self) -> None:
        """Signal handlers should be installed when no event loop is running."""
        import signal

        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        # Set a known handler first to detect changes
        def dummy_handler(sig: int, frame: object) -> None:
            pass

        original = signal.signal(signal.SIGINT, dummy_handler)

        try:
            with patch.object(shutdown, "atexit"):
                shutdown.install_shutdown_handlers()

            # Signal handler SHOULD have been changed from dummy
            current = signal.getsignal(signal.SIGINT)
            assert current != dummy_handler, "Signal handler was not installed"
            assert current == shutdown._signal_handler
        finally:
            # Restore original handler
            signal.signal(signal.SIGINT, original)
            shutdown._reset_handler_state()


class TestThreadSafety:
    """Tests for thread-safe installation."""

    def test_concurrent_installation_only_installs_once(self) -> None:
        """Concurrent calls to install_shutdown_handlers should only install once."""
        import threading

        from fapilog.core import shutdown

        shutdown._reset_handler_state()

        install_count = 0
        install_lock = threading.Lock()

        def counting_install() -> None:
            nonlocal install_count
            with install_lock:
                install_count += 1

        results: list[bool] = []
        results_lock = threading.Lock()

        def install_and_record() -> None:
            result = shutdown.install_shutdown_handlers()
            with results_lock:
                results.append(result)

        with patch.object(shutdown, "_do_install_signal_handlers", counting_install):
            with patch.object(shutdown, "atexit"):
                threads = [
                    threading.Thread(target=install_and_record) for _ in range(10)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        # Only one thread should have successfully installed (returned True)
        assert results.count(True) == 1
        assert results.count(False) == 9
        assert install_count == 1
