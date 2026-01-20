"""Tests for Settings() hot path elimination (Story 1.25).

Verifies that Settings() is not instantiated on every diagnostic emit,
worker process, or sink write call.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


class TestDiagnosticsCaching:
    """AC1: No Settings() in Diagnostic Emit Path."""

    def test_is_enabled_caches_settings_value(self) -> None:
        """_is_enabled() should cache the value from Settings() on first call."""
        import fapilog.core.diagnostics as diag

        # Reset any cached state
        diag._internal_logging_enabled = None

        with patch("fapilog.core.settings.Settings") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.core.internal_logging_enabled = True
            mock_cls.return_value = mock_settings

            # First call should read from Settings
            result1 = diag._is_enabled()
            assert result1 is True
            assert mock_cls.call_count == 1

            # Second call should use cached value, not call Settings again
            result2 = diag._is_enabled()
            assert result2 is True
            assert mock_cls.call_count == 1  # Still just 1 call

    def test_is_enabled_caches_false_value(self) -> None:
        """_is_enabled() should also cache False values properly."""
        import fapilog.core.diagnostics as diag

        diag._internal_logging_enabled = None

        with patch("fapilog.core.settings.Settings") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.core.internal_logging_enabled = False
            mock_cls.return_value = mock_settings

            result1 = diag._is_enabled()
            assert result1 is False
            assert mock_cls.call_count == 1

            # Should still be cached
            result2 = diag._is_enabled()
            assert result2 is False
            assert mock_cls.call_count == 1

    def test_configure_diagnostics_overrides_cached_value(self) -> None:
        """configure_diagnostics() should override the cached value."""
        import fapilog.core.diagnostics as diag

        # Set initial cached value
        diag._internal_logging_enabled = False

        # Override with explicit configuration
        diag.configure_diagnostics(enabled=True)

        assert diag._internal_logging_enabled is True
        assert diag._is_enabled() is True

        # Override back to False
        diag.configure_diagnostics(enabled=False)
        assert diag._is_enabled() is False

    def test_emit_does_not_call_settings_when_cached(self) -> None:
        """emit() should not instantiate Settings() when value is cached."""
        import fapilog.core.diagnostics as diag

        # Pre-configure the cache
        diag.configure_diagnostics(enabled=True)
        diag._reset_for_tests()

        captured: list[dict[str, Any]] = []
        diag.set_writer_for_tests(lambda p: captured.append(p))

        with patch("fapilog.core.settings.Settings") as mock_cls:
            # Emit multiple messages - Settings should never be called
            for i in range(10):
                diag.emit(
                    component="test",
                    level="DEBUG",
                    message=f"message {i}",
                )

            # Settings should NOT have been called since we pre-configured
            assert mock_cls.call_count == 0

        # Messages should have been emitted (up to rate limit)
        assert len(captured) > 0

    def test_warn_does_not_call_settings_when_cached(self) -> None:
        """warn() should not instantiate Settings() when value is cached."""
        import fapilog.core.diagnostics as diag

        diag.configure_diagnostics(enabled=True)
        diag._reset_for_tests()

        captured: list[dict[str, Any]] = []
        diag.set_writer_for_tests(lambda p: captured.append(p))

        with patch("fapilog.core.settings.Settings") as mock_cls:
            diag.warn("test", "test message")
            assert mock_cls.call_count == 0

        assert len(captured) == 1
        assert captured[0]["level"] == "WARN"

    def test_is_enabled_handles_settings_exception(self) -> None:
        """_is_enabled() should return False and cache if Settings() raises."""
        import fapilog.core.diagnostics as diag

        diag._internal_logging_enabled = None

        with patch("fapilog.core.settings.Settings") as mock_cls:
            mock_cls.side_effect = RuntimeError("Settings not available")

            result = diag._is_enabled()
            assert result is False
            # Should be cached as False
            assert diag._internal_logging_enabled is False

            # Subsequent calls should not try Settings again
            result2 = diag._is_enabled()
            assert result2 is False
            # Only one call attempted
            assert mock_cls.call_count == 1


class TestWorkerStrictEnvelopeMode:
    """AC2: No Settings() in Worker/Sink Write Paths."""

    def test_worker_uses_provider_not_settings(self) -> None:
        """LoggerWorker should use strict_envelope_mode_provider, not Settings()."""
        from fapilog.core.concurrency import NonBlockingRingQueue
        from fapilog.core.worker import LoggerWorker

        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(capacity=10)
        written: list[dict[str, Any]] = []

        async def sink_write(entry: dict[str, Any]) -> None:
            written.append(entry)

        # Provider returns True without calling Settings
        strict_mode_value = True
        provider_call_count = 0

        def strict_provider() -> bool:
            nonlocal provider_call_count
            provider_call_count += 1
            return strict_mode_value

        worker = LoggerWorker(
            queue=queue,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            sink_write=sink_write,
            sink_write_serialized=None,
            enrichers_getter=lambda: [],
            redactors_getter=lambda: [],
            metrics=None,
            serialize_in_flush=False,
            strict_envelope_mode_provider=strict_provider,
            stop_flag=lambda: False,
            drained_event=None,
            flush_event=None,
            flush_done_event=None,
            emit_enricher_diagnostics=False,
            emit_redactor_diagnostics=False,
            counters={"processed": 0, "dropped": 0},
        )

        # Just verify the worker was created with the provider
        assert worker._strict_envelope_mode_provider is strict_provider

    def test_logger_caches_strict_envelope_mode(self) -> None:
        """Logger should cache strict_envelope_mode at init time."""
        from fapilog.core.logger import SyncLoggerFacade

        async def sink_write(entry: dict[str, Any]) -> None:
            pass

        with patch("fapilog.core.settings.Settings") as mock_cls:
            mock_settings = MagicMock()
            mock_settings.core.strict_envelope_mode = True
            mock_settings.observability.logging.sampling_rate = 1.0
            mock_settings.core.filters = []
            mock_settings.core.error_dedupe_window_seconds = 0.0
            mock_cls.return_value = mock_settings

            logger = SyncLoggerFacade(
                name="test",
                queue_capacity=100,
                batch_max_size=10,
                batch_timeout_seconds=0.1,
                backpressure_wait_ms=100,
                drop_on_full=True,
                sink_write=sink_write,
            )

            # Settings should have been called once during init
            init_call_count = mock_cls.call_count

            # Access the cached value (should not call Settings again)
            cached_value = logger._cached_strict_envelope_mode
            assert cached_value is True
            assert mock_cls.call_count == init_call_count  # No additional calls


class TestLifecycleTimeoutInjection:
    """AC3: Configuration Passed at Creation Time - lifecycle timeout."""

    def test_install_signal_handlers_uses_passed_timeout(self) -> None:
        """install_signal_handlers should use passed timeout, not Settings()."""
        mock_logger = MagicMock()

        with patch("fapilog.core.settings.Settings") as mock_cls:
            # Import inside patch context to ensure any import-triggered
            # Settings() calls are captured (fixes Python 3.12 CI flakiness)
            from fapilog.core.lifecycle import install_signal_handlers

            # Record call count after import but before our target call
            calls_from_import = mock_cls.call_count

            # Pass explicit timeout - should not need Settings
            install_signal_handlers(mock_logger, timeout_seconds=5.0)

            # Settings should not be called for the timeout since one was provided
            # We only check that no NEW calls were made during install_signal_handlers
            assert mock_cls.call_count == calls_from_import


class TestSinkConfigInjection:
    """AC2/AC3: Sinks receive strict_envelope_mode via config, not Settings()."""

    def test_rotating_file_sink_config_has_strict_envelope_mode(self) -> None:
        """RotatingFileSinkConfig should have strict_envelope_mode field."""
        from pathlib import Path

        from fapilog.plugins.sinks.rotating_file import RotatingFileSinkConfig

        config = RotatingFileSinkConfig(
            directory=Path("/tmp"),
            strict_envelope_mode=True,
        )

        assert config.strict_envelope_mode is True

        # Default should be False
        config_default = RotatingFileSinkConfig(directory=Path("/tmp"))
        assert config_default.strict_envelope_mode is False

    async def test_rotating_file_sink_uses_config_not_settings(
        self, tmp_path: Any
    ) -> None:
        """RotatingFileSink.write() should use config.strict_envelope_mode."""
        import fapilog.core.diagnostics as diag
        from fapilog.plugins.sinks.rotating_file import (
            RotatingFileSink,
            RotatingFileSinkConfig,
        )

        # Pre-configure diagnostics to avoid Settings() call in warn()
        diag.configure_diagnostics(enabled=True)
        diag._reset_for_tests()

        config = RotatingFileSinkConfig(
            directory=tmp_path,
            strict_envelope_mode=True,
        )
        sink = RotatingFileSink(config)
        await sink.start()

        # Mock the serialization to force fallback path
        with patch(
            "fapilog.plugins.sinks.rotating_file.serialize_envelope"
        ) as mock_ser:
            with patch("fapilog.core.settings.Settings") as mock_settings_cls:
                # Make serialization fail to trigger strict mode check
                mock_ser.side_effect = ValueError("serialization error")

                # Write should use config.strict_envelope_mode, not Settings()
                await sink.write({"level": "INFO", "message": "test"})

                # Settings should NOT have been called
                assert mock_settings_cls.call_count == 0

        await sink.stop()

    def test_stdout_json_sink_accepts_strict_envelope_mode(self) -> None:
        """StdoutJsonSink should accept strict_envelope_mode in constructor."""
        from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

        sink = StdoutJsonSink(strict_envelope_mode=True)
        assert sink._strict_envelope_mode is True

        # Default should be False
        sink_default = StdoutJsonSink()
        assert sink_default._strict_envelope_mode is False

    async def test_stdout_json_sink_uses_config_not_settings(self) -> None:
        """StdoutJsonSink.write() should use instance strict_envelope_mode."""
        import fapilog.core.diagnostics as diag
        from fapilog.plugins.sinks.stdout_json import StdoutJsonSink

        # Pre-configure diagnostics to avoid Settings() call in warn()
        diag.configure_diagnostics(enabled=True)
        diag._reset_for_tests()

        sink = StdoutJsonSink(strict_envelope_mode=True)

        with patch("fapilog.plugins.sinks.stdout_json.serialize_envelope") as mock_ser:
            with patch("fapilog.core.settings.Settings") as mock_settings_cls:
                # Make serialization fail to trigger strict mode check
                mock_ser.side_effect = ValueError("serialization error")

                # Write should use _strict_envelope_mode, not Settings()
                await sink.write({"level": "INFO", "message": "test"})

                # Settings should NOT have been called
                assert mock_settings_cls.call_count == 0
