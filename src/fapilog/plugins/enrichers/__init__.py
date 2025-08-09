from __future__ import annotations

from typing import Iterable, List

from ...core.processing import process_in_parallel


class BaseEnricher:
    """Base interface for enrichers with async API."""

    async def enrich(self, event: dict) -> dict:
        return event


async def enrich_parallel(
    event: dict, enrichers: Iterable[BaseEnricher], *, concurrency: int = 5
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
        return await e.enrich(dict(event))

    results = await process_in_parallel(enricher_list, run_enricher, limit=concurrency)
    # Shallow merge results into a new dict
    merged: dict = dict(event)
    for res in results:
        if isinstance(res, BaseException):
            # Skip failed enricher to preserve pipeline resilience
            continue
        merged.update(res)
    return merged
