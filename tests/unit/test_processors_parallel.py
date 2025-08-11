import pytest

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.processors import BaseProcessor, process_parallel


class UpperProcessor(BaseProcessor):
    async def process(self, view: memoryview) -> memoryview:  # noqa: D401
        data = view.tobytes().upper()
        return memoryview(data)


class FailProcessor(BaseProcessor):
    async def process(self, view: memoryview) -> memoryview:  # noqa: D401
        raise ValueError("fail")


@pytest.mark.asyncio
async def test_process_parallel_success_and_metrics():
    metrics = MetricsCollector(enabled=True)
    views = [memoryview(b"a"), memoryview(b"b")]
    out = await process_parallel(views, [UpperProcessor()], metrics=metrics)
    assert [v.tobytes() for v in out] == [b"A", b"B"]
    snap = await metrics.snapshot()
    assert snap.events_processed == 2


@pytest.mark.asyncio
async def test_process_parallel_ignores_failed_lists():
    views = [memoryview(b"x")]
    # One fails, one succeeds; result should come from the last successful list
    out = await process_parallel(views, [UpperProcessor(), FailProcessor()])
    # When last fails, function returns previous successful views list
    assert [v.tobytes() for v in out] == [b"X"]
