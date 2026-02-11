"""Unit tests for PriorityAwareQueue.grow_capacity() — Story 1.48."""

from __future__ import annotations

import asyncio

import pytest

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

    @pytest.mark.asyncio
    async def test_grow_wakes_blocked_enqueuers(self) -> None:
        queue: PriorityAwareQueue[dict[str, str]] = PriorityAwareQueue(
            capacity=1, protected_levels={"ERROR"}
        )
        queue.try_enqueue({"level": "INFO", "msg": "a"})
        assert queue.is_full()

        enqueued = asyncio.Event()

        async def blocked_enqueuer() -> None:
            await queue.await_enqueue({"level": "INFO", "msg": "b"})
            enqueued.set()

        task = asyncio.create_task(blocked_enqueuer())

        # Let the enqueuer block
        await asyncio.sleep(0.05)
        assert not enqueued.is_set()

        # Grow capacity — should wake the blocked enqueuer
        queue.grow_capacity(2)

        await asyncio.wait_for(enqueued.wait(), timeout=1.0)
        assert enqueued.is_set()
        assert queue.qsize() == 2

        await task
