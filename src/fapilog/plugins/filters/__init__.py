from __future__ import annotations

import random
from typing import Any, Iterable, Protocol, runtime_checkable

from ...core import diagnostics
from ...metrics.metrics import MetricsCollector, plugin_timer
from ..loader import register_builtin
from .adaptive_sampling import AdaptiveSamplingFilter
from .first_occurrence import FirstOccurrenceFilter
from .level import LevelFilter
from .rate_limit import RateLimitFilter
from .sampling import SamplingFilter
from .trace_sampling import TraceSamplingFilter


@runtime_checkable
class BaseFilter(Protocol):
    """Contract for filters that can drop or transform events before enrichment."""

    name: str

    async def start(self) -> None:
        """Initialize filter resources (optional)."""

    async def stop(self) -> None:
        """Release filter resources (optional)."""

    async def filter(self, event: dict) -> dict | None:
        """Return event to continue or None to drop."""

    async def health_check(self) -> bool:
        """Return True if healthy."""
        return True


async def filter_in_order(
    event: dict,
    filters: Iterable[BaseFilter],
    *,
    metrics: MetricsCollector | None = None,
) -> dict | None:
    """Apply filters sequentially; return None when any drops the event."""
    current = dict(event)
    for f in filters:
        name = getattr(f, "name", type(f).__name__)
        try:
            async with plugin_timer(metrics, name):
                result = await f.filter(dict(current))
        except Exception as exc:
            try:
                diagnostics.warn(
                    "filter",
                    "filter exception",
                    filter=name,
                    reason=str(exc),
                )
            except Exception:
                pass
            continue
        if metrics is not None:
            await _record_filter_metrics(metrics, f, name)

        if result is None:
            if metrics is not None:
                await metrics.record_events_filtered(1)
            return None
        current = result
    return current


async def _record_filter_metrics(
    metrics: MetricsCollector, filter_plugin: BaseFilter, name: str
) -> None:
    try:
        rate_val = getattr(filter_plugin, "current_sample_rate", None)
        rate = rate_val() if callable(rate_val) else rate_val
        if rate is not None:
            await metrics.record_sample_rate(name, float(rate))
    except Exception:
        pass
    try:
        tracked_keys_val = getattr(filter_plugin, "tracked_key_count", None)
        tracked = tracked_keys_val() if callable(tracked_keys_val) else tracked_keys_val
        if tracked is not None:
            await metrics.record_rate_limit_keys_tracked(int(tracked))
    except Exception:
        pass


# Register built-ins with legacy aliases
register_builtin("fapilog.filters", "level", LevelFilter)
register_builtin("fapilog.filters", "sampling", SamplingFilter)
register_builtin(
    "fapilog.filters",
    "rate_limit",
    RateLimitFilter,
    aliases=["rate-limit"],
)
register_builtin("fapilog.filters", "adaptive_sampling", AdaptiveSamplingFilter)
register_builtin("fapilog.filters", "trace_sampling", TraceSamplingFilter)
register_builtin(
    "fapilog.filters",
    "first_occurrence",
    FirstOccurrenceFilter,
)

# Touch random to quiet linters about unused imports (used in sampling filter)
_ = random.random

__all__ = [
    "BaseFilter",
    "filter_in_order",
    "LevelFilter",
    "SamplingFilter",
    "RateLimitFilter",
    "AdaptiveSamplingFilter",
    "TraceSamplingFilter",
    "FirstOccurrenceFilter",
]
