"""Unit tests for PressureMonitor counter accumulation and snapshot()."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from fapilog.core.logger import AdaptiveDrainSummary
from fapilog.core.pressure import PressureLevel, PressureMonitor


def _make_queue(qsize: int = 0, capacity: int = 100) -> MagicMock:
    q = MagicMock()
    q.qsize.return_value = qsize
    q.capacity = capacity
    return q


class TestInitialCounters:
    def test_initial_counters_are_zero(self) -> None:
        queue = _make_queue()
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        snapshot = monitor.snapshot()
        assert snapshot.escalation_count == 0
        assert snapshot.deescalation_count == 0
        assert snapshot.peak_pressure_level == PressureLevel.NORMAL
        assert snapshot.filters_swapped == 0
        assert snapshot.workers_scaled == 0
        assert snapshot.peak_workers == 0
        assert snapshot.batch_resize_count == 0


class TestEscalationCounting:
    def test_escalation_increments_count(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        # NORMAL → ELEVATED (escalation)
        queue.qsize.return_value = 70
        monitor._tick()
        snapshot = monitor.snapshot()
        assert snapshot.escalation_count == 1
        assert snapshot.deescalation_count == 0

    def test_deescalation_increments_count(self) -> None:
        queue = _make_queue(qsize=70, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        # NORMAL → ELEVATED
        monitor._tick()
        # ELEVATED → NORMAL (de-escalation)
        queue.qsize.return_value = 0
        monitor._tick()
        snapshot = monitor.snapshot()
        assert snapshot.escalation_count == 1
        assert snapshot.deescalation_count == 1

    def test_peak_level_tracked(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        # NORMAL → ELEVATED
        queue.qsize.return_value = 70
        monitor._tick()
        # ELEVATED → HIGH
        queue.qsize.return_value = 85
        monitor._tick()
        # HIGH → ELEVATED (de-escalation)
        queue.qsize.return_value = 50
        monitor._tick()
        snapshot = monitor.snapshot()
        assert snapshot.peak_pressure_level == PressureLevel.HIGH

    def test_multiple_escalation_deescalation_cycle(self) -> None:
        """Simulate: NORMAL → ELEVATED → HIGH → ELEVATED → NORMAL."""
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        queue.qsize.return_value = 70  # → ELEVATED
        monitor._tick()
        queue.qsize.return_value = 85  # → HIGH
        monitor._tick()
        queue.qsize.return_value = 50  # → ELEVATED
        monitor._tick()
        queue.qsize.return_value = 0  # → NORMAL
        monitor._tick()
        snapshot = monitor.snapshot()
        assert snapshot.escalation_count == 2
        assert snapshot.deescalation_count == 2


class TestTimeAtLevel:
    def test_time_at_level_accumulates(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        # Stay at NORMAL for a bit
        monitor._tick()
        snapshot = monitor.snapshot()
        # All levels present, NORMAL has accumulated time (> 0 since init)
        assert PressureLevel.NORMAL in snapshot.time_at_level
        assert snapshot.time_at_level[PressureLevel.NORMAL] > 0

    def test_time_at_level_finalizes_current_on_snapshot(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        # No transitions, so all time should be at NORMAL
        # Wait a small duration
        time.sleep(0.01)
        snapshot = monitor.snapshot()
        assert snapshot.time_at_level[PressureLevel.NORMAL] >= 0.005
        # Other levels should be 0
        assert snapshot.time_at_level[PressureLevel.ELEVATED] == 0.0
        assert snapshot.time_at_level[PressureLevel.HIGH] == 0.0
        assert snapshot.time_at_level[PressureLevel.CRITICAL] == 0.0

    def test_time_at_level_covers_all_levels(self) -> None:
        queue = _make_queue(qsize=0, capacity=100)
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        snapshot = monitor.snapshot()
        for level in PressureLevel:
            assert level in snapshot.time_at_level


class TestActuatorRecordMethods:
    def test_record_filter_swap_increments(self) -> None:
        queue = _make_queue()
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        monitor.record_filter_swap()
        monitor.record_filter_swap()
        snapshot = monitor.snapshot()
        assert snapshot.filters_swapped == 2

    def test_record_worker_scaling_tracks_peak(self) -> None:
        queue = _make_queue()
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        monitor.record_worker_scaling(4)
        monitor.record_worker_scaling(6)
        monitor.record_worker_scaling(3)
        snapshot = monitor.snapshot()
        assert snapshot.workers_scaled == 3
        assert snapshot.peak_workers == 6

    def test_record_batch_resize_increments(self) -> None:
        queue = _make_queue()
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        monitor.record_batch_resize()
        snapshot = monitor.snapshot()
        assert snapshot.batch_resize_count == 1


class TestSnapshotReturnType:
    def test_snapshot_returns_adaptive_drain_summary(self) -> None:
        queue = _make_queue()
        monitor = PressureMonitor(queue=queue, cooldown_seconds=0.0)
        snapshot = monitor.snapshot()
        assert isinstance(snapshot, AdaptiveDrainSummary)
