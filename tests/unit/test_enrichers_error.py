import pytest

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.enrichers import BaseEnricher, enrich_parallel


class GoodEnricher(BaseEnricher):
    async def enrich(self, event: dict) -> dict:  # noqa: D401
        return {**event, "ok": True}


class BadEnricher(BaseEnricher):
    async def enrich(self, event: dict) -> dict:  # noqa: D401
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_enrich_parallel_skips_failed_and_records_metric():
    base = {"a": 1}
    metrics = MetricsCollector(enabled=True)
    out = await enrich_parallel(
        base, [GoodEnricher(), BadEnricher()], concurrency=2, metrics=metrics
    )
    # Good enricher applied; bad skipped
    assert out == {"a": 1, "ok": True}
    snap = await metrics.snapshot()
    # One success event recorded
    assert snap.events_processed >= 1
