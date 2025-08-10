import asyncio

import pytest

from fapilog.core.concurrency import LockFreeRingBuffer


@pytest.mark.asyncio
async def test_ring_buffer_push_pop_basic():
    buf: LockFreeRingBuffer[int] = LockFreeRingBuffer(capacity=2)
    assert buf.is_empty()
    assert not buf.is_full()

    assert buf.try_push(1)
    assert not buf.is_empty()
    ok, v = buf.try_pop()
    assert ok and v == 1
    assert buf.is_empty()


@pytest.mark.asyncio
async def test_ring_buffer_capacity_and_wrap():
    buf: LockFreeRingBuffer[int] = LockFreeRingBuffer(capacity=2)
    assert buf.try_push(1)
    assert buf.try_push(2)
    assert not buf.try_push(3)  # full

    ok, v1 = buf.try_pop()
    ok2, v2 = buf.try_pop()
    assert ok and ok2 and v1 == 1 and v2 == 2
    assert buf.is_empty()

    # Wrap-around behavior
    assert buf.try_push(3)
    ok, v3 = buf.try_pop()
    assert ok and v3 == 3


@pytest.mark.asyncio
async def test_ring_buffer_async_await_helpers():
    buf: LockFreeRingBuffer[int] = LockFreeRingBuffer(capacity=1)

    async def producer():
        # First push fills, second awaits until consumer pops
        await buf.await_push(10)
        await buf.await_push(20)

    async def consumer():
        await asyncio.sleep(0)  # allow producer to proceed
        v1 = await buf.await_pop()
        assert v1 == 10
        v2 = await buf.await_pop()
        assert v2 == 20

    await asyncio.gather(producer(), consumer())


def test_invalid_capacity():
    with pytest.raises(ValueError):
        LockFreeRingBuffer(capacity=0)
