import asyncio

import pytest

from fapilog.core.concurrency import (
    AsyncBoundedExecutor,
    BackpressurePolicy,
    LockFreeRingBuffer,
    NonBlockingRingQueue,
)
from fapilog.core.errors import BackpressureError, TimeoutError


@pytest.mark.asyncio
async def test_bounded_executor_wait_timeout():
    ex: AsyncBoundedExecutor[int] = AsyncBoundedExecutor(
        max_concurrency=1, max_queue_size=1, backpressure_policy=BackpressurePolicy.WAIT
    )
    async with ex:

        async def w() -> int:
            await asyncio.sleep(0.05)
            return 1

        # One running, one queued
        _ = await ex.submit(w)
        _ = await ex.submit(w)
        # Third should time out waiting for capacity
        with pytest.raises(BackpressureError):
            await ex.submit(w, timeout=0.01)


@pytest.mark.asyncio
async def test_lock_free_ring_buffer_timeouts():
    buf: LockFreeRingBuffer[int] = LockFreeRingBuffer(capacity=1)
    await buf.await_push(1)
    with pytest.raises(TimeoutError):
        await buf.await_push(2, timeout=0.01)
    ok, v = buf.try_pop()
    assert ok and v == 1
    with pytest.raises(TimeoutError):
        await buf.await_pop(timeout=0.01)


@pytest.mark.asyncio
async def test_non_blocking_ring_queue():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert (await q.await_enqueue(1)) is None
    with pytest.raises(TimeoutError):
        await q.await_enqueue(2, timeout=0.01)
    ok, v = q.try_dequeue()
    assert ok and v == 1
