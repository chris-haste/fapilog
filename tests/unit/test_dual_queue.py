"""Unit tests for DualQueue (Story 1.52)."""

from __future__ import annotations

import threading

import pytest

from fapilog.core.concurrency import DualQueue


class TestDualQueueRouting:
    """AC1: Protected events route to dedicated queue."""

    def test_protected_event_routes_to_protected_queue(self) -> None:
        dq = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR", "CRITICAL"}),
        )
        dq.try_enqueue({"level": "ERROR", "msg": "b"})
        assert dq.main_qsize() == 0
        assert dq.protected_qsize() == 1

    def test_unprotected_event_routes_to_main_queue(self) -> None:
        dq = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR", "CRITICAL"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "a"})
        assert dq.main_qsize() == 1
        assert dq.protected_qsize() == 0

    def test_routing_combined(self) -> None:
        dq = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR", "CRITICAL"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "a"})
        assert dq.main_qsize() == 1
        assert dq.protected_qsize() == 0

        dq.try_enqueue({"level": "ERROR", "msg": "b"})
        assert dq.main_qsize() == 1
        assert dq.protected_qsize() == 1

    def test_empty_protected_levels_routes_all_to_main(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset(),
        )
        dq.try_enqueue({"level": "ERROR", "msg": "a"})
        assert dq.main_qsize() == 1
        assert dq.protected_qsize() == 0

    def test_case_insensitive_level_matching(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "error", "msg": "a"})
        assert dq.protected_qsize() == 1

    def test_non_dict_item_routes_to_main(self) -> None:
        dq: DualQueue[str] = DualQueue(
            main_capacity=100,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue("plain string")  # type: ignore[arg-type]
        assert dq.main_qsize() == 1
        assert dq.protected_qsize() == 0


class TestDualQueueDequeue:
    """AC2: Workers drain protected queue first."""

    def test_dequeue_prioritizes_protected(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "first"})
        dq.try_enqueue({"level": "ERROR", "msg": "second"})

        ok, item = dq.try_dequeue()
        assert ok is True
        assert item["level"] == "ERROR"

    def test_dequeue_falls_back_to_main(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "only"})

        ok, item = dq.try_dequeue()
        assert ok is True
        assert item["level"] == "INFO"

    def test_dequeue_empty_returns_false(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        ok, item = dq.try_dequeue()
        assert ok is False
        assert item is None


class TestDualQueueIsolation:
    """AC3: Main queue full does not affect protected events."""

    def test_main_full_does_not_block_protected(self) -> None:
        dq = DualQueue(
            main_capacity=2,
            protected_capacity=2,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "1"})
        dq.try_enqueue({"level": "INFO", "msg": "2"})
        assert dq.main_is_full()

        result = dq.try_enqueue({"level": "ERROR", "msg": "3"})
        assert result is True
        assert dq.protected_qsize() == 1

    def test_protected_full_does_not_block_main(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=1,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "ERROR", "msg": "1"})
        assert dq.protected_is_full()

        result = dq.try_enqueue({"level": "INFO", "msg": "2"})
        assert result is True
        assert dq.main_qsize() == 1


class TestDualQueueProtectedFull:
    """AC4: Protected queue full emits diagnostic."""

    def test_protected_full_returns_false(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=1,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "ERROR", "msg": "a"})
        result = dq.try_enqueue({"level": "ERROR", "msg": "b"})
        assert result is False

    def test_protected_drop_increments_counter(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=1,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "ERROR", "msg": "a"})
        dq.try_enqueue({"level": "ERROR", "msg": "b"})  # dropped
        assert dq.protected_drops == 1

    def test_main_drop_increments_counter(self) -> None:
        dq = DualQueue(
            main_capacity=1,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "a"})
        dq.try_enqueue({"level": "INFO", "msg": "b"})  # dropped
        assert dq.main_drops == 1


class TestDualQueueDrain:
    """AC5: Shutdown drain prioritizes protected queue."""

    def test_drain_into_protected_first(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        for i in range(5):
            dq.try_enqueue({"level": "INFO", "msg": f"info-{i}"})
        for i in range(2):
            dq.try_enqueue({"level": "ERROR", "msg": f"error-{i}"})

        batch: list[dict] = []
        dq.drain_into(batch)

        assert batch[0]["level"] == "ERROR"
        assert batch[1]["level"] == "ERROR"
        assert len(batch) == 7


class TestDualQueueSizeAndEmpty:
    """AC6/AC7: Size, empty, full checks."""

    def test_qsize_reflects_both_queues(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "a"})
        dq.try_enqueue({"level": "ERROR", "msg": "b"})
        assert dq.qsize() == 2

    def test_is_empty_both_queues(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        assert dq.is_empty() is True
        dq.try_enqueue({"level": "INFO", "msg": "a"})
        assert dq.is_empty() is False

    def test_is_full_main_queue(self) -> None:
        dq = DualQueue(
            main_capacity=1,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "a"})
        assert dq.is_full() is True

    def test_capacity_returns_main_capacity(self) -> None:
        dq = DualQueue(
            main_capacity=500,
            protected_capacity=50,
            protected_levels=frozenset({"ERROR"}),
        )
        assert dq.capacity == 500


class TestDualQueueGrowCapacity:
    """Grow capacity applies to main queue only."""

    def test_grow_capacity_main_only(self) -> None:
        dq = DualQueue(
            main_capacity=10,
            protected_capacity=5,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.grow_capacity(20)
        assert dq.capacity == 20
        # Protected capacity unchanged
        assert dq._protected.capacity == 5

    def test_grow_capacity_ignores_shrink(self) -> None:
        dq = DualQueue(
            main_capacity=10,
            protected_capacity=5,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.grow_capacity(5)
        assert dq.capacity == 10


class TestDualQueueConcurrency:
    """AC8: Concurrent enqueue routing correctness."""

    def test_concurrent_enqueue_routing_correctness(self) -> None:
        dq = DualQueue(
            main_capacity=10000,
            protected_capacity=1000,
            protected_levels=frozenset({"ERROR"}),
        )

        def enqueue_mixed(n: int) -> None:
            for i in range(n):
                level = "ERROR" if i % 10 == 0 else "INFO"
                dq.try_enqueue({"level": level, "msg": str(i)})

        threads = [
            threading.Thread(target=enqueue_mixed, args=(1000,)) for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Drain all and verify: no ERROR in main, no INFO in protected
        # Each thread enqueues 100 ERROR events (i % 10 == 0), 900 INFO events
        # 4 threads: 400 ERROR, 3600 INFO
        batch: list[dict] = []
        dq.drain_into(batch)

        error_count = sum(1 for e in batch if e["level"] == "ERROR")
        info_count = sum(1 for e in batch if e["level"] == "INFO")
        assert error_count == 400
        assert info_count == 3600
        assert len(batch) == 4000


class TestDualQueueValidation:
    """Input validation."""

    def test_invalid_main_capacity(self) -> None:
        with pytest.raises(ValueError, match="capacity must be > 0"):
            DualQueue(
                main_capacity=0,
                protected_capacity=10,
                protected_levels=frozenset({"ERROR"}),
            )

    def test_invalid_protected_capacity(self) -> None:
        with pytest.raises(ValueError, match="capacity must be > 0"):
            DualQueue(
                main_capacity=10,
                protected_capacity=0,
                protected_levels=frozenset({"ERROR"}),
            )
