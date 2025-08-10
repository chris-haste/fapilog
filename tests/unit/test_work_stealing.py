import asyncio
import time

import pytest

from fapilog.core.concurrency import (
    AsyncWorkStealingExecutor,
    BackpressurePolicy,
)
from fapilog.core.errors import BackpressureError


@pytest.mark.asyncio
async def test_work_stealing_preserves_results_and_is_faster_than_single():
    async def worker(i: int) -> int:
        # Odd tasks are heavier
        if i % 2 == 1:
            await asyncio.sleep(0.03)
        else:
            await asyncio.sleep(0.005)
        return i * 10

    async def run_with_concurrency(
        max_concurrency: int,
    ) -> tuple[list[int], float]:
        ex: AsyncWorkStealingExecutor[int] = AsyncWorkStealingExecutor(
            max_concurrency=max_concurrency,
            max_queue_size=64,
        )
        start = time.perf_counter()
        async with ex:
            futures: list[asyncio.Future[int]] = []
            for i in range(16):

                async def make(i=i) -> int:
                    return await worker(i)

                def factory(make=make):
                    return make()

                futures.append(await ex.submit(factory))
            results = await asyncio.gather(*futures)
        elapsed = time.perf_counter() - start
        return results, elapsed

    results_1, elapsed_1 = await run_with_concurrency(1)
    results_4, elapsed_4 = await run_with_concurrency(4)

    assert results_4 == [i * 10 for i in range(16)]
    # With concurrency 4, wall time should be significantly less than single
    # worker
    assert elapsed_4 < (elapsed_1 * 0.6)


@pytest.mark.asyncio
async def test_work_stealing_backpressure_rejects_when_full():
    async def worker() -> int:
        await asyncio.sleep(0.05)
        return 7

    ex: AsyncWorkStealingExecutor[int] = AsyncWorkStealingExecutor(
        max_concurrency=1,
        max_queue_size=1,
        backpressure_policy=BackpressurePolicy.REJECT,
    )
    async with ex:
        fut1 = await ex.submit(worker)
        fut2 = await ex.submit(worker)
        with pytest.raises(BackpressureError):
            await ex.submit(worker)
        _ = await asyncio.gather(fut1, fut2)


@pytest.mark.asyncio
async def test_work_stealing_wait_policy_times_out():
    async def worker() -> int:
        await asyncio.sleep(0.05)
        return 3

    ex: AsyncWorkStealingExecutor[int] = AsyncWorkStealingExecutor(
        max_concurrency=1,
        max_queue_size=1,
        backpressure_policy=BackpressurePolicy.WAIT,
    )
    async with ex:
        _ = await ex.submit(worker)
        _ = await ex.submit(worker)
        with pytest.raises(BackpressureError):
            await ex.submit(worker, timeout=0.01)
