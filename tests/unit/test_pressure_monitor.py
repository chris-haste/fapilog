"""Unit tests for PressureMonitor."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from fapilog.core.pressure import PressureLevel, PressureMonitor


def _make_queue(qsize: int = 0, capacity: int = 100) -> MagicMock:
    """Create a mock queue with configurable fill ratio."""
    q = MagicMock()
    q.qsize.return_value = qsize
    q.capacity = capacity
    return q


class TestPressureMonitorSampling:
    @pytest.mark.asyncio
    async def test_monitor_reads_queue_fill_ratio(self) -> None:
        """Monitor evaluates fill ratio from queue.qsize()/capacity."""
        queue = _make_queue(qsize=70, capacity=100)
        monitor = PressureMonitor(
            queue=queue, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        # Run one tick
        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        assert monitor.pressure_level == PressureLevel.ELEVATED
        queue.qsize.assert_called()

    @pytest.mark.asyncio
    async def test_stop_flag_exits_loop(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(
            queue=queue, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.03)
        monitor.stop()
        await asyncio.wait_for(task, timeout=1.0)
        # Task should complete without error
        assert task.done()


class TestPressureMonitorCallbacks:
    @pytest.mark.asyncio
    async def test_callback_invoked_on_level_change(self) -> None:
        queue = _make_queue(qsize=70, capacity=100)
        monitor = PressureMonitor(
            queue=queue, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        changes: list[tuple[PressureLevel, PressureLevel]] = []
        monitor.on_level_change(lambda old, new: changes.append((old, new)))

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        # Constant fill=70% triggers exactly one transition: NORMAL→ELEVATED
        assert len(changes) == 1
        assert changes[0] == (PressureLevel.NORMAL, PressureLevel.ELEVATED)

    @pytest.mark.asyncio
    async def test_no_callback_when_level_unchanged(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)  # Stays NORMAL
        monitor = PressureMonitor(
            queue=queue, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        changes: list[tuple[PressureLevel, PressureLevel]] = []
        monitor.on_level_change(lambda old, new: changes.append((old, new)))

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_multiple_callbacks_all_invoked(self) -> None:
        queue = _make_queue(qsize=70, capacity=100)
        monitor = PressureMonitor(
            queue=queue, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        cb1_called: list[bool] = []
        cb2_called: list[bool] = []
        monitor.on_level_change(lambda old, new: cb1_called.append(True))
        monitor.on_level_change(lambda old, new: cb2_called.append(True))

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        # Both callbacks should fire exactly once (one state change)
        assert len(cb1_called) == 1
        assert len(cb2_called) == 1

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_crash_monitor(self) -> None:
        queue = _make_queue(qsize=70, capacity=100)
        monitor = PressureMonitor(
            queue=queue, check_interval_seconds=0.01, cooldown_seconds=0.0
        )

        def bad_callback(old: PressureLevel, new: PressureLevel) -> None:
            raise RuntimeError("callback error")

        good_calls: list[bool] = []
        monitor.on_level_change(bad_callback)
        monitor.on_level_change(lambda old, new: good_calls.append(True))

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        # Monitor survived the exception and called the good callback
        assert len(good_calls) == 1
        assert monitor.pressure_level == PressureLevel.ELEVATED


class TestPressureMonitorDiagnostics:
    @pytest.mark.asyncio
    async def test_diagnostic_emitted_on_transition(self) -> None:
        queue = _make_queue(qsize=70, capacity=100)
        diagnostics: list[dict[str, Any]] = []

        def capture_diagnostic(payload: dict[str, Any]) -> None:
            diagnostics.append(payload)

        monitor = PressureMonitor(
            queue=queue,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
            diagnostic_writer=capture_diagnostic,
        )

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        # Exactly one diagnostic for NORMAL→ELEVATED transition
        assert len(diagnostics) == 1
        diag = diagnostics[0]
        assert diag["component"] == "adaptive-controller"
        assert diag["message"] == "pressure level changed"
        assert diag["from_level"] == "normal"
        assert diag["to_level"] == "elevated"
        assert diag["fill_ratio"] == 0.7


class TestPressureMonitorMetrics:
    @pytest.mark.asyncio
    async def test_metric_updated_on_transition(self) -> None:
        queue = _make_queue(qsize=70, capacity=100)
        metric_values: list[int] = []

        def metric_setter(value: int) -> None:
            metric_values.append(value)

        monitor = PressureMonitor(
            queue=queue,
            check_interval_seconds=0.01,
            cooldown_seconds=0.0,
            metric_setter=metric_setter,
        )

        task = asyncio.create_task(monitor.run())
        await asyncio.sleep(0.05)
        monitor.stop()
        await task

        # Should have set metric to 1 (ELEVATED index) exactly once
        assert metric_values == [1]
