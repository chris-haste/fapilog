import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.errors import BackpressureError
from fapilog.core.resources import AsyncResourcePool


@pytest.mark.asyncio
async def test_non_blocking_ring_queue_basic():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=2)
    assert q.is_empty()
    assert not q.is_full()

    assert q.try_enqueue(1)
    ok, v = q.try_dequeue()
    assert ok and v == 1

    # Await variants
    await q.await_enqueue(10)
    val = await q.await_dequeue()
    assert val == 10


@pytest.mark.asyncio
async def test_non_blocking_ring_queue_waits_then_times_out():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert q.try_enqueue(1)
    from fapilog.core.errors import TimeoutError

    with pytest.raises(TimeoutError):
        await q.await_enqueue(2, timeout=0.01)


@pytest.mark.asyncio
async def test_resource_pool_close_alias_and_nowait_backpressure():
    created: list[int] = []

    async def create_item() -> int:
        item = len(created) + 1
        created.append(item)
        return item

    pool = AsyncResourcePool[int](
        name="nb-test",
        create_resource=create_item,
        close_resource=None,
        max_size=1,
        acquire_timeout_seconds=0.05,
    )

    # Acquire the only resource
    cm = pool.acquire()
    await cm.__aenter__()

    with pytest.raises(BackpressureError):
        await pool.acquire_nowait()

    await pool.close()
