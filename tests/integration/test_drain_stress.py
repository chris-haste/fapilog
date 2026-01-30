"""Stress tests for drain() behavior under various configurations.

These tests systematically verify that drain() correctly processes all events
across different combinations of:
- Number of workers (1, 2, 4, 8)
- Queue capacities (small, medium, large)
- Batch sizes (small, medium, large)
- Sink latencies (fast, slow, very slow)
- Logger modes (thread mode, bound loop mode)

Run with: pytest tests/integration/test_drain_stress.py -v
Run in CI: These are marked @pytest.mark.slow for nightly runs only.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade

# Scale down for CI environments
CI_SCALE = float(os.environ.get("CI_TIMEOUT_MULTIPLIER", "1"))
BASE_EVENTS = 500 if CI_SCALE > 1 else 1000


@dataclass
class DrainTestConfig:
    """Configuration for a drain stress test scenario."""

    name: str
    num_workers: int
    queue_capacity: int
    batch_max_size: int
    sink_latency_ms: float
    num_events: int
    mode: str  # "thread" or "bound_loop"

    @property
    def expected_drain_seconds(self) -> float:
        """Estimate expected drain time for timeout calculation."""
        if self.sink_latency_ms == 0:
            return 5.0
        # Events / workers * latency, with buffer
        return (self.num_events / self.num_workers) * (
            self.sink_latency_ms / 1000
        ) * 1.5 + 5.0


class SinkTracker:
    """Thread-safe sink that tracks processed events."""

    def __init__(self, latency_ms: float = 0):
        self.latency_ms = latency_ms
        self.count = 0
        self.lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    async def write(self, entry: dict[str, Any]) -> None:
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)
        with self.lock:
            self.count += 1
            # Only store first/last few for memory efficiency
            if len(self.events) < 10:
                self.events.append(entry)

    def reset(self) -> None:
        with self.lock:
            self.count = 0
            self.events.clear()


# =============================================================================
# Test Configurations
# =============================================================================

# Worker count variations
WORKER_CONFIGS = [
    # (num_workers, description)
    (1, "single"),
    (2, "dual"),
    (4, "quad"),
    (8, "octa"),
]

# Queue/batch size variations
QUEUE_BATCH_CONFIGS = [
    # (queue_capacity, batch_max_size, description)
    (100, 10, "small"),
    (1000, 100, "medium"),
    (5000, 500, "large"),
]

# Sink latency variations
LATENCY_CONFIGS = [
    # (latency_ms, description)
    (0, "instant"),
    (1, "fast"),
    (5, "slow"),
]


def generate_thread_mode_configs() -> list[DrainTestConfig]:
    """Generate test configurations for thread mode."""
    configs = []

    # Core matrix: workers × queue/batch × latency
    for num_workers, w_desc in WORKER_CONFIGS:
        for queue_cap, batch_size, qb_desc in QUEUE_BATCH_CONFIGS:
            for latency_ms, l_desc in LATENCY_CONFIGS:
                # Scale events based on latency to keep test times reasonable
                if latency_ms >= 5:
                    events = BASE_EVENTS // 4
                elif latency_ms >= 1:
                    events = BASE_EVENTS // 2
                else:
                    events = BASE_EVENTS

                configs.append(
                    DrainTestConfig(
                        name=f"thread_{w_desc}_{qb_desc}_{l_desc}",
                        num_workers=num_workers,
                        queue_capacity=queue_cap,
                        batch_max_size=batch_size,
                        sink_latency_ms=latency_ms,
                        num_events=events,
                        mode="thread",
                    )
                )

    return configs


def generate_bound_loop_configs() -> list[DrainTestConfig]:
    """Generate test configurations for bound loop mode."""
    configs = []

    # Subset of configurations for bound loop mode
    # (full matrix would be too slow)
    selected_combos = [
        (1, 100, 10, 0, "single_small_instant"),
        (2, 100, 10, 1, "dual_small_fast"),
        (4, 1000, 100, 0, "quad_medium_instant"),
        (4, 1000, 100, 1, "quad_medium_fast"),
        (8, 5000, 500, 0, "octa_large_instant"),
        (2, 1000, 100, 5, "dual_medium_slow"),
    ]

    for num_workers, queue_cap, batch_size, latency_ms, name in selected_combos:
        if latency_ms >= 5:
            events = BASE_EVENTS // 4
        elif latency_ms >= 1:
            events = BASE_EVENTS // 2
        else:
            events = BASE_EVENTS

        configs.append(
            DrainTestConfig(
                name=f"bound_{name}",
                num_workers=num_workers,
                queue_capacity=queue_cap,
                batch_max_size=batch_size,
                sink_latency_ms=latency_ms,
                num_events=events,
                mode="bound_loop",
            )
        )

    return configs


# Generate all test configurations
THREAD_MODE_CONFIGS = generate_thread_mode_configs()
BOUND_LOOP_CONFIGS = generate_bound_loop_configs()
ALL_CONFIGS = THREAD_MODE_CONFIGS + BOUND_LOOP_CONFIGS


# =============================================================================
# Thread Mode Tests (logger started outside async context)
# =============================================================================


@pytest.mark.slow
@pytest.mark.parametrize(
    "config",
    THREAD_MODE_CONFIGS,
    ids=[c.name for c in THREAD_MODE_CONFIGS],
)
def test_thread_mode_drain(config: DrainTestConfig) -> None:
    """Test drain in thread mode with various configurations.

    Thread mode: Logger is started before any async context exists,
    so it creates its own worker thread with a dedicated event loop.
    """
    sink = SinkTracker(latency_ms=config.sink_latency_ms)

    # Create and start logger OUTSIDE async context = thread mode
    logger = SyncLoggerFacade(
        name=f"stress_{config.name}",
        queue_capacity=config.queue_capacity,
        batch_max_size=config.batch_max_size,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=config.num_workers,
    )
    logger.start()

    assert logger._worker_thread is not None, "Expected thread mode"  # noqa: WA003

    # Generate test payload
    payload = {"test": "x" * 100, "config": config.name}

    # Submit events
    for i in range(config.num_events):
        logger.info(f"event_{i}", extra={"payload": payload, "seq": i})

    # Drain and verify
    async def do_drain():
        return await logger.stop_and_drain()

    timeout = config.expected_drain_seconds * CI_SCALE
    start = time.perf_counter()
    result = asyncio.run(do_drain())
    elapsed = time.perf_counter() - start

    # Verify no events lost
    missing = result.submitted - result.processed - result.dropped
    assert missing == 0, (
        f"Missing events: {missing} "
        f"(submitted={result.submitted}, processed={result.processed}, "
        f"dropped={result.dropped}, sink_count={sink.count})"
    )

    # Verify sink received what was reported as processed
    assert sink.count == result.processed, (
        f"Sink count mismatch: sink={sink.count}, reported={result.processed}"
    )

    # Verify drain completed in reasonable time
    assert elapsed < timeout, f"Drain took {elapsed:.1f}s, expected < {timeout:.1f}s"


# =============================================================================
# Bound Loop Mode Tests (logger started inside async context)
# =============================================================================


@pytest.mark.slow
@pytest.mark.parametrize(
    "config",
    BOUND_LOOP_CONFIGS,
    ids=[c.name for c in BOUND_LOOP_CONFIGS],
)
@pytest.mark.asyncio
async def test_bound_loop_mode_drain(config: DrainTestConfig) -> None:
    """Test drain in bound loop mode with various configurations.

    Bound loop mode: Logger is started inside an async context,
    so it uses the caller's event loop for workers.
    """
    sink = SinkTracker(latency_ms=config.sink_latency_ms)

    # Create and start logger INSIDE async context = bound loop mode
    logger = SyncLoggerFacade(
        name=f"stress_{config.name}",
        queue_capacity=config.queue_capacity,
        batch_max_size=config.batch_max_size,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=config.num_workers,
    )
    logger.start()

    assert logger._worker_thread is None, "Expected bound loop mode"

    # Generate test payload
    payload = {"test": "x" * 100, "config": config.name}

    # Submit events
    for i in range(config.num_events):
        logger.info(f"event_{i}", extra={"payload": payload, "seq": i})

    # Drain and verify
    timeout = config.expected_drain_seconds * CI_SCALE
    result = await asyncio.wait_for(
        logger.stop_and_drain(),
        timeout=timeout,
    )

    # Verify no events lost
    missing = result.submitted - result.processed - result.dropped
    assert missing == 0, (
        f"Missing events: {missing} "
        f"(submitted={result.submitted}, processed={result.processed}, "
        f"dropped={result.dropped}, sink_count={sink.count})"
    )

    # Verify sink received what was reported as processed
    assert sink.count == result.processed, (
        f"Sink count mismatch: sink={sink.count}, reported={result.processed}"
    )


# =============================================================================
# AsyncLoggerFacade Tests
# =============================================================================


@pytest.mark.slow
@pytest.mark.asyncio
async def test_async_facade_multiworker_drain() -> None:
    """Test AsyncLoggerFacade drain with multiple workers."""
    sink = SinkTracker(latency_ms=2)

    logger = AsyncLoggerFacade(
        name="async_stress",
        queue_capacity=1000,
        batch_max_size=100,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=4,
    )
    logger.start()

    # Submit events using async API
    payload = {"test": "async_payload"}
    for i in range(500):
        await logger.info(f"event_{i}", extra={"payload": payload})

    result = await logger.drain()

    missing = result.submitted - result.processed - result.dropped
    assert missing == 0, f"Missing events: {missing}"
    assert sink.count == result.processed


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.slow
def test_drain_empty_queue() -> None:
    """Test drain with no events submitted."""
    sink = SinkTracker()

    logger = SyncLoggerFacade(
        name="empty_drain",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=2,
    )
    logger.start()

    # Drain without submitting anything
    result = asyncio.run(logger.stop_and_drain())

    assert result.submitted == 0
    assert result.processed == 0
    assert result.dropped == 0
    assert sink.count == 0


@pytest.mark.slow
def test_drain_with_queue_overflow() -> None:
    """Test drain when queue overflows (drop_on_full=True)."""
    sink = SinkTracker(latency_ms=10)  # Slow sink to cause backup

    logger = SyncLoggerFacade(
        name="overflow_drain",
        queue_capacity=50,  # Small queue
        batch_max_size=10,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=1,
    )
    logger.start()

    # Submit more events than queue can hold
    for i in range(200):
        logger.info(f"event_{i}")

    result = asyncio.run(logger.stop_and_drain())

    # Should have some drops due to overflow
    assert result.dropped > 0, "Expected some drops with small queue"

    # Verify accounting: submitted = processed + dropped
    assert result.submitted == result.processed + result.dropped


@pytest.mark.slow
def test_drain_rapid_submit_then_drain() -> None:
    """Test rapid submission followed immediately by drain."""
    sink = SinkTracker()

    logger = SyncLoggerFacade(
        name="rapid_drain",
        queue_capacity=10000,
        batch_max_size=500,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=4,
    )
    logger.start()

    # Rapid submission
    for i in range(5000):
        logger.info(f"event_{i}")

    # Immediate drain
    result = asyncio.run(logger.stop_and_drain())

    missing = result.submitted - result.processed - result.dropped
    assert missing == 0, f"Missing events: {missing}"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_concurrent_submit_and_drain() -> None:
    """Test submitting events while drain is in progress."""
    sink = SinkTracker(latency_ms=1)

    logger = SyncLoggerFacade(
        name="concurrent_drain",
        queue_capacity=1000,
        batch_max_size=50,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=2,
    )
    logger.start()

    # Submit initial batch
    for i in range(200):
        logger.info(f"event_{i}")

    # Start drain
    drain_task = asyncio.create_task(logger.stop_and_drain())

    # Try to submit more (should be dropped after stop_flag is set)
    await asyncio.sleep(0.01)
    for i in range(100):
        logger.info(f"late_event_{i}")

    result = await drain_task

    # All accounted events should be processed or dropped
    missing = result.submitted - result.processed - result.dropped
    assert missing == 0, f"Missing events: {missing}"


# =============================================================================
# Large Payload Tests
# =============================================================================


@pytest.mark.slow
def test_drain_with_large_payloads() -> None:
    """Test drain with large structured payloads."""
    sink = SinkTracker()

    logger = SyncLoggerFacade(
        name="large_payload",
        queue_capacity=500,
        batch_max_size=50,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink.write,
        enrichers=[],
        metrics=None,
        num_workers=2,
    )
    logger.start()

    # Large nested payload (~5KB each)
    large_payload = {
        "data": "x" * 2000,
        "nested": {
            "level1": {
                "level2": {
                    "level3": {"data": "y" * 1000},
                },
            },
        },
        "array": [{"item": i, "value": "z" * 100} for i in range(10)],
    }

    for i in range(300):
        logger.info(f"event_{i}", extra={"payload": large_payload})

    result = asyncio.run(logger.stop_and_drain())

    missing = result.submitted - result.processed - result.dropped
    assert missing == 0, f"Missing events: {missing}"
    assert sink.count == result.processed


# =============================================================================
# Stress Test Summary
# =============================================================================


@pytest.mark.slow
def test_config_coverage_summary() -> None:
    """Verify test configuration coverage (meta-test)."""
    # Verify we have good coverage
    thread_configs = len(THREAD_MODE_CONFIGS)
    bound_configs = len(BOUND_LOOP_CONFIGS)

    # Should have at least these many configurations
    assert thread_configs >= 36, f"Expected 36+ thread configs, got {thread_configs}"
    assert bound_configs >= 6, f"Expected 6+ bound configs, got {bound_configs}"

    # Verify worker coverage
    worker_counts = {c.num_workers for c in ALL_CONFIGS}
    assert {1, 2, 4, 8} <= worker_counts, f"Missing worker counts: {worker_counts}"

    # Verify latency coverage
    latencies = {c.sink_latency_ms for c in ALL_CONFIGS}
    assert {0, 1, 5} <= latencies, f"Missing latencies: {latencies}"

    # Verify mode coverage
    modes = {c.mode for c in ALL_CONFIGS}
    assert modes == {"thread", "bound_loop"}, f"Missing modes: {modes}"
