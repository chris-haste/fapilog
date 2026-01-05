from __future__ import annotations

import random
from typing import Iterable, Protocol, runtime_checkable

from ...core import diagnostics
from ...metrics.metrics import MetricsCollector, plugin_timer
from ..loader import register_builtin
from .level import LevelFilter
from .rate_limit import RateLimitFilter
from .sampling import SamplingFilter


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

        if result is None:
            if metrics is not None:
                await metrics.record_events_filtered(1)
            return None
        current = result
    return current


# Register built-ins with legacy aliases
register_builtin("fapilog.filters", "level", LevelFilter)
register_builtin("fapilog.filters", "sampling", SamplingFilter)
register_builtin(
    "fapilog.filters",
    "rate_limit",
    RateLimitFilter,
    aliases=["rate-limit"],
)

# Touch random to quiet linters about unused imports (used in sampling filter)
_ = random.random

__all__ = [
    "BaseFilter",
    "filter_in_order",
    "LevelFilter",
    "SamplingFilter",
    "RateLimitFilter",
]
