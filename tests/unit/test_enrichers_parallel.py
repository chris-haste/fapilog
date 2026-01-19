from typing import Any

import pytest

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.enrichers import BaseEnricher, _deep_merge, enrich_parallel


class AddFieldEnricher(BaseEnricher):
    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value

    async def enrich(self, event: dict) -> dict:
        event[self.key] = self.value
        return event


class NestedEnricher(BaseEnricher):
    """Enricher that returns nested structure targeting semantic groups."""

    name = "nested"

    def __init__(self, target: str, data: dict[str, Any]) -> None:
        self.target = target
        self.data = data

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        return {self.target: self.data}


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


class TestDeepMerge:
    """Tests for _deep_merge helper function."""

    def test_merges_flat_dicts(self) -> None:
        base = {"a": 1, "b": 2}
        updates = {"c": 3}
        result = _deep_merge(base, updates)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_deep_merges_nested_dicts(self) -> None:
        base = {"context": {"correlation_id": "abc"}, "diagnostics": {}}
        updates = {"context": {"request_id": "req-123"}}
        result = _deep_merge(base, updates)
        assert result["context"]["correlation_id"] == "abc"
        assert result["context"]["request_id"] == "req-123"

    def test_updates_overwrite_non_dict_values(self) -> None:
        base = {"level": "INFO", "message": "old"}
        updates = {"message": "new"}
        result = _deep_merge(base, updates)
        assert result["message"] == "new"
        assert result["level"] == "INFO"

    def test_does_not_mutate_base(self) -> None:
        base = {"context": {"a": 1}}
        updates = {"context": {"b": 2}}
        _deep_merge(base, updates)
        assert base == {"context": {"a": 1}}

    def test_handles_empty_base(self) -> None:
        result = _deep_merge({}, {"diagnostics": {"host": "server1"}})
        assert result == {"diagnostics": {"host": "server1"}}

    def test_handles_empty_updates(self) -> None:
        base = {"context": {"id": "123"}}
        result = _deep_merge(base, {})
        assert result == {"context": {"id": "123"}}

    def test_deep_merge_multiple_levels(self) -> None:
        base = {"a": {"b": {"c": 1}}}
        updates = {"a": {"b": {"d": 2}}}
        result = _deep_merge(base, updates)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}


@pytest.mark.asyncio
async def test_enrich_parallel_deep_merges_nested_results():
    """enrich_parallel deep-merges results into semantic groups."""
    event = {
        "timestamp": "2024-01-15T10:00:00.000Z",
        "level": "INFO",
        "message": "test",
        "context": {"correlation_id": "corr-123"},
        "diagnostics": {},
        "data": {},
    }
    enrichers = [
        NestedEnricher("diagnostics", {"host": "server1", "pid": 12345}),
        NestedEnricher("context", {"request_id": "req-456"}),
    ]
    result = await enrich_parallel(event, enrichers)

    # Original context preserved and enriched
    assert result["context"]["correlation_id"] == "corr-123"
    assert result["context"]["request_id"] == "req-456"
    # Diagnostics merged
    assert result["diagnostics"]["host"] == "server1"
    assert result["diagnostics"]["pid"] == 12345


@pytest.mark.asyncio
async def test_enrich_parallel_deep_merge_combines_multiple_enrichers():
    """Multiple enrichers targeting same group have fields combined."""
    event = {"diagnostics": {}}
    enrichers = [
        NestedEnricher("diagnostics", {"host": "server1"}),
        NestedEnricher("diagnostics", {"pid": 12345}),
    ]
    result = await enrich_parallel(event, enrichers)

    assert result["diagnostics"]["host"] == "server1"
    assert result["diagnostics"]["pid"] == 12345


@pytest.mark.asyncio
async def test_enrich_parallel_deep_merge_handles_empty_dicts():
    """Deep-merge works when starting with empty semantic groups."""
    event = {"context": {}, "diagnostics": {}, "data": {}}
    enrichers = [
        NestedEnricher("context", {"trace_id": "trace-abc"}),
    ]
    result = await enrich_parallel(event, enrichers)

    assert result["context"]["trace_id"] == "trace-abc"
    assert result["diagnostics"] == {}
    assert result["data"] == {}
