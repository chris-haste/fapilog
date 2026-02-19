"""Tests for PressureMonitor protected queue shedding (Story 1.59).

Covers AC3 (shed activates/deactivates at threshold), AC4 (hysteresis),
AC6 (diagnostic events), AC7 (shed stats in snapshot), AC10 (no shed for non-DualQueue).
"""

from __future__ import annotations

from typing import Any

from fapilog.core.concurrency import DualQueue, NonBlockingRingQueue
from fapilog.core.pressure import PressureMonitor


def _make_dual_queue(
    main_capacity: int = 100,
    protected_capacity: int = 10,
) -> DualQueue[dict[str, Any]]:
    return DualQueue(
        main_capacity=main_capacity,
        protected_capacity=protected_capacity,
        protected_levels=frozenset({"ERROR"}),
    )


def _fill_protected(dq: DualQueue[dict[str, Any]], count: int) -> None:
    """Fill the protected queue with count events."""
    for _ in range(count):
        dq.try_enqueue({"level": "ERROR", "message": "fill"})


def _drain_protected(dq: DualQueue[dict[str, Any]], count: int) -> None:
    """Drain count events from the protected queue."""
    for _ in range(count):
        dq.try_dequeue()


class TestShedActivatesAtThreshold:
    """AC3: Shed activates when protected fill ratio >= shed_threshold."""

    def test_shed_activates_at_threshold(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Fill 7 out of 10 = 0.70
        _fill_protected(dq, 7)
        monitor._tick()

        assert dq.is_shedding is True

    def test_shed_does_not_activate_below_threshold(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Fill 6 out of 10 = 0.60 (below 0.70)
        _fill_protected(dq, 6)
        monitor._tick()

        assert dq.is_shedding is False


class TestShedDeactivatesAtRecoveryThreshold:
    """AC3: Shed deactivates when protected fill ratio < recover_threshold."""

    def test_shed_deactivates_below_recovery(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Activate shedding
        _fill_protected(dq, 7)
        monitor._tick()
        assert dq.is_shedding is True

        # Drain to 2 out of 10 = 0.20 (below 0.30)
        _drain_protected(dq, 5)
        monitor._tick()

        assert dq.is_shedding is False


class TestHysteresisPreventsOscillation:
    """AC4: Shed/recover thresholds prevent rapid toggling."""

    def test_shedding_stays_active_between_thresholds(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Activate shedding at 70%
        _fill_protected(dq, 7)
        monitor._tick()
        assert dq.is_shedding is True

        # Drain to 50% — still shedding (above 30%)
        _drain_protected(dq, 2)
        monitor._tick()
        assert dq.is_shedding is True

    def test_shedding_stays_inactive_between_thresholds(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Fill to 50% — shedding stays inactive (below 70%)
        _fill_protected(dq, 5)
        monitor._tick()
        assert dq.is_shedding is False

    def test_full_hysteresis_cycle(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # 1) 70% → activate
        _fill_protected(dq, 7)
        monitor._tick()
        assert dq.is_shedding is True

        # 2) 50% → still active
        _drain_protected(dq, 2)
        monitor._tick()
        assert dq.is_shedding is True

        # 3) 20% → deactivate
        _drain_protected(dq, 3)
        monitor._tick()
        assert dq.is_shedding is False

        # 4) 50% → still inactive
        _fill_protected(dq, 3)
        monitor._tick()
        assert dq.is_shedding is False


class TestDiagnosticEventsOnShedTransitions:
    """AC6: Diagnostic events emitted on shed activation/deactivation."""

    def test_diagnostic_emitted_on_activation(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        diagnostics: list[dict[str, Any]] = []
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
            diagnostic_writer=diagnostics.append,
        )

        _fill_protected(dq, 7)
        monitor._tick()

        shed_events = [
            d for d in diagnostics if d.get("message") == "protected shedding activated"
        ]
        assert len(shed_events) == 1
        event = shed_events[0]
        assert event["component"] == "adaptive-controller"
        assert event["protected_fill_ratio"] == 0.7
        assert event["protected_qsize"] == 7
        assert event["protected_capacity"] == 10

    def test_diagnostic_emitted_on_deactivation(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        diagnostics: list[dict[str, Any]] = []
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
            diagnostic_writer=diagnostics.append,
        )

        # Activate
        _fill_protected(dq, 7)
        monitor._tick()

        # Deactivate
        _drain_protected(dq, 5)
        monitor._tick()

        deactivate_events = [
            d
            for d in diagnostics
            if d.get("message") == "protected shedding deactivated"
        ]
        assert len(deactivate_events) == 1
        event = deactivate_events[0]
        assert event["component"] == "adaptive-controller"
        assert event["protected_fill_ratio"] == 0.2
        assert "shed_duration_seconds" in event

    def test_no_diagnostic_when_no_writer(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
            diagnostic_writer=None,
        )

        _fill_protected(dq, 7)
        # Should not raise
        monitor._tick()
        assert dq.is_shedding is True


class TestShedStatsInSnapshot:
    """AC7: AdaptiveDrainSummary includes shed stats."""

    def test_snapshot_includes_shed_activations(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Activate shedding
        _fill_protected(dq, 7)
        monitor._tick()

        summary = monitor.snapshot()
        assert summary.shed_activations == 1
        # Shedding is still active, so snapshot includes elapsed time > 0
        assert summary.shed_total_seconds > 0.0

    def test_snapshot_includes_multiple_activations(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # First cycle
        _fill_protected(dq, 7)
        monitor._tick()
        _drain_protected(dq, 5)
        monitor._tick()

        # Second cycle
        _fill_protected(dq, 5)
        monitor._tick()
        _drain_protected(dq, 5)
        monitor._tick()

        summary = monitor.snapshot()
        assert summary.shed_activations == 2

    def test_snapshot_defaults_to_zero(self) -> None:
        dq = _make_dual_queue(protected_capacity=10)
        monitor = PressureMonitor(
            queue=dq,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        summary = monitor.snapshot()
        assert summary.shed_activations == 0
        assert summary.shed_total_seconds == 0.0


class TestNoShedEvaluationForNonDualQueue:
    """AC10: No shed evaluation when queue is not DualQueue."""

    def test_non_dual_queue_no_shedding(self) -> None:
        queue: NonBlockingRingQueue[dict[str, Any]] = NonBlockingRingQueue(100)
        monitor = PressureMonitor(
            queue=queue,
            shed_threshold=0.70,
            recover_threshold=0.30,
        )

        # Fill to trigger evaluation
        for _ in range(80):
            queue.try_enqueue({"level": "INFO", "message": "fill"})

        monitor._tick()

        # NonBlockingRingQueue has no shedding API — no errors
        assert not hasattr(queue, "is_shedding")
