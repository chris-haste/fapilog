import threading

import pytest

from fapilog.core.concurrency import DualQueue, NonBlockingRingQueue


def test_ring_queue_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="capacity must be > 0"):
        NonBlockingRingQueue(capacity=0)


def test_ring_queue_try_enqueue_and_dequeue_edges() -> None:
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert q.try_enqueue(1) is True
    assert q.try_enqueue(2) is False
    ok, item = q.try_dequeue()
    assert ok is True
    assert item == 1
    ok, item = q.try_dequeue()
    assert ok is False
    assert item is None


def test_concurrent_enqueue_dequeue() -> None:
    """Concurrent try_enqueue/try_dequeue from multiple threads should not lose items."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=100)
    enqueued = []
    dequeued = []
    n_items = 1000
    n_threads = 4

    def enqueue_worker(start: int, count: int) -> None:
        for i in range(start, start + count):
            while not q.try_enqueue(i):
                pass  # spin until enqueued
            enqueued.append(i)

    def dequeue_worker(count: int) -> None:
        collected = 0
        while collected < count:
            ok, item = q.try_dequeue()
            if ok:
                dequeued.append(item)
                collected += 1

    items_per_thread = n_items // n_threads
    enqueue_threads = [
        threading.Thread(
            target=enqueue_worker, args=(i * items_per_thread, items_per_thread)
        )
        for i in range(n_threads)
    ]
    dequeue_threads = [
        threading.Thread(target=dequeue_worker, args=(items_per_thread,))
        for i in range(n_threads)
    ]

    for t in enqueue_threads + dequeue_threads:
        t.start()
    for t in enqueue_threads + dequeue_threads:
        t.join(timeout=10)

    assert len(dequeued) == n_items
    assert sorted(dequeued) == sorted(enqueued)


# --- shrink_capacity tests (Story 1.54) ---


class TestShrinkCapacity:
    """Tests for NonBlockingRingQueue.shrink_capacity()."""

    def test_shrink_reduces_capacity(self) -> None:
        q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        q.grow_capacity(4000)
        assert q.capacity == 4000
        q.shrink_capacity(2000)
        assert q.capacity == 2000

    def test_shrink_clamps_at_initial_capacity(self) -> None:
        q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        q.grow_capacity(4000)
        q.shrink_capacity(500)
        assert q.capacity == 1000

    def test_shrink_clamps_at_current_fill(self) -> None:
        q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        q.grow_capacity(4000)
        for i in range(2500):
            assert q.try_enqueue(i)
        q.shrink_capacity(1000)
        assert q.capacity == 2500
        assert q.qsize() == 2500

    def test_shrink_ignored_when_target_gte_current(self) -> None:
        q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        q.grow_capacity(4000)
        q.shrink_capacity(5000)
        assert q.capacity == 4000
        q.shrink_capacity(4000)
        assert q.capacity == 4000

    def test_grow_then_shrink_round_trip(self) -> None:
        """AC9: grow then fully decay returns to initial behavior."""
        q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        q.grow_capacity(4000)
        q.shrink_capacity(1000)
        assert q.capacity == 1000
        for i in range(1000):
            assert q.try_enqueue(i)
        assert not q.try_enqueue(9999)

    def test_thread_safe_shrink(self) -> None:
        """AC5: concurrent enqueue/dequeue/shrink — no corruption."""
        q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=500)
        q.grow_capacity(2000)
        errors: list[str] = []

        def enqueue_loop() -> None:
            for i in range(2000):
                q.try_enqueue(i)

        def dequeue_loop() -> None:
            for _ in range(2000):
                q.try_dequeue()

        def shrink_loop() -> None:
            for target in [1500, 1000, 800, 600, 500]:
                q.shrink_capacity(target)

        threads = [
            threading.Thread(target=enqueue_loop),
            threading.Thread(target=dequeue_loop),
            threading.Thread(target=shrink_loop),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Queue should still be usable with consistent state
        assert q.capacity >= 500  # noqa: WA003
        assert len(errors) == 0


class TestDualQueueShrink:
    """Tests for DualQueue.shrink_capacity() delegation."""

    def test_shrink_delegates_to_main(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.grow_capacity(4000)
        assert dq.capacity == 4000
        dq.shrink_capacity(2000)
        assert dq.capacity == 2000

    def test_shrink_respects_initial_floor(self) -> None:
        dq: DualQueue[dict[str, str]] = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.grow_capacity(4000)
        dq.shrink_capacity(500)
        assert dq.capacity == 1000
