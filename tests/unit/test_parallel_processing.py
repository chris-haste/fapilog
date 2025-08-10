import asyncio

import pytest

from fapilog.core.processing import gather_with_limit, process_in_parallel
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.processors import BaseProcessor, process_parallel


@pytest.mark.asyncio
async def test_gather_with_limit_preserves_order_and_limits_concurrency():
    concurrent_peek = 0
    current = 0
    lock = asyncio.Lock()

    async def worker(i: int) -> int:
        nonlocal concurrent_peek, current
        async with lock:
            current += 1
            concurrent_peek = max(concurrent_peek, current)
        # simulate IO
        await asyncio.sleep(0.05)
        async with lock:
            current -= 1
        return i * 2

    factories = [lambda i=i: worker(i) for i in range(10)]
    results = await gather_with_limit(factories, limit=3)

    assert results == [i * 2 for i in range(10)]
    assert concurrent_peek <= 3


@pytest.mark.asyncio
async def test_process_in_parallel_with_worker_and_limit():
    async def worker(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    values = list(range(5))
    out = await process_in_parallel(values, worker, limit=2)
    assert out == [x + 1 for x in values]


@pytest.mark.asyncio
async def test_gather_with_limit_raises_on_bad_limit():
    async def foo() -> int:
        return 1

    with pytest.raises(ValueError):
        await gather_with_limit([lambda: foo()], limit=0)


class RaiseProcessor(BaseProcessor):
    async def process(  # type: ignore[override]
        self, view: memoryview
    ) -> memoryview:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_process_parallel_records_metrics_on_success_and_error():
    class Passthrough(BaseProcessor):
        async def process(  # type: ignore[override]
            self, view: memoryview
        ) -> memoryview:
            await asyncio.sleep(0.005)
            return view

    views = [memoryview(b"abc"), memoryview(b"def")]
    metrics = MetricsCollector(enabled=True)

    # Success path
    out = await process_parallel(
        views,
        [Passthrough()],
        concurrency=2,
        metrics=metrics,
    )
    assert [bytes(v) for v in out] == [b"abc", b"def"]
    snap = await metrics.snapshot()
    assert snap.events_processed == 2

    # Error path increments plugin_errors and gracefully degrades
    metrics_err = MetricsCollector(enabled=True)
    out2 = await process_parallel(
        views,
        [RaiseProcessor()],
        concurrency=2,
        metrics=metrics_err,
    )
    assert [bytes(v) for v in out2] == [b"abc", b"def"]
    snap_err = await metrics_err.snapshot()
    assert snap_err.plugin_errors == 1
