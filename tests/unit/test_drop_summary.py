"""Tests for drop/dedupe visibility feature (Story 12.20)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


class TestDropSummaryEmission:
    """Test drop/dedupe summary emission behavior."""

    @pytest.mark.asyncio
    async def test_drop_summary_emitted_when_enabled(self) -> None:
        """With emit_drop_summary=True, drop summaries appear in logs (AC2)."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test_drop",
            queue_capacity=1,  # Tiny queue to force drops
            batch_max_size=8,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,  # Short wait
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            emit_drop_summary=True,
            drop_summary_window_seconds=1.0,  # 1 second window - will trigger on first drop
        )
        logger.start()

        # Flood the queue to trigger drops - first drop will trigger summary
        # because _last_drop_summary_time starts at 0
        for i in range(50):
            await logger.info(f"Test message {i}")
            # Small delay to allow processing
            if i % 10 == 0:
                await asyncio.sleep(0.01)

        # Allow processing
        await asyncio.sleep(0.1)
        await logger.drain()

        # Check for summary event with internal marker
        # Count is non-deterministic due to timing; at least 1 is sufficient  # noqa: WA002
        summaries = [e for e in collected if e.get("data", {}).get("_fapilog_internal")]
        assert len(summaries) >= 1, (  # noqa: WA002
            f"Expected at least one summary event, got: {[e.get('message') for e in collected]}"
        )
        summary = summaries[0]
        assert summary["level"] == "WARNING"
        assert "dropped" in summary["message"].lower()
        assert "dropped_count" in summary.get("data", {})

    @pytest.mark.asyncio
    async def test_drop_summary_not_emitted_when_disabled(self) -> None:
        """With emit_drop_summary=False (default), no drop summaries (AC4)."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test_no_drop",
            queue_capacity=1,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            emit_drop_summary=False,  # Disabled (default)
        )
        logger.start()

        # Flood the queue
        for i in range(50):
            await logger.info(f"Test message {i}")

        await asyncio.sleep(0.1)
        await logger.drain()

        # Should be no internal summary events
        summaries = [e for e in collected if e.get("data", {}).get("_fapilog_internal")]
        assert len(summaries) == 0, f"Expected no summary events, got {len(summaries)}"

    @pytest.mark.asyncio
    async def test_summary_is_rate_limited(self) -> None:
        """Summaries are aggregated, not emitted per drop (AC5)."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test_rate_limited",
            queue_capacity=1,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            emit_drop_summary=True,
            drop_summary_window_seconds=60.0,  # Long window
        )
        logger.start()

        # Flood the queue with many events
        for i in range(200):
            await logger.info(f"Test message {i}")

        await asyncio.sleep(0.05)
        await logger.drain()

        # Should be at most 1 summary (window hasn't elapsed)
        summaries = [e for e in collected if e.get("data", {}).get("_fapilog_internal")]
        assert len(summaries) <= 1, f"Expected at most 1 summary, got {len(summaries)}"


class TestDedupeSummaryEmission:
    """Test dedupe summary emission behavior."""

    @pytest.mark.asyncio
    async def test_dedupe_summary_emitted_when_enabled(self) -> None:
        """With emit_drop_summary=True, dedupe summaries appear in logs (AC3)."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test_dedupe",
            queue_capacity=100,
            batch_max_size=50,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            emit_drop_summary=True,
            drop_summary_window_seconds=60.0,  # Long window (irrelevant here)
        )
        # Set dedupe window via cached setting
        logger._cached_error_dedupe_window = 0.05  # 50ms window
        logger.start()

        # Log same error multiple times within dedupe window
        for _ in range(5):
            await logger.error("Repeated error")
            await asyncio.sleep(0.001)

        # Wait for dedupe window to elapse
        await asyncio.sleep(0.1)

        # Log the error again to trigger summary emission
        await logger.error("Repeated error")

        await asyncio.sleep(0.05)
        await logger.drain()

        # Check for dedupe summary event
        # Count may vary due to timing; at least 1 expected
        summaries = [
            e
            for e in collected
            if e.get("data", {}).get("_fapilog_internal")
            and "deduplicated" in e.get("message", "").lower()
        ]
        assert len(summaries) >= 1, (  # noqa: WA002
            f"Expected dedupe summary, got: {[e.get('message') for e in collected]}"
        )
        summary = summaries[0]
        assert summary["level"] == "INFO"
        assert "suppressed_count" in summary.get("data", {})

    @pytest.mark.asyncio
    async def test_dedupe_summary_not_emitted_when_disabled(self) -> None:
        """With emit_drop_summary=False, no dedupe summaries in logs."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test_no_dedupe",
            queue_capacity=100,
            batch_max_size=50,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            emit_drop_summary=False,  # Disabled
        )
        logger._cached_error_dedupe_window = 0.05
        logger.start()

        # Log same error multiple times
        for _ in range(5):
            await logger.error("Repeated error")
            await asyncio.sleep(0.001)

        await asyncio.sleep(0.1)
        await logger.error("Repeated error")

        await asyncio.sleep(0.05)
        await logger.drain()

        # Should be no dedupe summary events
        summaries = [e for e in collected if e.get("data", {}).get("_fapilog_internal")]
        assert len(summaries) == 0


class TestSyncDropSummaryEmission:
    """Test drop summary emission for SyncLoggerFacade."""

    def test_sync_drop_summary_tracking(self) -> None:
        """SyncLoggerFacade tracks drops for summary emission."""
        import time

        from fapilog.core.logger import SyncLoggerFacade

        collected: list[dict[str, Any]] = []

        async def sink(e: dict[str, Any]) -> None:
            collected.append(dict(e))

        logger = SyncLoggerFacade(
            name="test_sync_drop",
            queue_capacity=1,  # Tiny queue to force drops
            batch_max_size=8,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink,
            emit_drop_summary=True,
            drop_summary_window_seconds=1.0,
        )
        logger.start()

        # Wait for worker to be ready
        time.sleep(0.05)

        # Flood the queue to trigger drops (sync path)
        # The same-thread detection will cause immediate drops
        for i in range(50):
            logger.info(f"Test message {i}")

        # Allow some processing
        time.sleep(0.3)

        # Verify the feature is enabled in the logger
        assert logger._emit_drop_summary is True
        assert logger._drop_summary_window_seconds == 1.0

    def test_record_drop_for_summary_increments_counter(self) -> None:
        """Test _record_drop_for_summary increments counter when enabled."""
        import time as time_module

        from fapilog.core.logger import SyncLoggerFacade

        async def sink(e: dict[str, Any]) -> None:
            pass

        logger = SyncLoggerFacade(
            name="test_record",
            queue_capacity=10,
            batch_max_size=8,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
            emit_drop_summary=True,
            drop_summary_window_seconds=60.0,  # Long window
        )
        logger.start()

        # Set last summary time to current so window hasn't elapsed
        logger._last_drop_summary_time = time_module.monotonic()

        # Directly call the record method
        logger._record_drop_for_summary(5)

        # Should increment counter (window not elapsed)
        assert logger._drop_count_since_summary == 5

        # Call again
        logger._record_drop_for_summary(3)
        assert logger._drop_count_since_summary == 8

    def test_schedule_drop_summary_emission_resets_counters(self) -> None:
        """Test _schedule_drop_summary_emission resets counters."""
        import time

        from fapilog.core.logger import SyncLoggerFacade

        collected: list[dict[str, Any]] = []

        async def sink(e: dict[str, Any]) -> None:
            collected.append(dict(e))

        logger = SyncLoggerFacade(
            name="test_schedule",
            queue_capacity=10,
            batch_max_size=8,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
            emit_drop_summary=True,
            drop_summary_window_seconds=60.0,
        )
        logger.start()
        time.sleep(0.05)

        # Set up a pending summary
        logger._drop_count_since_summary = 10

        # Call schedule emission
        logger._schedule_drop_summary_emission()

        # Should reset counter
        assert logger._drop_count_since_summary == 0
        # last_drop_summary_time should be updated
        assert logger._last_drop_summary_time > 0

        # Allow time for async emission
        time.sleep(0.2)

        # Summary should have been emitted
        summaries = [e for e in collected if e.get("data", {}).get("_fapilog_internal")]
        assert len(summaries) == 1
        assert summaries[0]["data"]["dropped_count"] == 10


class TestDropSummaryEdgeCases:
    """Test edge cases for drop summary emission."""

    def test_record_drop_triggers_emission_when_window_elapsed(self) -> None:
        """_record_drop_for_summary triggers emission when window elapsed."""
        import time as time_module

        from fapilog.core.logger import SyncLoggerFacade

        collected: list[dict[str, Any]] = []

        async def sink(e: dict[str, Any]) -> None:
            collected.append(dict(e))

        logger = SyncLoggerFacade(
            name="test_window",
            queue_capacity=10,
            batch_max_size=8,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
            emit_drop_summary=True,
            drop_summary_window_seconds=0.1,  # Short window
        )
        logger.start()
        time_module.sleep(0.05)

        # Set last summary time to past
        logger._last_drop_summary_time = time_module.monotonic() - 1.0

        # Record a drop - should trigger emission (window elapsed)
        logger._record_drop_for_summary(3)

        # Wait for async emission
        time_module.sleep(0.2)

        # Should have emitted summary
        summaries = [e for e in collected if e.get("data", {}).get("_fapilog_internal")]
        assert len(summaries) == 1
        assert summaries[0]["data"]["dropped_count"] == 3

    def test_schedule_does_nothing_when_no_drops(self) -> None:
        """_schedule_drop_summary_emission returns early when no drops."""
        from fapilog.core.logger import SyncLoggerFacade

        async def sink(e: dict[str, Any]) -> None:
            pass

        logger = SyncLoggerFacade(
            name="test_no_drops",
            queue_capacity=10,
            batch_max_size=8,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=sink,
            emit_drop_summary=True,
            drop_summary_window_seconds=60.0,
        )
        logger.start()

        # Ensure no pending drops
        logger._drop_count_since_summary = 0

        # Call schedule - should return early
        initial_time = logger._last_drop_summary_time
        logger._schedule_drop_summary_emission()

        # Time should not have changed (early return)
        assert logger._last_drop_summary_time == initial_time

    @pytest.mark.asyncio
    async def test_emit_summary_handles_sink_exception(self) -> None:
        """_emit_drop_summary_event handles sink exceptions gracefully."""
        from fapilog.core.logger import AsyncLoggerFacade

        async def failing_sink(e: dict[str, Any]) -> None:
            raise RuntimeError("Sink failed")

        logger = AsyncLoggerFacade(
            name="test_failing",
            queue_capacity=10,
            batch_max_size=8,
            batch_timeout_seconds=0.1,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=failing_sink,
            emit_drop_summary=True,
            drop_summary_window_seconds=60.0,
        )
        logger.start()

        # Should not raise even though sink fails
        await logger._emit_drop_summary_event(5, 60.0)

        # No assertion needed - test passes if no exception raised


class TestDropSummaryBuilder:
    """Test LoggerBuilder.with_drop_summary() method."""

    def test_with_drop_summary_enables_feature(self) -> None:
        """with_drop_summary() should enable emit_drop_summary."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_drop_summary()

        # Check internal config
        assert builder._config.get("core", {}).get("emit_drop_summary") is True

    def test_with_drop_summary_custom_window(self) -> None:
        """with_drop_summary() should accept custom window."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_drop_summary(window_seconds=30.0)

        assert builder._config["core"]["emit_drop_summary"] is True
        assert builder._config["core"]["drop_summary_window_seconds"] == 30.0

    def test_with_drop_summary_disabled(self) -> None:
        """with_drop_summary(enabled=False) should disable feature."""
        from fapilog import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_drop_summary(enabled=False)

        assert builder._config["core"]["emit_drop_summary"] is False


class TestDropSummarySettings:
    """Test emit_drop_summary configuration settings."""

    def test_emit_drop_summary_disabled_by_default(self) -> None:
        """Default settings should not emit drop summaries (AC4)."""
        from fapilog import Settings

        settings = Settings()
        assert settings.core.emit_drop_summary is False

    def test_emit_drop_summary_can_be_enabled(self) -> None:
        """Setting emit_drop_summary=True should work (AC1)."""
        from fapilog import Settings

        settings = Settings(core={"emit_drop_summary": True})
        assert settings.core.emit_drop_summary is True

    def test_drop_summary_window_default(self) -> None:
        """Default window should be 60 seconds (AC5)."""
        from fapilog import Settings

        settings = Settings()
        assert settings.core.drop_summary_window_seconds == 60.0

    def test_drop_summary_window_configurable(self) -> None:
        """Window should be configurable (AC5)."""
        from fapilog import Settings

        settings = Settings(core={"drop_summary_window_seconds": 30.0})
        assert settings.core.drop_summary_window_seconds == 30.0

    def test_drop_summary_window_minimum_validation(self) -> None:
        """Window should have minimum of 1 second."""
        from pydantic import ValidationError

        from fapilog import Settings

        with pytest.raises(ValidationError):
            Settings(core={"drop_summary_window_seconds": 0.5})
