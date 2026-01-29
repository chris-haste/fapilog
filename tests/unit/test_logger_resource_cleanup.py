"""Tests for logger resource cleanup on drain (Story 4.63).

Verifies that internal data structures are cleared after stop_and_drain()
to prevent memory leaks in long-running applications.
"""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector, PluginStats


async def _collecting_sink(
    collected: list[dict[str, Any]], entry: dict[str, Any]
) -> None:
    collected.append(dict(entry))


class TestMetricsCollectorCleanup:
    """Tests for MetricsCollector.cleanup() method."""

    def test_cleanup_clears_plugin_stats(self) -> None:
        """AC2: MetricsCollector._plugin_stats cleared on cleanup()."""
        collector = MetricsCollector(enabled=False)
        # Populate _plugin_stats
        collector._plugin_stats["test_plugin"] = PluginStats(
            executions=10, errors=1, total_duration_seconds=0.5
        )
        collector._plugin_stats["another_plugin"] = PluginStats(
            executions=5, errors=0, total_duration_seconds=0.2
        )

        collector.cleanup()

        assert collector._plugin_stats == {}

    def test_cleanup_idempotent(self) -> None:
        """Calling cleanup() multiple times is safe."""
        collector = MetricsCollector(enabled=False)
        collector._plugin_stats["test"] = PluginStats()

        collector.cleanup()
        collector.cleanup()  # Should not raise

        assert collector._plugin_stats == {}


class TestLoggerResourceCleanup:
    """Tests for logger resource cleanup on drain."""

    @pytest.mark.asyncio
    async def test_error_dedupe_cleared_on_drain(self) -> None:
        """AC1: _error_dedupe dictionary cleared after stop_and_drain()."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test-dedupe-cleanup",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        # Populate _error_dedupe by manually setting entries
        logger._error_dedupe["test error 1"] = (1000.0, 5)
        logger._error_dedupe["test error 2"] = (1000.0, 3)

        await logger.info("test message")
        await logger.stop_and_drain()

        assert logger._error_dedupe == {}

    @pytest.mark.asyncio
    async def test_worker_tasks_cleared_on_drain(self) -> None:
        """AC3: _worker_tasks list cleared after stop_and_drain()."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test-tasks-cleanup",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        # Log something to ensure workers are active
        await logger.info("test message")

        await logger.stop_and_drain()

        assert logger._worker_tasks == []

    @pytest.mark.asyncio
    async def test_plugin_lists_cleared_on_drain(self) -> None:
        """AC4: All plugin reference lists cleared after stop_and_drain()."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test-plugins-cleanup",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        await logger.info("test message")
        await logger.stop_and_drain()

        assert logger._enrichers == []
        assert logger._processors == []
        assert logger._filters == []
        assert logger._redactors == []
        assert logger._sinks == []

    @pytest.mark.asyncio
    async def test_metrics_cleanup_called_on_drain(self) -> None:
        """AC2: MetricsCollector.cleanup() called during drain."""
        collected: list[dict[str, Any]] = []
        metrics = MetricsCollector(enabled=False)
        # Pre-populate stats
        metrics._plugin_stats["test_plugin"] = PluginStats(executions=5)

        logger = AsyncLoggerFacade(
            name="test-metrics-cleanup",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
            metrics=metrics,
        )

        await logger.info("test message")
        await logger.stop_and_drain()

        assert metrics._plugin_stats == {}

    @pytest.mark.asyncio
    async def test_drain_still_reports_accurate_counts(self) -> None:
        """AC5: DrainResult still reports accurate counts after cleanup changes."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test-drain-counts",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        await logger.info("message 1")
        await logger.info("message 2")
        await logger.info("message 3")

        result = await logger.stop_and_drain()

        assert result.submitted == 3
        assert result.processed >= 3

    @pytest.mark.asyncio
    async def test_cleanup_idempotent_double_drain(self) -> None:
        """Calling drain twice is safe (idempotent cleanup)."""
        collected: list[dict[str, Any]] = []
        logger = AsyncLoggerFacade(
            name="test-double-drain",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        await logger.info("test")

        result1 = await logger.stop_and_drain()
        result2 = await logger.stop_and_drain()  # Should not raise

        # First call gets the submitted count, second sees same value (no new submits)
        assert result1.submitted == 1
        assert result2.submitted == 1  # Same value since no new logs submitted


class TestSyncLoggerResourceCleanup:
    """Tests for sync logger resource cleanup on drain."""

    @pytest.mark.asyncio
    async def test_sync_logger_cleanup_on_drain(self) -> None:
        """Sync logger also cleans up resources on drain."""
        collected: list[dict[str, Any]] = []
        logger = SyncLoggerFacade(
            name="test-sync-cleanup",
            queue_capacity=16,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=lambda e: _collecting_sink(collected, e),
        )

        # Populate internal state
        logger._error_dedupe["test error"] = (1000.0, 2)

        logger.info("test message")

        await logger.stop_and_drain()

        assert logger._error_dedupe == {}
        assert logger._worker_tasks == []
        assert logger._enrichers == []
        assert logger._processors == []
        assert logger._filters == []
        assert logger._redactors == []
        assert logger._sinks == []
