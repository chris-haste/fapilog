"""
Benchmark helpers for plugin performance testing.

Provides utilities to measure async plugin performance with minimal setup.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass
class BenchmarkResult:
    """Results from a plugin benchmark."""

    name: str
    iterations: int
    total_seconds: float
    ops_per_second: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float

    def __str__(self) -> str:
        return (
            f"{self.name}: {self.ops_per_second:.0f} ops/s, "
            f"avg={self.avg_latency_ms:.3f}ms"
        )


async def benchmark_async(
    name: str,
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    iterations: int = 1000,
    warmup: int = 100,
    **kwargs: Any,
) -> BenchmarkResult:
    """Benchmark an async function with a warmup phase."""
    for _ in range(warmup):
        await fn(*args, **kwargs)

    latencies: list[float] = []
    start_total = time.perf_counter()

    for _ in range(iterations):
        start = time.perf_counter()
        await fn(*args, **kwargs)
        latencies.append((time.perf_counter() - start) * 1000)

    total_seconds = time.perf_counter() - start_total
    ops_per_second = iterations / total_seconds if total_seconds > 0 else float("inf")

    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_seconds=total_seconds,
        ops_per_second=ops_per_second,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        min_latency_ms=min(latencies) if latencies else 0.0,
        max_latency_ms=max(latencies) if latencies else 0.0,
    )


async def benchmark_sink(
    sink: Any,
    iterations: int = 1000,
    warmup: int = 100,
) -> BenchmarkResult:
    """Benchmark a sink's write performance."""
    entry = {"level": "INFO", "message": "benchmark"}
    await sink.start()
    try:
        return await benchmark_async(
            f"sink:{getattr(sink, 'name', 'unknown')}",
            sink.write,
            entry,
            iterations=iterations,
            warmup=warmup,
        )
    finally:
        await sink.stop()


async def benchmark_enricher(
    enricher: Any,
    iterations: int = 1000,
    warmup: int = 100,
) -> BenchmarkResult:
    """Benchmark an enricher's enrich performance."""
    event = {"level": "INFO", "message": "benchmark"}
    await enricher.start()
    try:
        return await benchmark_async(
            f"enricher:{getattr(enricher, 'name', 'unknown')}",
            enricher.enrich,
            event,
            iterations=iterations,
            warmup=warmup,
        )
    finally:
        await enricher.stop()


async def benchmark_filter(
    filter_plugin: Any,
    iterations: int = 1000,
    warmup: int = 100,
) -> BenchmarkResult:
    """Benchmark a filter's filter performance."""
    event = {"level": "INFO", "message": "benchmark"}
    await filter_plugin.start()
    try:
        return await benchmark_async(
            f"filter:{getattr(filter_plugin, 'name', 'unknown')}",
            filter_plugin.filter,
            event,
            iterations=iterations,
            warmup=warmup,
        )
    finally:
        await filter_plugin.stop()
