"""Tests for DualQueue shedding mechanism (Story 1.59).

Covers AC1 (shedding flag toggle), AC2 (try_dequeue skips main when shedding),
AC8 (drain_into ignores shedding), and enqueue behavior during shedding.
"""

from __future__ import annotations

from fapilog.core.concurrency import DualQueue


class TestSheddingFlagToggle:
    """AC1: DualQueue exposes activate/deactivate/is_shedding."""

    def test_shedding_defaults_to_false(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        assert dq.is_shedding is False

    def test_activate_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.activate_shedding()
        assert dq.is_shedding is True

    def test_deactivate_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.activate_shedding()
        dq.deactivate_shedding()
        assert dq.is_shedding is False

    def test_double_activate_is_idempotent(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.activate_shedding()
        dq.activate_shedding()
        assert dq.is_shedding is True

    def test_double_deactivate_is_idempotent(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.deactivate_shedding()
        assert dq.is_shedding is False


class TestProtectedCapacityProperty:
    """AC1 supplement: DualQueue exposes protected_capacity."""

    def test_protected_capacity_returns_correct_value(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=42,
            protected_levels=frozenset({"ERROR"}),
        )
        assert dq.protected_capacity == 42


class TestTryDequeueSkipsMainWhenShedding:
    """AC2: try_dequeue only returns protected events when shedding."""

    def test_returns_protected_event_when_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "message": "main event"})
        dq.try_enqueue({"level": "ERROR", "message": "protected event"})
        dq.activate_shedding()

        ok, item = dq.try_dequeue()
        assert ok is True
        assert item is not None and item["level"] == "ERROR"

    def test_skips_main_event_when_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "message": "main event"})
        dq.try_enqueue({"level": "ERROR", "message": "protected event"})
        dq.activate_shedding()

        # Drain the protected event
        dq.try_dequeue()

        # Main event should be skipped
        ok, item = dq.try_dequeue()
        assert ok is False
        assert item is None

    def test_main_event_available_after_deactivating_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "message": "main event"})
        dq.try_enqueue({"level": "ERROR", "message": "protected event"})
        dq.activate_shedding()

        # Drain the protected event
        dq.try_dequeue()

        # Deactivate shedding
        dq.deactivate_shedding()

        # Main event should now be available
        ok, item = dq.try_dequeue()
        assert ok is True
        assert item is not None and item["level"] == "INFO"

    def test_empty_queues_return_false_when_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.activate_shedding()
        ok, item = dq.try_dequeue()
        assert ok is False
        assert item is None


class TestEnqueueUnaffectedByShedding:
    """Shedding should not affect enqueue behavior — main queue still accepts."""

    def test_main_enqueue_works_during_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.activate_shedding()
        ok = dq.try_enqueue({"level": "INFO", "message": "main event"})
        assert ok is True
        assert dq.main_qsize() == 1

    def test_protected_enqueue_works_during_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.activate_shedding()
        ok = dq.try_enqueue({"level": "ERROR", "message": "protected event"})
        assert ok is True
        assert dq.protected_qsize() == 1


class TestDrainIntoIgnoresShedding:
    """AC8: drain_into drains both queues regardless of shedding state."""

    def test_drain_into_drains_both_queues_when_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "message": "main 1"})
        dq.try_enqueue({"level": "INFO", "message": "main 2"})
        dq.try_enqueue({"level": "ERROR", "message": "protected 1"})

        dq.activate_shedding()

        batch: list[dict[str, str]] = []
        dq.drain_into(batch)

        assert len(batch) == 3
        # Protected events drained first, then main
        levels = [e["level"] for e in batch]
        assert levels == ["ERROR", "INFO", "INFO"]

    def test_queues_empty_after_drain_into_when_shedding(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "message": "main"})
        dq.try_enqueue({"level": "ERROR", "message": "protected"})

        dq.activate_shedding()

        batch: list[dict[str, str]] = []
        dq.drain_into(batch)

        assert dq.is_empty() is True
        assert dq.main_qsize() == 0
        assert dq.protected_qsize() == 0
