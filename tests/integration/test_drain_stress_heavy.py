"""Heavy stress tests for drain() that push the system to its limits.

These tests are designed to find breaking points and verify behavior under
extreme load. They take several minutes to run and should be run manually
or in dedicated performance testing environments.

Throughput expectations by mode:
    - Thread mode (SyncLoggerFacade outside async): ~10-15K events/sec
      (cross-thread synchronization overhead)
    - Bound loop mode (SyncLoggerFacade inside async): ~100K+ events/sec
    - AsyncLoggerFacade: ~100K+ events/sec

Most tests use thread mode for broad compatibility. The TestSustainedLoad class
includes bound loop mode tests for async-context throughput validation.

Run with: pytest tests/integration/test_drain_stress_heavy.py -v -s
The -s flag shows real-time progress output.

Environment variables:
    STRESS_SCALE: Multiplier for event counts (default: 1.0, use 0.5 for faster runs)
    STRESS_DURATION: Target duration in seconds for sustained tests (default: 10)
"""

from __future__ import annotations

import asyncio
import gc
import os
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade

# Configuration from environment
STRESS_SCALE = float(os.environ.get("STRESS_SCALE", "1.0"))
STRESS_DURATION = float(os.environ.get("STRESS_DURATION", "10"))


@dataclass
class StressMetrics:
    """Metrics collected during stress test."""

    submit_count: int = 0
    submit_elapsed: float = 0.0
    submit_rate: float = 0.0
    drain_elapsed: float = 0.0
    processed: int = 0
    dropped: int = 0
    missing: int = 0
    sink_count: int = 0
    latencies_us: list[float] = field(default_factory=list)

    @property
    def latency_avg_us(self) -> float:
        return statistics.mean(self.latencies_us) if self.latencies_us else 0

    @property
    def latency_p50_us(self) -> float:
        return statistics.median(self.latencies_us) if self.latencies_us else 0

    @property
    def latency_p99_us(self) -> float:
        if not self.latencies_us:
            return 0
        sorted_lat = sorted(self.latencies_us)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def summary(self) -> str:
        return (
            f"Submit: {self.submit_count:,} events in {self.submit_elapsed:.2f}s "
            f"({self.submit_rate:,.0f}/sec)\n"
            f"Drain: {self.drain_elapsed:.2f}s\n"
            f"Processed: {self.processed:,}, Dropped: {self.dropped:,}, "
            f"Missing: {self.missing:,}\n"
            f"Sink received: {self.sink_count:,}\n"
            f"Latency: avg={self.latency_avg_us:.1f}µs, "
            f"p50={self.latency_p50_us:.1f}µs, p99={self.latency_p99_us:.1f}µs"
        )


class LatencyTrackingSink:
    """Sink that tracks processing latency and count."""

    def __init__(self, latency_ms: float = 0, sample_latency: bool = False):
        self.latency_ms = latency_ms
        self.sample_latency = sample_latency
        self.count = 0
        self.lock = threading.Lock()
        self.latencies_us: list[float] = []
        self._sample_every = 100  # Sample 1% of events for latency

    async def write(self, entry: dict[str, Any]) -> None:
        # Track end-to-end latency for sampled events
        if self.sample_latency and self.count % self._sample_every == 0:
            if "_submit_time" in entry:
                latency = (time.perf_counter() - entry["_submit_time"]) * 1_000_000
                with self.lock:
                    self.latencies_us.append(latency)

        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        with self.lock:
            self.count += 1

    def reset(self) -> None:
        with self.lock:
            self.count = 0
            self.latencies_us.clear()


def generate_payload(size_bytes: int) -> dict[str, Any]:
    """Generate a payload of approximately the given size."""
    base = {
        "user_id": "user-12345-abcdef",
        "session_id": "sess-67890-ghijkl",
        "request_id": "req-11111-mnopqr",
        "timestamp": "2024-01-15T10:30:00.000Z",
        "level": "INFO",
        "service": "test-service",
        "environment": "stress-test",
    }
    current_size = len(str(base))
    if current_size < size_bytes:
        base["payload"] = "x" * (size_bytes - current_size)
    return base


# =============================================================================
# High Throughput Tests
# =============================================================================


@pytest.mark.stress
class TestHighThroughput:
    """Tests that push for maximum events per second."""

    def test_max_throughput_fast_sink(self) -> None:
        """Measure maximum throughput with instant sink (no I/O latency).

        This establishes the upper bound of what the logging pipeline can handle.
        """
        sink = LatencyTrackingSink(latency_ms=0, sample_latency=True)
        num_events = int(100_000 * STRESS_SCALE)

        logger = SyncLoggerFacade(
            name="throughput_fast",
            queue_capacity=50_000,
            batch_max_size=1000,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(f"\n  Submitting {num_events:,} events (fast sink)...")
        start = time.perf_counter()
        for i in range(num_events):
            logger.info(
                f"event_{i}",
                extra={"payload": payload, "_submit_time": time.perf_counter()},
            )
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count
        metrics.latencies_us = sink.latencies_us

        print(f"\n  {metrics.summary()}")

        # Assertions - verify correctness, not throughput (hardware-dependent)
        assert metrics.missing == 0, f"Missing events: {metrics.missing}"
        assert metrics.sink_count == metrics.processed

    def test_max_throughput_slow_sink(self) -> None:
        """Measure throughput with realistic sink latency (1ms per event).

        This simulates real-world conditions where sinks have I/O latency.
        """
        sink = LatencyTrackingSink(latency_ms=1, sample_latency=True)
        num_events = int(20_000 * STRESS_SCALE)

        logger = SyncLoggerFacade(
            name="throughput_slow",
            queue_capacity=30_000,
            batch_max_size=500,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=8,  # More workers to parallelize slow sink
        )
        logger.start()

        payload = generate_payload(512)
        metrics = StressMetrics()

        print(f"\n  Submitting {num_events:,} events (1ms sink latency)...")
        start = time.perf_counter()
        for i in range(num_events):
            logger.info(
                f"event_{i}",
                extra={"payload": payload, "_submit_time": time.perf_counter()},
            )
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining (this will take a while with slow sink)...")

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count
        metrics.latencies_us = sink.latencies_us

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"
        assert metrics.sink_count == metrics.processed


# =============================================================================
# Sustained Load Tests
# =============================================================================


@pytest.mark.stress
class TestSustainedLoad:
    """Tests that maintain load over extended periods."""

    def test_sustained_load_thread_mode(self) -> None:
        """Sustain high load for extended duration in thread mode.

        This tests for memory leaks, queue stability, and consistent performance.
        """
        sink = LatencyTrackingSink(latency_ms=0.5, sample_latency=True)
        duration = STRESS_DURATION
        target_rate = 10_000  # events/sec

        logger = SyncLoggerFacade(
            name="sustained_thread",
            queue_capacity=20_000,
            batch_max_size=200,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=2,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(f"\n  Sustaining ~{target_rate:,} events/sec for {duration}s...")

        # Submit at controlled rate
        start = time.perf_counter()
        event_count = 0
        interval = 1.0 / target_rate

        while time.perf_counter() - start < duration:
            batch_start = time.perf_counter()
            # Submit in small batches for rate control
            for _ in range(100):
                logger.info(
                    f"event_{event_count}",
                    extra={"payload": payload, "_submit_time": time.perf_counter()},
                )
                event_count += 1
            # Pace to target rate
            batch_elapsed = time.perf_counter() - batch_start
            target_batch_time = 100 * interval
            if batch_elapsed < target_batch_time:
                time.sleep(target_batch_time - batch_elapsed)

        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = event_count
        metrics.submit_rate = event_count / metrics.submit_elapsed

        print(f"  Submitted {event_count:,} events in {metrics.submit_elapsed:.1f}s")
        print(f"  Actual rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count
        metrics.latencies_us = sink.latencies_us

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"

    @pytest.mark.asyncio
    async def test_sustained_load_bound_loop_mode(self) -> None:
        """Sustain high load in bound loop mode (async context)."""
        sink = LatencyTrackingSink(latency_ms=0.5, sample_latency=True)
        duration = STRESS_DURATION
        target_rate = 10_000

        logger = SyncLoggerFacade(
            name="sustained_bound",
            queue_capacity=20_000,
            batch_max_size=200,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=2,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        assert logger._worker_thread is None, "Expected bound loop mode"

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(
            f"\n  Sustaining ~{target_rate:,} events/sec for {duration}s (bound loop)..."
        )

        start = time.perf_counter()
        event_count = 0
        interval = 1.0 / target_rate

        while time.perf_counter() - start < duration:
            batch_start = time.perf_counter()
            for _ in range(100):
                logger.info(
                    f"event_{event_count}",
                    extra={"payload": payload, "_submit_time": time.perf_counter()},
                )
                event_count += 1
            batch_elapsed = time.perf_counter() - batch_start
            target_batch_time = 100 * interval
            if batch_elapsed < target_batch_time:
                await asyncio.sleep(target_batch_time - batch_elapsed)

        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = event_count
        metrics.submit_rate = event_count / metrics.submit_elapsed

        print(f"  Submitted {event_count:,} events in {metrics.submit_elapsed:.1f}s")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = await logger.stop_and_drain()
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count
        metrics.latencies_us = sink.latencies_us

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"


# =============================================================================
# Queue Saturation Tests
# =============================================================================


@pytest.mark.stress
class TestQueueSaturation:
    """Tests that keep the queue at or near capacity."""

    def test_queue_constantly_full(self) -> None:
        """Test behavior when queue is constantly at capacity.

        Submit faster than drain can process, forcing drops.
        """
        sink = LatencyTrackingSink(latency_ms=5)  # Very slow sink
        num_events = int(50_000 * STRESS_SCALE)
        queue_capacity = 1000  # Small queue to force saturation

        logger = SyncLoggerFacade(
            name="saturated",
            queue_capacity=queue_capacity,
            batch_max_size=100,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=2,
        )
        logger.start()

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(f"\n  Submitting {num_events:,} events to queue of {queue_capacity}...")
        print("  (Sink latency 5ms, expect significant drops)")

        start = time.perf_counter()
        for i in range(num_events):
            logger.info(f"event_{i}", extra={"payload": payload})
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count

        print(f"\n  {metrics.summary()}")
        print(f"  Drop rate: {100 * metrics.dropped / metrics.submit_count:.1f}%")

        # Key assertion: no missing events (all accounted as processed or dropped)
        assert metrics.missing == 0, f"Missing events: {metrics.missing}"
        # Should have significant drops given the configuration
        assert metrics.dropped > 0, "Expected drops with saturated queue"
        # Verify accounting
        assert metrics.sink_count == metrics.processed


# =============================================================================
# Large Payload Tests
# =============================================================================


@pytest.mark.stress
class TestLargePayloads:
    """Tests with large structured payloads."""

    def test_large_payloads_high_volume(self) -> None:
        """Test with large payloads (5KB each) at high volume."""
        sink = LatencyTrackingSink(latency_ms=0)
        num_events = int(20_000 * STRESS_SCALE)
        payload_size = 5000  # 5KB

        logger = SyncLoggerFacade(
            name="large_payload",
            queue_capacity=10_000,
            batch_max_size=100,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        payload = generate_payload(payload_size)
        metrics = StressMetrics()

        print(
            f"\n  Submitting {num_events:,} events with {payload_size / 1000:.0f}KB payloads..."
        )

        gc.collect()
        mem_before = _get_memory_mb()

        start = time.perf_counter()
        for i in range(num_events):
            logger.info(f"event_{i}", extra={"payload": payload})
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        metrics.drain_elapsed = time.perf_counter() - drain_start

        gc.collect()
        mem_after = _get_memory_mb()

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count

        print(f"\n  {metrics.summary()}")
        print(
            f"  Memory: {mem_before:.1f}MB -> {mem_after:.1f}MB (delta: {mem_after - mem_before:.1f}MB)"
        )

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"

    def test_deeply_nested_payloads(self) -> None:
        """Test with deeply nested payload structures."""
        sink = LatencyTrackingSink(latency_ms=0)
        num_events = int(10_000 * STRESS_SCALE)

        logger = SyncLoggerFacade(
            name="nested_payload",
            queue_capacity=5_000,
            batch_max_size=100,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        # Create deeply nested structure
        def make_nested(depth: int) -> dict:
            if depth == 0:
                return {"leaf": "x" * 100}
            return {"level": depth, "data": "y" * 50, "child": make_nested(depth - 1)}

        payload = make_nested(20)  # 20 levels deep
        metrics = StressMetrics()

        print(f"\n  Submitting {num_events:,} events with 20-level nested payloads...")

        start = time.perf_counter()
        for i in range(num_events):
            logger.info(f"event_{i}", extra={"payload": payload})
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"


# =============================================================================
# Multi-Worker Scaling Tests
# =============================================================================


@pytest.mark.stress
class TestWorkerScaling:
    """Tests for worker count scaling behavior."""

    @pytest.mark.parametrize("num_workers", [1, 2, 4, 8, 16])
    def test_worker_scaling_with_slow_sink(self, num_workers: int) -> None:
        """Test how throughput scales with worker count for slow sinks."""
        sink = LatencyTrackingSink(latency_ms=2)
        num_events = int(5_000 * STRESS_SCALE)

        logger = SyncLoggerFacade(
            name=f"scaling_{num_workers}w",
            queue_capacity=10_000,
            batch_max_size=100,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=2,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=num_workers,
        )
        logger.start()

        payload = generate_payload(256)

        print(f"\n  Workers: {num_workers}, Events: {num_events:,}...")

        start = time.perf_counter()
        for i in range(num_events):
            logger.info(f"event_{i}", extra={"payload": payload})
        submit_elapsed = time.perf_counter() - start

        drain_start = time.perf_counter()
        result = asyncio.run(logger.stop_and_drain())
        drain_elapsed = time.perf_counter() - drain_start

        total_elapsed = submit_elapsed + drain_elapsed
        throughput = num_events / total_elapsed

        missing = result.submitted - result.processed - result.dropped

        print(
            f"  Total time: {total_elapsed:.2f}s, Throughput: {throughput:,.0f} events/sec"
        )
        print(f"  Processed: {result.processed:,}, Dropped: {result.dropped:,}")

        assert missing == 0, f"Missing events: {missing}"


# =============================================================================
# Async High Throughput Tests (100K+ events/sec target)
# =============================================================================


@pytest.mark.stress
class TestAsyncHighThroughput:
    """Tests targeting 100K+ events/sec using async modes.

    These tests validate the library's async-first design where high throughput
    is achieved by avoiding cross-thread synchronization.
    """

    @pytest.mark.asyncio
    async def test_async_facade_max_throughput(self) -> None:
        """AsyncLoggerFacade should achieve 100K+ events/sec with fast sink."""
        sink = LatencyTrackingSink(latency_ms=0, sample_latency=True)
        num_events = int(100_000 * STRESS_SCALE)

        logger = AsyncLoggerFacade(
            name="async_throughput",
            queue_capacity=50_000,
            batch_max_size=1000,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(f"\n  AsyncLoggerFacade: {num_events:,} events...")
        start = time.perf_counter()
        for i in range(num_events):
            await logger.info(f"event_{i}", extra={"payload": payload})
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = await logger.drain()
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count
        metrics.latencies_us = sink.latencies_us

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"
        assert metrics.sink_count == metrics.processed

    @pytest.mark.asyncio
    async def test_bound_loop_max_throughput(self) -> None:
        """SyncLoggerFacade in bound loop mode should achieve 100K+ events/sec."""
        sink = LatencyTrackingSink(latency_ms=0, sample_latency=True)
        num_events = int(100_000 * STRESS_SCALE)

        # Start inside async context = bound loop mode
        logger = SyncLoggerFacade(
            name="bound_throughput",
            queue_capacity=50_000,
            batch_max_size=1000,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=4,
        )
        logger.start()

        assert logger._worker_thread is None, "Expected bound loop mode"

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(f"\n  Bound loop mode: {num_events:,} events...")
        start = time.perf_counter()
        for i in range(num_events):
            logger.info(f"event_{i}", extra={"payload": payload})
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = await logger.stop_and_drain()
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count
        metrics.latencies_us = sink.latencies_us

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"
        assert metrics.sink_count == metrics.processed

    @pytest.mark.asyncio
    async def test_async_facade_sustained_high_throughput(self) -> None:
        """Sustain high throughput for extended duration with AsyncLoggerFacade."""
        sink = LatencyTrackingSink(latency_ms=0.1)  # Small latency
        duration = STRESS_DURATION
        target_rate = 50_000  # Target 50K/sec sustained

        logger = AsyncLoggerFacade(
            name="async_sustained",
            queue_capacity=100_000,
            batch_max_size=500,
            batch_timeout_seconds=0.01,
            backpressure_wait_ms=1,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=8,
        )
        logger.start()

        payload = generate_payload(256)
        metrics = StressMetrics()

        print(f"\n  Sustaining ~{target_rate:,} events/sec for {duration}s (async)...")

        start = time.perf_counter()
        event_count = 0
        interval = 1.0 / target_rate

        while time.perf_counter() - start < duration:
            batch_start = time.perf_counter()
            for _ in range(100):
                await logger.info(f"event_{event_count}", extra={"payload": payload})
                event_count += 1
            batch_elapsed = time.perf_counter() - batch_start
            target_batch_time = 100 * interval
            if batch_elapsed < target_batch_time:
                await asyncio.sleep(target_batch_time - batch_elapsed)

        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = event_count
        metrics.submit_rate = event_count / metrics.submit_elapsed

        print(f"  Submitted {event_count:,} events in {metrics.submit_elapsed:.1f}s")
        print(f"  Actual rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = await logger.drain()
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"

    @pytest.mark.asyncio
    async def test_async_facade_with_slow_sink(self) -> None:
        """Test AsyncLoggerFacade with realistic sink latency."""
        sink = LatencyTrackingSink(latency_ms=2)
        num_events = int(50_000 * STRESS_SCALE)

        logger = AsyncLoggerFacade(
            name="async_slow_sink",
            queue_capacity=100_000,
            batch_max_size=500,
            batch_timeout_seconds=0.02,
            backpressure_wait_ms=5,
            drop_on_full=True,
            sink_write=sink.write,
            enrichers=[],
            metrics=None,
            num_workers=16,  # More workers for slow sink
        )
        logger.start()

        payload = generate_payload(512)
        metrics = StressMetrics()

        print(f"\n  AsyncLoggerFacade with 2ms sink: {num_events:,} events...")
        start = time.perf_counter()
        for i in range(num_events):
            await logger.info(f"event_{i}", extra={"payload": payload})
        metrics.submit_elapsed = time.perf_counter() - start
        metrics.submit_count = num_events
        metrics.submit_rate = num_events / metrics.submit_elapsed

        print(f"  Submit rate: {metrics.submit_rate:,.0f} events/sec")
        print("  Draining...")

        drain_start = time.perf_counter()
        result = await logger.drain()
        metrics.drain_elapsed = time.perf_counter() - drain_start

        metrics.processed = result.processed
        metrics.dropped = result.dropped
        metrics.missing = result.submitted - result.processed - result.dropped
        metrics.sink_count = sink.count

        print(f"\n  {metrics.summary()}")

        assert metrics.missing == 0, f"Missing events: {metrics.missing}"
        assert metrics.sink_count == metrics.processed


# =============================================================================
# Helpers
# =============================================================================


def _get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
    except ImportError:
        return 0.0


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    # Allow running directly for quick manual testing
    pytest.main([__file__, "-v", "-s", "--tb=short"])
