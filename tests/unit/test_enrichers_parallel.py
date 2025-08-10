import pytest

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.enrichers import BaseEnricher, enrich_parallel


class AddFieldEnricher(BaseEnricher):
    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value

    async def enrich(self, event: dict) -> dict:
        event[self.key] = self.value
        return event


@pytest.mark.asyncio
async def test_enrich_parallel_merges_results():
    base = {"a": 1}
    enrichers = [AddFieldEnricher("b", "x"), AddFieldEnricher("c", "y")]
    metrics = MetricsCollector(enabled=True)
    out = await enrich_parallel(base, enrichers, concurrency=2, metrics=metrics)
    assert out == {"a": 1, "b": "x", "c": "y"}
    snap = await metrics.snapshot()
    assert snap.events_processed == 2
    # Ensure original not mutated
    assert base == {"a": 1}
