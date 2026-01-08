"""
Concurrency tests for SinkCircuitBreaker (Story 7.7).

These tests verify thread-safe behavior under concurrent access.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from fapilog.core.circuit_breaker import (
    CircuitState,
    SinkCircuitBreaker,
    SinkCircuitBreakerConfig,
)


class TestCircuitBreakerThreadConcurrency:
    """Thread-level concurrency tests."""

    @pytest.mark.integration
    def test_half_open_call_limit_enforced_single_thread(self) -> None:
        """Half-open call limit should be enforced by should_allow() itself.

        This test verifies that should_allow() atomically checks AND increments
        the half_open_calls counter. Currently, should_allow() only checks but
        doesn't increment - this is a design flaw that needs fixing.
        """
        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
            half_open_max_calls=3,
        )
        breaker = SinkCircuitBreaker("limit-sink", config)

        # Force into HALF_OPEN state
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # First should_allow() transitions to HALF_OPEN and should count as call 1
        allowed_1 = breaker.should_allow()
        assert allowed_1 is True
        assert breaker.state == CircuitState.HALF_OPEN

        # Subsequent calls should be counted and limited
        allowed_2 = breaker.should_allow()
        allowed_3 = breaker.should_allow()
        allowed_4 = breaker.should_allow()  # Should be denied (4th call, limit is 3)

        allowed_calls = [allowed_1, allowed_2, allowed_3, allowed_4]

        # Exactly 3 calls should be allowed (half_open_max_calls=3)
        assert sum(allowed_calls) == 3, (
            f"Expected exactly 3 allowed calls but got {sum(allowed_calls)}. "
            f"Results: {allowed_calls}. "
            "should_allow() must atomically increment _half_open_calls."
        )

    @pytest.mark.integration
    def test_failure_count_not_lost_under_contention(self) -> None:
        """Failure count increments are not lost under concurrent access."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=1000,  # High threshold so circuit stays closed
            recovery_timeout_seconds=60.0,
        )
        breaker = SinkCircuitBreaker("count-sink", config)

        num_threads = 50
        failures_per_thread = 20
        expected_total = num_threads * failures_per_thread

        def record_failures() -> None:
            for _ in range(failures_per_thread):
                breaker.record_failure()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_failures) for _ in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        # With proper locking, no increments should be lost
        assert breaker._failure_count == expected_total, (
            f"Expected {expected_total} failures but got {breaker._failure_count}. "
            f"Lost {expected_total - breaker._failure_count} increments due to race condition."
        )

    @pytest.mark.integration
    def test_concurrent_failures_open_circuit(self) -> None:
        """Multiple threads recording failures should open circuit."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout_seconds=60.0,
        )
        breaker = SinkCircuitBreaker("test-sink", config)

        num_threads = 20
        failures_per_thread = 5

        def record_failures() -> int:
            count = 0
            for _ in range(failures_per_thread):
                breaker.record_failure()
                count += 1
            return count

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(record_failures) for _ in range(num_threads)]
            total = sum(f.result() for f in as_completed(futures))

        # All failures should be recorded
        assert total == num_threads * failures_per_thread

        # Circuit must be open (threshold=10, recorded=100)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.integration
    def test_concurrent_success_and_failure_during_half_open(self) -> None:
        """Concurrent success/failure during HALF_OPEN produces valid state."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,  # Immediate recovery
            half_open_max_calls=10,
        )
        breaker = SinkCircuitBreaker("test-sink", config)

        # Force into HALF_OPEN
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        breaker.should_allow()  # Transitions to HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

        results: list[CircuitState] = []
        lock = threading.Lock()

        def mixed_operations(success: bool) -> None:
            if success:
                breaker.record_success()
            else:
                breaker.record_failure()
            with lock:
                results.append(breaker.state)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in range(50):
                futures.append(executor.submit(mixed_operations, i % 2 == 0))
            for f in as_completed(futures):
                f.result()

        # Final state must be valid
        assert breaker.state in (
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        )

        # All observed states must be valid
        for state in results:
            assert state in (
                CircuitState.CLOSED,
                CircuitState.OPEN,
                CircuitState.HALF_OPEN,
            )

    @pytest.mark.integration
    def test_high_contention_stress(self) -> None:
        """Stress test with high contention (100+ concurrent operations)."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=50,
            recovery_timeout_seconds=0.001,
            half_open_max_calls=5,
        )
        breaker = SinkCircuitBreaker("stress-sink", config)

        num_threads = 100
        operations_per_thread = 100
        errors: list[Exception] = []
        error_lock = threading.Lock()

        def stress_operations() -> None:
            try:
                for i in range(operations_per_thread):
                    breaker.should_allow()
                    if i % 3 == 0:
                        breaker.record_failure()
                    else:
                        breaker.record_success()
            except Exception as e:
                with error_lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(stress_operations) for _ in range(num_threads)]
            for f in as_completed(futures):
                f.result()

        # No exceptions during stress
        assert len(errors) == 0, f"Errors: {errors}"

        # State must be valid
        assert breaker.state in (
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        )


class TestCircuitBreakerAsyncConcurrency:
    """Async task concurrency tests."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_async_failures(self) -> None:
        """Multiple async tasks recording failures concurrently."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout_seconds=60.0,
        )
        breaker = SinkCircuitBreaker("async-sink", config)

        async def record_failures(count: int) -> int:
            for _ in range(count):
                breaker.record_failure()
                await asyncio.sleep(0)  # Yield to other tasks
            return count

        tasks = [asyncio.create_task(record_failures(5)) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        assert sum(results) == 100
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_async_state_transitions_under_load(self) -> None:
        """State transitions remain consistent under async load."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout_seconds=0.001,
            half_open_max_calls=2,
        )
        breaker = SinkCircuitBreaker("async-transitions", config)

        state_history: list[CircuitState] = []

        async def observer() -> None:
            for _ in range(100):
                state_history.append(breaker.state)
                await asyncio.sleep(0.001)

        async def operator() -> None:
            for i in range(50):
                breaker.should_allow()
                if i % 4 == 0:
                    breaker.record_failure()
                else:
                    breaker.record_success()
                await asyncio.sleep(0.001)

        await asyncio.gather(observer(), operator(), operator(), operator())

        # All observed states must be valid
        for state in state_history:
            assert state in (
                CircuitState.CLOSED,
                CircuitState.OPEN,
                CircuitState.HALF_OPEN,
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_half_open_call_limit_enforced_async(self) -> None:
        """Half-open call limit is enforced under concurrent async access."""
        config = SinkCircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
            half_open_max_calls=3,
        )
        breaker = SinkCircuitBreaker("limit-sink", config)

        # Force into HALF_OPEN
        breaker.record_failure()
        breaker.should_allow()  # Transitions to HALF_OPEN, counts as call 1
        assert breaker.state == CircuitState.HALF_OPEN

        allowed_count = 0
        lock = asyncio.Lock()

        async def try_call() -> bool:
            nonlocal allowed_count
            allowed = breaker.should_allow()
            if allowed:
                async with lock:
                    allowed_count += 1
            return allowed

        # Launch 20 concurrent tasks trying to get through
        tasks = [asyncio.create_task(try_call()) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # With locking, only remaining calls should be allowed (3 - 1 = 2)
        # First call was the transition, so only 2 more allowed
        assert sum(results) == 2, f"Expected 2 allowed calls but got {sum(results)}"
        assert allowed_count == 2
