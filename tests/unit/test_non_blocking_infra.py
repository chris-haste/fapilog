import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.errors import BackpressureError
from fapilog.core.resources import AsyncResourcePool

pytestmark = pytest.mark.critical


@pytest.mark.asyncio
async def test_non_blocking_ring_queue_basic():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=2)
    assert q.is_empty()
    assert not q.is_full()

    assert q.try_enqueue(1)
    ok, v = q.try_dequeue()
    assert ok and v == 1


def test_non_blocking_ring_queue_full_and_empty():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert q.try_enqueue(1) is True
    assert q.is_full()
    assert q.try_enqueue(2) is False
    ok, v = q.try_dequeue()
    assert ok and v == 1
    assert q.is_empty()


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
