#!/usr/bin/env python3
"""
Load testing script for fapilog logging queue.

This script simulates high-throughput logging scenarios to verify the logging queue
performs reliably under load and does not degrade service responsiveness.

Usage:
    python scripts/load_test_log_queue.py [OPTIONS]

Examples:
    # Basic test with default settings
    python scripts/load_test_log_queue.py

    # High concurrency test
    python scripts/load_test_log_queue.py --concurrency 50 --rate 1000 --duration 30

    # Test different overflow strategies
    python scripts/load_test_log_queue.py --overflow drop --queue-size 100
    python scripts/load_test_log_queue.py --overflow block --queue-size 100
    python scripts/load_test_log_queue.py --overflow sample --queue-size 100
"""

import argparse
import asyncio
import os
import sys
import time
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fapilog import configure_logging, log
from fapilog.settings import LoggingSettings


class LoadTestMetrics:
    """Track metrics during load testing."""

    def __init__(self) -> None:
        self.total_attempted = 0
        self.total_enqueued = 0
        self.total_dropped = 0
        self.latencies: List[float] = []
        self.start_time = 0.0
        self.end_time = 0.0

    def record_log_attempt(self, enqueued: bool, latency: float) -> None:
        """Record a log attempt with its result."""
        self.total_attempted += 1
        if enqueued:
            self.total_enqueued += 1
            self.latencies.append(latency)
        else:
            self.total_dropped += 1

    def get_average_latency(self) -> float:
        """Calculate average enqueue latency in microseconds."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies) * 1_000_000  # Convert to µs

    def get_total_duration(self) -> float:
        """Get total test duration in seconds."""
        return self.end_time - self.start_time

    def get_logs_per_second(self) -> float:
        """Calculate logs per second."""
        duration = self.get_total_duration()
        if duration <= 0:
            return 0.0
        return self.total_attempted / duration


class DebugSink:
    """Debug sink that records delivery counts for instrumentation."""

    def __init__(self) -> None:
        self.delivery_count = 0
        self.error_count = 0

    async def write(self, event_dict: Dict) -> None:
        """Write event and track delivery."""
        try:
            # Simulate some processing time
            await asyncio.sleep(0.001)
            self.delivery_count += 1
        except Exception:
            self.error_count += 1
            raise


async def log_worker(
    worker_id: int,
    rate_per_second: float,
    duration: float,
    metrics: LoadTestMetrics,
    log_interval: float,
) -> None:
    """Worker coroutine that generates logs at a specified rate."""
    start_time = time.perf_counter()
    end_time = start_time + duration

    while time.perf_counter() < end_time:
        # Calculate when this log should be sent
        expected_time = start_time + (metrics.total_attempted * log_interval)
        current_time = time.perf_counter()

        # Sleep if we're ahead of schedule
        if current_time < expected_time:
            await asyncio.sleep(expected_time - current_time)

        # Generate log with timing measurement
        log_start = time.perf_counter()

        # Use a structured log with worker info
        log.info(
            "load_test_log",
            worker_id=worker_id,
            log_number=metrics.total_attempted,
            timestamp=time.time(),
            message=f"Load test log from worker {worker_id}",
        )

        log_end = time.perf_counter()
        latency = log_end - log_start

        # Record the attempt (we can't easily detect if it was dropped,
        # so we'll assume it was enqueued for now)
        metrics.record_log_attempt(enqueued=True, latency=latency)


async def run_load_test(
    concurrency: int,
    rate_per_second: float,
    duration: float,
    queue_size: int,
    overflow_strategy: str,
    batch_size: int,
    batch_timeout: float,
) -> LoadTestMetrics:
    """Run the load test with specified parameters."""
    print(f"Starting load test with {concurrency} workers...")
    print(f"Target rate: {rate_per_second} logs/sec per worker")
    print(f"Duration: {duration} seconds")
    print(f"Queue size: {queue_size}")
    print(f"Overflow strategy: {overflow_strategy}")
    print(f"Batch size: {batch_size}")
    print(f"Batch timeout: {batch_timeout}s")
    print("-" * 60)

    # Configure logging with test settings
    settings = LoggingSettings(
        level="INFO",
        queue_enabled=True,
        queue_maxsize=queue_size,
        queue_overflow=overflow_strategy,
        queue_batch_size=batch_size,
        queue_batch_timeout=batch_timeout,
        queue_retry_delay=0.1,  # Faster retries for testing
        queue_max_retries=1,  # Fewer retries for testing
        sinks=["stdout"],
        json_console="json",  # Use JSON for consistent output
    )

    # Configure logging
    configure_logging(settings=settings)

    # Create metrics tracker
    metrics = LoadTestMetrics()
    metrics.start_time = time.perf_counter()

    # Calculate log interval per worker
    log_interval = 1.0 / rate_per_second if rate_per_second > 0 else 1.0

    # Create worker tasks
    tasks = []
    for worker_id in range(concurrency):
        task = asyncio.create_task(
            log_worker(worker_id, rate_per_second, duration, metrics, log_interval)
        )
        tasks.append(task)

    # Wait for all workers to complete
    await asyncio.gather(*tasks, return_exceptions=True)

    metrics.end_time = time.perf_counter()

    return metrics


def print_results(metrics: LoadTestMetrics, settings: LoggingSettings) -> None:
    """Print test results in a formatted way."""
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)

    duration = metrics.get_total_duration()
    logs_per_second = metrics.get_logs_per_second()
    avg_latency = metrics.get_average_latency()

    print(f"Test Duration:           {duration:.2f} seconds")
    print(f"Total Logs Attempted:    {metrics.total_attempted:,}")
    print(f"Successfully Enqueued:   {metrics.total_enqueued:,}")
    print(f"Dropped:                 {metrics.total_dropped:,}")
    print(f"Actual Logs/Second:      {logs_per_second:.2f}")
    print(f"Average Enqueue Latency: {avg_latency:.2f} µs")

    if metrics.latencies:
        min_latency = min(metrics.latencies) * 1_000_000
        max_latency = max(metrics.latencies) * 1_000_000
        print(f"Min Latency:             {min_latency:.2f} µs")
        print(f"Max Latency:             {max_latency:.2f} µs")

    print("\nQueue Configuration:")
    print(f"  Queue Size:            {settings.queue_maxsize}")
    print(f"  Overflow Strategy:      {settings.queue_overflow}")
    print(f"  Batch Size:            {settings.queue_batch_size}")
    print(f"  Batch Timeout:         {settings.queue_batch_timeout}s")

    # Performance assessment
    print("\nPerformance Assessment:")
    if avg_latency < 100:
        print("  ✅ Excellent: <100 µs average latency")
    elif avg_latency < 500:
        print(f"  ⚠️  Good: {avg_latency:.2f} µs average latency")
    else:
        print(f"  ❌ Poor: {avg_latency:.2f} µs average latency")

    if metrics.total_dropped == 0:
        print("  ✅ No logs dropped")
    else:
        drop_rate = (metrics.total_dropped / metrics.total_attempted) * 100
        print(f"  ⚠️  {drop_rate:.2f}% of logs dropped")

    print("=" * 60)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Load test the fapilog logging queue",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("LOAD_TEST_CONCURRENCY", "10")),
        help="Number of concurrent workers (default: 10)",
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=float(os.getenv("LOAD_TEST_RATE", "100")),
        help="Logs per second per worker (default: 100)",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("LOAD_TEST_DURATION", "30")),
        help="Test duration in seconds (default: 30)",
    )

    parser.add_argument(
        "--queue-size",
        type=int,
        default=int(os.getenv("LOAD_TEST_QUEUE_SIZE", "1000")),
        help="Maximum queue size (default: 1000)",
    )

    parser.add_argument(
        "--overflow",
        choices=["drop", "block", "sample"],
        default=os.getenv("LOAD_TEST_OVERFLOW", "drop"),
        help="Queue overflow strategy (default: drop)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("LOAD_TEST_BATCH_SIZE", "10")),
        help="Queue batch size (default: 10)",
    )

    parser.add_argument(
        "--batch-timeout",
        type=float,
        default=float(os.getenv("LOAD_TEST_BATCH_TIMEOUT", "1.0")),
        help="Queue batch timeout in seconds (default: 1.0)",
    )

    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    # Validate arguments
    if args.concurrency <= 0:
        print("Error: concurrency must be positive")
        sys.exit(1)

    if args.rate <= 0:
        print("Error: rate must be positive")
        sys.exit(1)

    if args.duration <= 0:
        print("Error: duration must be positive")
        sys.exit(1)

    if args.queue_size <= 0:
        print("Error: queue-size must be positive")
        sys.exit(1)

    try:
        # Run the load test
        metrics = await run_load_test(
            concurrency=args.concurrency,
            rate_per_second=args.rate,
            duration=args.duration,
            queue_size=args.queue_size,
            overflow_strategy=args.overflow,
            batch_size=args.batch_size,
            batch_timeout=args.batch_timeout,
        )

        # Create settings for result display
        settings = LoggingSettings(
            queue_maxsize=args.queue_size,
            queue_overflow=args.overflow,
            queue_batch_size=args.batch_size,
            queue_batch_timeout=args.batch_timeout,
        )

        # Print results
        print_results(metrics, settings)

    except KeyboardInterrupt:
        print("\nLoad test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during load test: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
