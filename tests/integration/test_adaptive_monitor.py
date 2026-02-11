"""Integration tests for PressureMonitor lifecycle in the logger."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.concurrency import PriorityAwareQueue
from fapilog.core.pressure import PressureLevel, PressureMonitor


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
