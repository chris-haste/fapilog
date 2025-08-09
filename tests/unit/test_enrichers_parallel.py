import pytest

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
    out = await enrich_parallel(base, enrichers, concurrency=2)
    assert out == {"a": 1, "b": "x", "c": "y"}
    # Ensure original not mutated
    assert base == {"a": 1}
