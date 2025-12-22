from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ...core.processing import process_in_parallel
from ...metrics.metrics import MetricsCollector, plugin_timer


@runtime_checkable
class BaseEnricher(Protocol):
    """Authoring contract for enrichers that augment events.

    Enrichers receive an event mapping and return a mapping of additional fields
    to be shallow-merged into the event. Implementations must be async and must
    not block the event loop. Failures should be contained; returning an empty
    mapping is acceptable on error.
    """

    async def start(self) -> None:  # Optional lifecycle hook
        """Initialize resources for the enricher (optional)."""

    async def stop(self) -> None:  # Optional lifecycle hook
        """Release resources for the enricher (optional)."""

    async def enrich(self, event: dict) -> dict:
        """Return additional fields computed from the input event.

        Implementations should avoid mutating the input mapping and return only
        the new fields to add. Must not raise upstream.
        """


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
            # Emit diagnostics when enabled
            try:
                from ...core import diagnostics as _diag

                _diag.warn(
                    "enricher",
                    "enrichment error",
                    error_type=type(res).__name__,
                    _rate_limit_key="enrich",
                )
            except Exception:
                pass
            continue
        merged.update(res)
        if metrics is not None:
            await metrics.record_event_processed()
    return merged
