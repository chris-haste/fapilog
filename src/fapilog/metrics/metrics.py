"""
Async-first performance metrics collection for Fapilog v3.

Implements minimal Prometheus-compatible counters and histograms used by
parallel processing and plugin execution paths.

Design goals:
- Pure async/await, no blocking I/O
- Zero global state; instances are container-scoped
- Safe no-op behavior when metrics are disabled by settings
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Histogram


@dataclass
class PipelineMetrics:
    """Captured runtime metrics for quick assertions in tests."""

    events_processed: int = 0
    plugin_errors: int = 0


class MetricsCollector:
    """Container-scoped async metrics collector.

    If Prometheus client is unavailable or metrics are disabled, all methods
    are safe no-ops while still tracking basic in-memory counters for tests.
    """

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = bool(enabled)
        self._lock = asyncio.Lock()
        self._state = PipelineMetrics()

        # Lazily-initialized exporters to avoid global registration noise
        self._c_events: Any | None = None
        self._c_plugin_errors: Any | None = None
        self._h_process_latency: Any | None = None
        self._registry: CollectorRegistry | None = None

        if self._enabled:
            # Minimal metric set; names align with conventional Prometheus
            # style. Use isolated registry to avoid global duplication in tests
            self._registry = CollectorRegistry()
            self._c_events = Counter(
                "fapilog_events_processed_total",
                ("Total number of events processed across the pipeline"),
                registry=self._registry,
            )
            self._c_plugin_errors = Counter(
                "fapilog_plugin_errors_total",
                "Total number of plugin execution errors",
                ["plugin"],
                registry=self._registry,
            )
            self._h_process_latency = Histogram(
                "fapilog_event_process_seconds",
                "Latency for processing a single event",
                buckets=(
                    0.0005,
                    0.001,
                    0.0025,
                    0.005,
                    0.01,
                    0.025,
                    0.05,
                    0.1,
                    0.25,
                    0.5,
                    1.0,
                ),
                registry=self._registry,
            )

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def registry(self) -> CollectorRegistry | None:
        """Expose the isolated Prometheus registry when enabled."""
        return self._registry

    async def record_event_processed(
        self, *, duration_seconds: float | None = None
    ) -> None:
        async with self._lock:
            self._state.events_processed += 1
        if not self._enabled:
            return
        if self._c_events is not None:
            self._c_events.inc()
        if duration_seconds is not None and self._h_process_latency is not None:
            self._h_process_latency.observe(duration_seconds)

    async def record_plugin_error(
        self,
        *,
        plugin_name: str | None = None,
    ) -> None:
        async with self._lock:
            self._state.plugin_errors += 1
        if not self._enabled:
            return
        if self._c_plugin_errors is not None:
            label = plugin_name or "unknown"
            self._c_plugin_errors.labels(plugin=label).inc()

    async def snapshot(self) -> PipelineMetrics:
        # Lightweight copy without exposing internals
        async with self._lock:
            return PipelineMetrics(
                events_processed=self._state.events_processed,
                plugin_errors=self._state.plugin_errors,
            )
