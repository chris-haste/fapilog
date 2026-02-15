"""Integration tests for PressureMonitor lifecycle in the logger."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from fapilog.core.concurrency import PriorityAwareQueue
from fapilog.core.logger import SyncLoggerFacade
from fapilog.core.pressure import PressureLevel, PressureMonitor


async def _noop_sink(entry: dict[str, Any]) -> None:
    pass


async def _slow_sink(entry: dict[str, Any]) -> None:
    await asyncio.sleep(100.0)


class TestMonitorLifecycle:
    @pytest.mark.asyncio
    async def test_monitor_coexists_with_workers(self) -> None:
        """Monitor runs alongside a simulated worker without interference."""
        queue: PriorityAwareQueue[dict[str, Any]] = PriorityAwareQueue(
            capacity=100, protected_levels=frozenset()
        )
        monitor = PressureMonitor(
            queue=queue,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )

        # Simulate a worker draining
        worker_ran = False

        async def fake_worker() -> None:
            nonlocal worker_ran
            await asyncio.sleep(0.05)
            worker_ran = True

        monitor_task = asyncio.create_task(monitor.run())
        worker_task = asyncio.create_task(fake_worker())

        await worker_task
        monitor.stop()
        await monitor_task

        assert worker_ran
        # Monitor should have evaluated at least once
        assert monitor.pressure_level == PressureLevel.NORMAL

    @pytest.mark.asyncio
    async def test_monitor_reads_live_queue_state(self) -> None:
        """Monitor reacts to queue fill changes."""
        queue: PriorityAwareQueue[dict[str, Any]] = PriorityAwareQueue(
            capacity=100, protected_levels=frozenset()
        )
        monitor = PressureMonitor(
            queue=queue,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )

        changes: list[tuple[PressureLevel, PressureLevel]] = []
        monitor.on_level_change(lambda old, new: changes.append((old, new)))

        # Fill queue to 65%
        for _ in range(65):
            queue.try_enqueue({"level": "INFO", "message": "test"})

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)

        assert monitor.pressure_level == PressureLevel.ELEVATED
        assert len(changes) == 1

        monitor.stop()
        await task

    @pytest.mark.asyncio
    async def test_monitor_stops_cleanly(self) -> None:
        """Monitor exits its loop when stop() is called."""
        queue: PriorityAwareQueue[dict[str, Any]] = PriorityAwareQueue(
            capacity=100, protected_levels=frozenset()
        )
        monitor = PressureMonitor(
            queue=queue,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
        )

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.03)
        monitor.stop()
        await asyncio.wait_for(task, timeout=1.0)

        assert task.done()
        assert not task.cancelled()


class TestLoggerMonitorWiring:
    """Tests for PressureMonitor lifecycle wired through the logger."""

    @pytest.mark.asyncio
    async def test_monitor_started_when_adaptive_enabled(self) -> None:
        """Logger creates and starts PressureMonitor task when adaptive.enabled=True."""
        logger = SyncLoggerFacade(
            name="t-adaptive",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        # Cache adaptive settings as enabled
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        # Monitor task should be running
        assert isinstance(logger._pressure_monitor, PressureMonitor)
        assert isinstance(logger._pressure_monitor_task, asyncio.Task)
        assert not logger._pressure_monitor_task.done()

        res = await logger.stop_and_drain()
        assert res.dropped == 0
        # Monitor should be cleaned up after drain
        assert logger._pressure_monitor is None
        assert logger._pressure_monitor_task is None

    @pytest.mark.asyncio
    async def test_monitor_not_started_when_adaptive_disabled(self) -> None:
        """Logger does not create PressureMonitor when adaptive.enabled=False."""
        logger = SyncLoggerFacade(
            name="t-no-adaptive",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )

        logger.start()
        assert logger._pressure_monitor is None
        assert logger._pressure_monitor_task is None

        res = await logger.stop_and_drain()
        assert res.dropped == 0

    @pytest.mark.asyncio
    async def test_monitor_stops_before_workers_on_drain(self) -> None:
        """Monitor stop is called before workers during drain."""
        logger = SyncLoggerFacade(
            name="t-drain-order",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        assert isinstance(logger._pressure_monitor, PressureMonitor)
        monitor_task = logger._pressure_monitor_task
        assert isinstance(monitor_task, asyncio.Task)
        assert not monitor_task.done()

        res = await logger.stop_and_drain()
        assert res.dropped == 0
        # After drain, monitor task completed and references cleared
        assert monitor_task.done()
        assert logger._pressure_monitor is None
        assert logger._pressure_monitor_task is None

    @pytest.mark.asyncio
    async def test_settings_caching_enables_monitor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AdaptiveSettings.enabled=True in Settings triggers monitor creation."""
        monkeypatch.setenv("FAPILOG_ADAPTIVE__ENABLED", "true")
        logger = SyncLoggerFacade(
            name="t-settings-cache",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=_noop_sink,
        )
        # _common_init should have cached adaptive settings from env
        assert logger._cached_adaptive_enabled is True
        assert logger._cached_adaptive_settings.enabled is True

        logger.start()
        assert isinstance(logger._pressure_monitor, PressureMonitor)
        await logger.stop_and_drain()

    @pytest.mark.asyncio
    async def test_monitor_transition_fires_diagnostic_and_metric(self) -> None:
        """State transition through logger-wired monitor fires diagnostic and metric closures."""

        from fapilog.metrics.metrics import MetricsCollector

        logger = SyncLoggerFacade(
            name="t-closures",
            queue_capacity=100,
            batch_max_size=1,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=_slow_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        # Provide a real metrics collector so _metric_setter closure fires
        logger._metrics = MetricsCollector(enabled=True)

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        logger.start()
        # Slow sink blocks worker after first dequeue — items stay queued
        # Need enough items to stay above de-escalation threshold (0.40)
        # even after queue grows to 175 at ELEVATED (1.75x with default 4.0)
        for i in range(80):
            logger.info("fill", idx=i)

        # Give monitor time to sample the filled queue
        await asyncio.sleep(0.1)
        assert isinstance(logger._pressure_monitor, PressureMonitor)
        assert logger._pressure_monitor.pressure_level == PressureLevel.ELEVATED

        # Clean up: stop the worker thread
        logger._stop_flag = True
        loop = logger._worker_loop
        if loop is not None:

            async def _cancel_all() -> None:
                if logger._pressure_monitor_task is not None:
                    logger._pressure_monitor_task.cancel()
                    try:
                        await logger._pressure_monitor_task
                    except (asyncio.CancelledError, Exception):
                        pass
                for task in logger._worker_tasks:
                    task.cancel()
                await asyncio.gather(*logger._worker_tasks, return_exceptions=True)
                loop.call_soon(loop.stop)

            asyncio.run_coroutine_threadsafe(_cancel_all(), loop)
        if logger._worker_thread is not None:
            logger._worker_thread.join(timeout=5.0)

    def test_thread_mode_drain_stops_monitor(self) -> None:
        """In thread mode, drain stops the pressure monitor."""
        collected: list[dict[str, Any]] = []

        async def collecting_sink(entry: dict[str, Any]) -> None:
            collected.append(dict(entry))

        logger = SyncLoggerFacade(
            name="t-thread-drain",
            queue_capacity=100,
            batch_max_size=8,
            batch_timeout_seconds=0.05,
            backpressure_wait_ms=10,
            drop_on_full=True,
            sink_write=collecting_sink,
        )
        from fapilog.core.settings import AdaptiveSettings

        logger._cached_adaptive_enabled = True
        logger._cached_adaptive_settings = AdaptiveSettings(
            enabled=True, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        # Start in a separate thread to force thread-loop mode
        def start_in_thread() -> None:
            logger.start()

        t = threading.Thread(target=start_in_thread)
        t.start()
        t.join(timeout=3.0)

        assert isinstance(logger._worker_thread, threading.Thread)
        assert isinstance(logger._pressure_monitor, PressureMonitor)

        # Drain in thread mode (synchronous call)
        logger._drain_thread_mode(warn_on_timeout=False)
        assert logger._worker_thread is None
