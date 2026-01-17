"""
Test settings caching in logger hot path (Story 1.23).

Scope:
- Verify Settings() is only called at initialization, not on every log
- Verify deprecation warning still works for sampling_rate < 1.0
- Verify error dedupe window uses cached value
"""

from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from fapilog.core.logger import SyncLoggerFacade


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


class TestSettingsCaching:
    """Tests for settings caching at init rather than per-call."""

    @pytest.mark.asyncio
    async def test_settings_not_called_on_every_log(self) -> None:
        """Verify Settings() is not instantiated on every log call.

        Settings should be cached at mixin initialization, not created
        repeatedly in _prepare_payload().
        """
        collected: list[dict[str, Any]] = []

        with patch("fapilog.core.settings.Settings") as mock_settings:
            # Configure mock to return sensible defaults
            mock_instance = MagicMock()
            mock_instance.observability.logging.sampling_rate = 1.0
            mock_instance.core.filters = []
            mock_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = mock_instance

            logger = SyncLoggerFacade(
                name="t",
                queue_capacity=1024,  # Large enough to avoid backpressure
                batch_max_size=64,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=10,
                drop_on_full=True,
                sink_write=lambda e: _collecting_sink(collected, e),
            )

            # Record call count after init
            init_call_count = mock_settings.call_count

            # Log multiple messages - fewer than queue capacity to avoid backpressure
            for _ in range(50):
                logger.info("test message")

            # Settings should not have been called again during logging
            assert mock_settings.call_count == init_call_count, (
                f"Settings() was called {mock_settings.call_count - init_call_count} "
                f"times during logging; expected 0 calls after init"
            )

            await logger.stop_and_drain()


class TestDeprecationWarning:
    """Tests for sampling_rate deprecation warning preservation."""

    @pytest.mark.asyncio
    async def test_sampling_rate_deprecation_warning_still_emitted(self) -> None:
        """Verify deprecation warning is emitted when sampling_rate < 1.0.

        Even with cached settings, the deprecation warning for
        observability.logging.sampling_rate should still be triggered.
        """
        collected: list[dict[str, Any]] = []

        with patch("fapilog.core.settings.Settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.observability.logging.sampling_rate = 0.5  # < 1.0
            mock_instance.core.filters = []  # No sampling filter configured
            mock_instance.core.error_dedupe_window_seconds = 0.0
            mock_settings.return_value = mock_instance

            logger = SyncLoggerFacade(
                name="t",
                queue_capacity=16,
                batch_max_size=8,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=10,
                drop_on_full=True,
                sink_write=lambda e: _collecting_sink(collected, e),
            )

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                # Log at INFO level (affected by sampling)
                logger.info("test")

                # Should emit deprecation warning
                deprecation_warnings = [
                    x for x in w if issubclass(x.category, DeprecationWarning)
                ]
                assert any(
                    "sampling_rate is deprecated" in str(x.message)
                    for x in deprecation_warnings
                ), f"Expected deprecation warning, got: {[str(x.message) for x in w]}"

            await logger.stop_and_drain()


class TestErrorDedupeWindowCaching:
    """Tests for error dedupe window caching."""

    @pytest.mark.asyncio
    async def test_error_dedupe_uses_cached_window(self) -> None:
        """Verify error deduplication uses cached window value.

        Settings() should not be called in the error dedupe path;
        the window value should be read from cached state.
        """
        collected: list[dict[str, Any]] = []

        with patch("fapilog.core.settings.Settings") as mock_settings:
            mock_instance = MagicMock()
            mock_instance.observability.logging.sampling_rate = 1.0
            mock_instance.core.filters = []
            mock_instance.core.error_dedupe_window_seconds = 5.0  # Non-zero window
            mock_settings.return_value = mock_instance

            logger = SyncLoggerFacade(
                name="t",
                queue_capacity=16,
                batch_max_size=8,
                batch_timeout_seconds=0.05,
                backpressure_wait_ms=10,
                drop_on_full=True,
                sink_write=lambda e: _collecting_sink(collected, e),
            )

            init_call_count = mock_settings.call_count

            # Log multiple ERROR messages (error dedupe path)
            for _ in range(10):
                logger.error("error message")

            # Settings should not have been called again
            assert mock_settings.call_count == init_call_count, (
                f"Settings() was called {mock_settings.call_count - init_call_count} "
                f"times during error logging; expected 0 calls after init"
            )

            await logger.stop_and_drain()
