"""
Plugin health check models and utilities.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class PluginHealth:
    name: str
    plugin_type: str
    status: HealthStatus = HealthStatus.UNKNOWN
    healthy: bool = True
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_error: str | None = None
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedHealth:
    overall_status: HealthStatus
    timestamp: datetime
    plugins: list[PluginHealth]
    healthy_count: int
    unhealthy_count: int
    degraded_count: int

    @property
    def all_healthy(self) -> bool:
        return self.unhealthy_count == 0 and self.degraded_count == 0


@runtime_checkable
class DetailedHealthCheckable(Protocol):
    async def health_check(self) -> bool: ...

    async def health_details(self) -> PluginHealth: ...


async def check_plugin_health(
    plugin: Any, plugin_type: str, timeout_seconds: float = 5.0
) -> PluginHealth:
    """Run a health check on a plugin with timeout and result capture."""

    name = getattr(plugin, "name", type(plugin).__name__)
    health = PluginHealth(name=name, plugin_type=plugin_type)

    if not hasattr(plugin, "health_check"):
        health.status = HealthStatus.UNKNOWN
        return health

    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(plugin.health_check(), timeout=timeout_seconds)
        health.latency_ms = (time.perf_counter() - start) * 1000
        health.healthy = bool(result)
        health.status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
    except asyncio.TimeoutError:
        health.healthy = False
        health.status = HealthStatus.UNHEALTHY
        health.last_error = f"health check timed out after {timeout_seconds}s"
    except Exception as exc:
        health.healthy = False
        health.status = HealthStatus.UNHEALTHY
        health.last_error = str(exc)
    return health


async def aggregate_plugin_health(
    enrichers: list[Any],
    redactors: list[Any],
    sinks: list[Any],
    processors: list[Any] | None = None,
    filters: list[Any] | None = None,
    *,
    timeout_seconds: float = 5.0,
) -> AggregatedHealth:
    """Check health of all plugins and return aggregated status.

    Args:
        enrichers: List of enricher plugin instances.
        redactors: List of redactor plugin instances.
        sinks: List of sink plugin instances.
        timeout_seconds: Timeout for each individual health check.

    Returns:
        AggregatedHealth with overall status and per-plugin details.
    """
    plugin_healths: list[PluginHealth] = []

    for f in filters or []:
        plugin_healths.append(await check_plugin_health(f, "filter", timeout_seconds))
    for p in processors or []:
        plugin_healths.append(
            await check_plugin_health(p, "processor", timeout_seconds)
        )
    for e in enrichers:
        plugin_healths.append(await check_plugin_health(e, "enricher", timeout_seconds))
    for r in redactors:
        plugin_healths.append(await check_plugin_health(r, "redactor", timeout_seconds))
    for s in sinks:
        plugin_healths.append(await check_plugin_health(s, "sink", timeout_seconds))

    healthy = sum(1 for p in plugin_healths if p.healthy)
    unhealthy = sum(
        1
        for p in plugin_healths
        if (not p.healthy and p.status == HealthStatus.UNHEALTHY)
    )
    degraded = sum(1 for p in plugin_healths if p.status == HealthStatus.DEGRADED)

    overall = HealthStatus.HEALTHY
    if unhealthy > 0:
        overall = HealthStatus.UNHEALTHY
    elif degraded > 0:
        overall = HealthStatus.DEGRADED

    return AggregatedHealth(
        overall_status=overall,
        timestamp=datetime.now(timezone.utc),
        plugins=plugin_healths,
        healthy_count=healthy,
        unhealthy_count=unhealthy,
        degraded_count=degraded,
    )


# Mark for static analyzers
_VULTURE_USED: tuple[Any, ...] = (
    HealthStatus.HEALTHY,
    HealthStatus.DEGRADED,
    HealthStatus.UNHEALTHY,
    HealthStatus.UNKNOWN,
    PluginHealth,
    AggregatedHealth,
    DetailedHealthCheckable,
    check_plugin_health,
    aggregate_plugin_health,
    DetailedHealthCheckable.health_details,
)


def _vulture_touch() -> None:  # pragma: no cover - marker for static analyzers
    """Touch dataclasses/fields so vulture sees them as used."""
    sample = PluginHealth(name="sample", plugin_type="sink")
    agg = AggregatedHealth(
        overall_status=HealthStatus.UNKNOWN,
        timestamp=datetime.now(timezone.utc),
        plugins=[sample],
        healthy_count=0,
        unhealthy_count=0,
        degraded_count=0,
    )
    _ = (
        sample.status,
        sample.healthy,
        sample.last_check,
        agg.all_healthy,
        agg.overall_status,
        agg.plugins,
        agg.healthy_count,
        agg.unhealthy_count,
        agg.degraded_count,
    )


_VULTURE_USED += (_vulture_touch,)
