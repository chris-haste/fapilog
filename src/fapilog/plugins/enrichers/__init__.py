from __future__ import annotations

from typing import Any, Iterable, Protocol, runtime_checkable

from ...core.processing import process_in_parallel
from ...metrics.metrics import MetricsCollector, plugin_timer
from ..loader import register_builtin
from .context_vars import ContextVarsEnricher
from .kubernetes import KubernetesEnricher
from .runtime_info import RuntimeInfoEnricher


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge updates into base dict.

    For nested dicts (context, diagnostics, data), merge contents.
    For other keys, updates overwrite base.

    Returns a new dict; does not mutate base.
    """
    result: dict[str, Any] = dict(base)
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@runtime_checkable
class BaseEnricher(Protocol):
    """Authoring contract for enrichers that augment events (v1.1 schema).

    Enrichers receive an event mapping and return a mapping targeting semantic
    groups. Results are deep-merged into the event, supporting nested structures.

    **Return Format (v1.1):**
    Enrichers should return dicts targeting semantic groups:
    - `{"context": {...}}` - for request/trace identifiers
    - `{"diagnostics": {...}}` - for runtime/operational data
    - `{"data": {...}}` - for user-provided structured data

    Example:
        ```python
        async def enrich(self, event: dict) -> dict:
            return {"diagnostics": {"host": "server1", "pid": 12345}}
        ```

    Deep-merge behavior:
    - Nested dicts (context, diagnostics, data) have their contents merged
    - Non-dict values are overwritten by updates
    - Original event data is preserved unless explicitly overwritten

    Implementations must be async and must not block the event loop.
    Failures should be contained; returning an empty mapping is acceptable on error.

    Attributes:
        name: Unique identifier for this enricher type (e.g., "runtime_info").
    """

    name: str  # Plugin identifier for discovery and configuration

    async def start(self) -> None:  # Optional lifecycle hook
        """Initialize resources for the enricher (optional)."""

    async def stop(self) -> None:  # Optional lifecycle hook
        """Release resources for the enricher (optional)."""

    async def enrich(self, event: dict) -> dict:
        """Return fields targeting semantic groups to be deep-merged into the event.

        Implementations should return dicts targeting semantic groups (context,
        diagnostics, or data). The result is deep-merged into the event.

        Implementations should avoid mutating the input mapping. Must not raise.
        """

    async def health_check(self) -> bool:  # pragma: no cover - optional
        """Return True if the enricher is healthy. Default: assume healthy."""
        return True


async def enrich_parallel(
    event: dict,
    enrichers: Iterable[BaseEnricher],
    *,
    concurrency: int = 5,
    metrics: MetricsCollector | None = None,
) -> dict:
    """Run multiple enrichers in parallel on the same event with controlled concurrency.

    Each enricher receives and returns a mapping targeting semantic groups.
    Results are deep-merged in order, supporting nested dict structures like
    context, diagnostics, and data.

    Args:
        event: The event dict to enrich (not mutated).
        enrichers: Iterable of enrichers to run in parallel.
        concurrency: Maximum concurrent enrichers (default 5).
        metrics: Optional metrics collector for instrumentation.

    Returns:
        A new dict with all enricher results deep-merged into the event.
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
    # Deep-merge results into a new dict to support nested semantic groups
    merged: dict[str, Any] = dict(event)
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
        merged = _deep_merge(merged, res)
        if metrics is not None:
            await metrics.record_event_processed()
    return merged


# Register built-ins with alias support (hyphen/underscore)
register_builtin(
    "fapilog.enrichers",
    "runtime_info",
    RuntimeInfoEnricher,
    aliases=["runtime-info", "runtime-info-enricher"],
)
register_builtin(
    "fapilog.enrichers",
    "context_vars",
    ContextVarsEnricher,
    aliases=["context-vars", "context-vars-enricher"],
)
register_builtin(
    "fapilog.enrichers",
    "kubernetes",
    KubernetesEnricher,
    aliases=["k8s", "k8s-enricher"],
)

__all__ = [
    "BaseEnricher",
    "_deep_merge",
    "enrich_parallel",
    "RuntimeInfoEnricher",
    "ContextVarsEnricher",
    "KubernetesEnricher",
]
