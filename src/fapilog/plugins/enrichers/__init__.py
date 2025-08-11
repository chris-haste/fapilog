from __future__ import annotations

from typing import Iterable

from ...core.processing import process_in_parallel
from ...metrics.metrics import MetricsCollector, plugin_timer


class BaseEnricher:
    """Base interface for enrichers with async API."""

    async def enrich(self, event: dict) -> dict:
        return event


async def enrich_parallel(
    event: dict,
    enrichers: Iterable[BaseEnricher],
    *,
    concurrency: int = 5,
    metrics: MetricsCollector | None = None,
) -> dict:
    """
    Run multiple enrichers in parallel on the same event with controlled
    concurrency.

    Each enricher receives and returns a mapping. Results are merged
    shallowly in order.
    """
    enricher_list: list[BaseEnricher] = list(enrichers)

    async def run_enricher(e: BaseEnricher) -> dict:
        # pass a shallow copy to preserve isolation
        async with plugin_timer(metrics, e.__class__.__name__):
            result = await e.enrich(dict(event))
        return result

    results = await process_in_parallel(
        enricher_list, run_enricher, limit=concurrency, return_exceptions=True
    )
    # Shallow merge results into a new dict
    merged: dict = dict(event)
    for res in results:
        if isinstance(res, BaseException):
            # Skip failed enricher to preserve pipeline resilience
            if metrics is not None and metrics.is_enabled:
                plugin_label = getattr(type(res), "__name__", "enricher_error")
                await metrics.record_plugin_error(plugin_name=plugin_label)
            continue
        merged.update(res)
        if metrics is not None:
            await metrics.record_event_processed()
    return merged
