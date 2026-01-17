"""
Tests for logger sampling and error deduplication.

Scope:
- Sampling logic with different rates and levels
- Sampling effects on DEBUG/INFO levels
- Sampling exception handling
- Error deduplication within time window
- Error deduplication window rollover
- Error deduplication disabled mode
"""

import asyncio
import time
import warnings
from typing import Any
from unittest.mock import Mock, patch

import pytest

from fapilog.core.logger import SyncLoggerFacade


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

        # Patch Settings BEFORE logger creation (settings are cached at init)
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 0.001
            settings_instance.core.filters = []
            settings_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = settings_instance

            logger = _create_test_logger("sampling-test", out, backpressure_wait_ms=0)
            logger.start()

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
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

        # Patch Settings BEFORE logger creation (settings are cached at init)
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 0.5
            settings_instance.core.filters = []
            settings_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = settings_instance

            logger = _create_test_logger(
                "sampling-test", out, queue_capacity=32, backpressure_wait_ms=0
            )
            logger.start()

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
        """Test sampling with settings exceptions.

        When Settings() fails at init, defaults are used (no sampling).
        """
        out: list[dict[str, Any]] = []

        # Patch Settings BEFORE logger creation (settings are cached at init)
        # When Settings raises, defaults are used: no sampling, no dedupe
        with patch(
            "fapilog.core.settings.Settings", side_effect=Exception("Settings error")
        ):
            logger = _create_test_logger(
                "sampling-test", out, queue_capacity=8, backpressure_wait_ms=0
            )
            logger.start()

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

        # Patch Settings BEFORE logger creation (settings are cached at init)
        with patch("fapilog.core.settings.Settings") as mock_settings:
            settings_instance = Mock()
            settings_instance.observability.logging.sampling_rate = 1.0
            settings_instance.core.filters = []
            settings_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = settings_instance

            logger = _create_test_logger(
                "dedup-test", out, queue_capacity=16, backpressure_wait_ms=0
            )
            logger.start()

            for _ in range(5):
                logger.error("Repeated error")

            asyncio.run(logger.stop_and_drain())

        error_msgs = [e for e in out if e.get("level") == "ERROR"]
        assert len(error_msgs) == 5

    def test_error_deduplication_exception_handling(self) -> None:
        """Test error deduplication with settings exceptions.

        When Settings() fails at init, defaults are used (no deduplication).
        """
        out: list[dict[str, Any]] = []

        # Patch Settings BEFORE logger creation (settings are cached at init)
        # When Settings raises, defaults are used: no sampling, no dedupe
        with patch(
            "fapilog.core.settings.Settings", side_effect=Exception("Settings error")
        ):
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

            logger.error("Error with settings exception")
            logger.error("Error with settings exception")

            asyncio.run(logger.stop_and_drain())

        error_msgs = [e for e in out if e.get("level") == "ERROR"]
        assert len(error_msgs) == 2
