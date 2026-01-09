import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.errors import TimeoutError


@pytest.mark.asyncio
async def test_non_blocking_ring_queue():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert (await q.await_enqueue(1)) is None
    with pytest.raises(TimeoutError):
        await q.await_enqueue(2, timeout=0.01)
    ok, v = q.try_dequeue()
    assert ok and v == 1


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


@pytest.mark.asyncio
async def test_ring_queue_dequeue_timeout() -> None:
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    with pytest.raises(TimeoutError):
        await q.await_dequeue(timeout=0.01)
