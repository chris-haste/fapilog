"""Tests for logger startup validation behavior.

Story 1.29: Backpressure Configuration Startup Validation

These tests verify that SyncLoggerFacade emits a one-time warning when
drop_on_full=False is configured, alerting users that same-thread calls
will still drop immediately to prevent deadlock.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from fapilog.core.diagnostics import configure_diagnostics, set_writer_for_tests
from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade


@pytest.fixture
def captured_diagnostics() -> list[dict[str, Any]]:
    """Capture diagnostic emissions for assertion."""
    captured: list[dict[str, Any]] = []

    def capture(payload: dict[str, Any]) -> None:
        captured.append(payload)

    configure_diagnostics(enabled=True)
    set_writer_for_tests(capture)
    return captured


@pytest.fixture
def mock_sink() -> AsyncMock:
    """Create a mock sink for logger tests."""
    return AsyncMock()


class TestSyncFacadeStartupWarning:
    """AC1, AC2, AC3, AC4: SyncLoggerFacade startup warning behavior."""

    def test_sync_facade_warns_on_drop_on_full_false(
        self,
        captured_diagnostics: list[dict[str, Any]],
        mock_sink: AsyncMock,
    ) -> None:
        """AC1: Emit warning when SyncLoggerFacade starts with drop_on_full=False."""
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=False,
            sink_write=mock_sink,
        )
        logger.start()

        # Filter for backpressure startup warnings
        startup_warnings = [
            d
            for d in captured_diagnostics
            if d.get("component") == "backpressure"
            and "drop_on_full=False configured" in d.get("message", "")
        ]
        assert len(startup_warnings) == 1
        warning = startup_warnings[0]
        assert warning["level"] == "WARN"
        assert "same-thread" in warning["message"]

    def test_sync_facade_no_warn_on_drop_on_full_true(
        self,
        captured_diagnostics: list[dict[str, Any]],
        mock_sink: AsyncMock,
    ) -> None:
        """AC3: No warning when drop_on_full=True (default behavior)."""
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=True,
            sink_write=mock_sink,
        )
        logger.start()

        # Should not have any startup configuration warnings
        startup_warnings = [
            d
            for d in captured_diagnostics
            if d.get("component") == "backpressure"
            and "drop_on_full=False configured" in d.get("message", "")
        ]
        assert len(startup_warnings) == 0

    def test_startup_warning_emitted_once_per_logger(
        self,
        captured_diagnostics: list[dict[str, Any]],
        mock_sink: AsyncMock,
    ) -> None:
        """AC2: Warning is emitted only once on start(), not on subsequent calls."""
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=False,
            sink_write=mock_sink,
        )

        # Call start multiple times
        logger.start()
        logger.start()
        logger.start()

        # Should only have one startup warning
        startup_warnings = [
            d
            for d in captured_diagnostics
            if d.get("component") == "backpressure"
            and "drop_on_full=False configured" in d.get("message", "")
        ]
        assert len(startup_warnings) == 1

    def test_startup_warning_includes_recommendation(
        self,
        captured_diagnostics: list[dict[str, Any]],
        mock_sink: AsyncMock,
    ) -> None:
        """AC4: Warning includes AsyncLoggerFacade recommendation."""
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=False,
            sink_write=mock_sink,
        )
        logger.start()

        startup_warnings = [
            d
            for d in captured_diagnostics
            if d.get("component") == "backpressure"
            and "drop_on_full=False configured" in d.get("message", "")
        ]
        assert len(startup_warnings) == 1
        warning = startup_warnings[0]
        assert "AsyncLoggerFacade" in warning["message"]
        assert "async context" in warning["message"].lower()


class TestStartupWarningExceptionHandling:
    """Test that startup warning handles diagnostics failures gracefully."""

    def test_startup_warning_handles_diagnostics_exception(
        self,
        mock_sink: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Startup warning exception is silently caught to prevent startup failure."""
        import fapilog.core.diagnostics

        # Make diagnostics.warn raise an exception
        def raise_exception(*args: object, **kwargs: object) -> None:
            raise RuntimeError("Diagnostics failure")

        monkeypatch.setattr(fapilog.core.diagnostics, "warn", raise_exception)

        # Create logger with drop_on_full=False
        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=False,
            sink_write=mock_sink,
        )

        # start() should not raise even if diagnostics.warn fails
        logger.start()
        # Verify the logger is actually started by checking worker loop is running
        assert logger._worker_loop is not None and logger._worker_loop.is_running()


class TestAsyncFacadeNoStartupWarning:
    """AC5: AsyncLoggerFacade should not emit startup warning."""

    @pytest.mark.asyncio
    async def test_async_facade_no_startup_warning(
        self,
        captured_diagnostics: list[dict[str, Any]],
        mock_sink: AsyncMock,
    ) -> None:
        """AC5: AsyncLoggerFacade does not emit warning (same-thread issue doesn't apply)."""
        logger = AsyncLoggerFacade(
            name="test",
            queue_capacity=100,
            batch_max_size=10,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=50,
            drop_on_full=False,
            sink_write=mock_sink,
        )
        await logger.start_async()

        # Should not have any startup configuration warnings
        startup_warnings = [
            d
            for d in captured_diagnostics
            if d.get("component") == "backpressure"
            and "drop_on_full=False configured" in d.get("message", "")
        ]
        assert len(startup_warnings) == 0
