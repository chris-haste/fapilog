"""Unit tests for PriorityAwareQueue.grow_capacity() — Story 1.48."""

from __future__ import annotations

from fapilog.core.concurrency import PriorityAwareQueue


class TestGrowCapacity:
    """Tests for grow_capacity() method on PriorityAwareQueue."""

    def test_grow_increases_capacity(self) -> None:
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=100, protected_levels={"ERROR"}
        )
        assert queue.capacity == 100

        queue.grow_capacity(200)
        assert queue.capacity == 200

    def test_grow_only_no_shrink(self) -> None:
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=200, protected_levels={"ERROR"}
        )
        queue.grow_capacity(100)
        assert queue.capacity == 200  # Unchanged

    def test_grow_same_capacity_is_noop(self) -> None:
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=100, protected_levels={"ERROR"}
        )
        queue.grow_capacity(100)
        assert queue.capacity == 100

    def test_is_full_reflects_new_capacity(self) -> None:
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "INFO", "msg": "a"})
        assert queue.is_full()

        queue.grow_capacity(2)
        assert not queue.is_full()

    def test_enqueue_succeeds_after_growth(self) -> None:
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "INFO", "msg": "a"})
        assert queue.is_full()

        # Without growth, enqueue fails (unprotected event, no eviction)
        assert not queue.try_enqueue({"level": "INFO", "msg": "b"})

        queue.grow_capacity(2)
        assert queue.try_enqueue({"level": "INFO", "msg": "b"})
        assert queue.qsize() == 2

    def test_grow_allows_enqueue_after_full(self) -> None:
        """After growing capacity, previously-full queue accepts new items."""
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "INFO", "msg": "a"})
        assert queue.is_full()

        # try_enqueue fails when full
        assert not queue.try_enqueue({"level": "INFO", "msg": "b"})

        # Grow capacity
        queue.grow_capacity(2)

        # Now enqueue succeeds
        assert queue.try_enqueue({"level": "INFO", "msg": "b"})
        assert queue.qsize() == 2
