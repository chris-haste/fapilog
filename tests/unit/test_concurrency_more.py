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
