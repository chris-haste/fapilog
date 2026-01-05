"""
TDD tests for Story 5.4: Plugin Testing Benchmarks.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_benchmark_async_records_results() -> None:
    """benchmark_async should return BenchmarkResult with metrics."""
    from fapilog.testing.benchmarks import BenchmarkResult, benchmark_async

    calls = 0

    async def sample() -> None:
        nonlocal calls
        calls += 1

    result = await benchmark_async("sample", sample, iterations=5, warmup=2)

    assert isinstance(result, BenchmarkResult)
    assert result.iterations == 5
    assert calls == 7  # warmup + iterations
    assert result.total_seconds > 0
    assert result.ops_per_second > 0


@pytest.mark.asyncio
async def test_benchmark_sink_uses_lifecycle() -> None:
    """benchmark_sink should start and stop the sink."""
    from fapilog.testing import MockSink
    from fapilog.testing.benchmarks import benchmark_sink

    sink = MockSink()
    result = await benchmark_sink(sink, iterations=3, warmup=0)

    assert sink.start_called is True
    assert sink.stop_called is True
    assert result.iterations == 3


@pytest.mark.asyncio
async def test_benchmark_enricher_runs_enrich() -> None:
    """benchmark_enricher should measure enrich performance."""
    from fapilog.testing import MockEnricher
    from fapilog.testing.benchmarks import benchmark_enricher

    enricher = MockEnricher()
    result = await benchmark_enricher(enricher, iterations=4, warmup=0)

    assert enricher.call_count >= 4
    assert result.iterations == 4
    assert result.ops_per_second > 0


@pytest.mark.asyncio
async def test_benchmark_filter_runs_filter() -> None:
    """benchmark_filter should measure filter performance."""
    from fapilog.testing import MockFilter
    from fapilog.testing.benchmarks import benchmark_filter

    filter_plugin = MockFilter()
    result = await benchmark_filter(filter_plugin, iterations=2, warmup=0)

    assert filter_plugin.call_count >= 2
    assert result.iterations == 2
    assert result.avg_latency_ms >= 0
