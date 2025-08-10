import asyncio
from typing import Any, Coroutine

import pytest

from fapilog.core.concurrency import AsyncBoundedExecutor, BackpressurePolicy
from fapilog.core.errors import BackpressureError


@pytest.mark.asyncio
async def test_bounded_executor_limits_concurrency_and_preserves_order():
    concurrent = 0
    peak = 0
    lock = asyncio.Lock()

    async def worker(i: int) -> int:
        nonlocal concurrent, peak
        async with lock:
            concurrent += 1
            peak = max(peak, concurrent)
        await asyncio.sleep(0.05)
        async with lock:
            concurrent -= 1
        return i * 3

    typed_executor: AsyncBoundedExecutor[int] = AsyncBoundedExecutor(
        max_concurrency=3, max_queue_size=10
    )
    async with typed_executor:
        futures: list[asyncio.Future[int]] = []
        for i in range(8):
            # Bind i by default to avoid late binding; expose as factory
            async def make(i=i) -> int:
                return await worker(i)

            def factory(make=make) -> Coroutine[Any, Any, int]:
                return make()

            futures.append(await typed_executor.submit(factory))
        results = await asyncio.gather(*futures)

    assert results == [i * 3 for i in range(8)]
    assert peak <= 3


@pytest.mark.asyncio
async def test_backpressure_reject_policy_raises_when_full():
    async def worker() -> int:
        await asyncio.sleep(0.2)
        return 1

    typed_executor: AsyncBoundedExecutor[int] = AsyncBoundedExecutor(
        max_concurrency=1,
        max_queue_size=1,
        backpressure_policy=BackpressurePolicy.REJECT,
    )
    async with typed_executor:
        # One running, one queued
        fut1 = await typed_executor.submit(worker)
        fut2 = await typed_executor.submit(worker)
        with pytest.raises(BackpressureError):
            await typed_executor.submit(worker)
        # Finish
        _ = await asyncio.gather(fut1, fut2)


@pytest.mark.asyncio
async def test_backpressure_wait_policy_times_out():
    async def worker() -> int:
        await asyncio.sleep(0.2)
        return 2

    typed_executor: AsyncBoundedExecutor[int] = AsyncBoundedExecutor(
        max_concurrency=1,
        max_queue_size=1,
        backpressure_policy=BackpressurePolicy.WAIT,
    )
    async with typed_executor:
        fut1 = await typed_executor.submit(worker)
        fut2 = await typed_executor.submit(worker)
        with pytest.raises(BackpressureError):
            await typed_executor.submit(worker, timeout=0.01)
        _ = await asyncio.gather(fut1, fut2)
