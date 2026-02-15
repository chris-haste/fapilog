import threading

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue


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


def test_ring_queue_has_lock() -> None:
    """Queue should have a threading.Lock for thread safety."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert hasattr(q, "_lock")
    assert isinstance(q._lock, type(threading.Lock()))


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
