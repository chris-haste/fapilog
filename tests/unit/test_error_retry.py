"""
Tests for retry mechanisms and error integration.

Scope:
- Retry mechanisms with exponential backoff
- Integration between all error handling components
- Error propagation with context preservation
- Concurrent error handling
"""

import asyncio

import pytest

from fapilog.core import (
    AsyncRetrier,
    ComponentError,
    ContainerError,
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    NetworkError,
    RetryConfig,
    RetryExhaustedError,
    execution_context,
    retry_async,
)


class TestRetryMechanism:
    """Test retry mechanisms with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_successful_operation(self):
        """Succeeds immediately without delays."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=3, base_delay=0.0))

        async def successful_operation():
            return "success"

        result = await retrier.retry(successful_operation)
        assert result == "success"
        assert retrier.stats.attempt_count == 1
        assert retrier.stats.total_delay == 0.0

    @pytest.mark.asyncio
    async def test_retry_eventual_success(self):
        """Retries until success within max_attempts."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=3, base_delay=0.0))

        call_count = 0

        async def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await retrier.retry(eventually_successful_operation)
        assert result == "success"
        assert retrier.stats.attempt_count == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Raises RetryExhaustedError after max_attempts."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=2, base_delay=0.0))

        async def always_failing_operation():
            raise ConnectionError("Always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retrier.retry(always_failing_operation)

        assert retrier.stats.attempt_count == 2
        assert "All 2 retry attempts exhausted" in str(exc_info.value)
        assert (
            hasattr(exc_info.value, "retry_stats")
            and exc_info.value.retry_stats.attempt_count == 2
        )

    @pytest.mark.asyncio
    async def test_non_retryable_exception_bubbles(self):
        """ValueError should not be retried when not configured."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=3, retryable_exceptions=[]))

        async def bad_operation():
            raise ValueError("Do not retry")

        with pytest.raises(ValueError):
            await retrier.retry(bad_operation)
        assert retrier.stats.attempt_count == 1

    @pytest.mark.asyncio
    async def test_retry_timeout_per_attempt(self):
        """Times out each attempt and surfaces last timeout."""
        retrier = AsyncRetrier(
            RetryConfig(max_attempts=2, base_delay=0.0, timeout_per_attempt=0.01)
        )

        async def slow_operation():
            await asyncio.sleep(0.02)
            return "too slow"

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retrier.retry(slow_operation)

        stats = exc_info.value.retry_stats
        assert hasattr(stats, "attempt_count") and stats.attempt_count == 2
        assert isinstance(stats.last_exception, asyncio.TimeoutError)

    @pytest.mark.asyncio
    async def test_retry_async_convenience(self):
        """retry_async helper should delegate to AsyncRetrier."""
        attempt_count = 0

        async def test_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ConnectionError("First fails")
            return "retry_async_success"

        result = await retry_async(test_operation, config=RetryConfig(max_attempts=2))
        assert result == "retry_async_success"
        assert attempt_count == 2


class TestIntegration:
    """Test integration between all error handling components."""

    @pytest.mark.asyncio
    async def test_error_propagation_with_context(self):
        """Test error propagation while preserving context."""

        async def operation_level_3():
            # Deepest level - create error with current context
            error = ComponentError(
                "Deep operation failed", component_name="deep-component"
            )
            return error

        async def operation_level_2():
            error = await operation_level_3()
            # Add more context and re-raise
            enhanced_error = ContainerError(
                "Container operation failed", cause=error, container_id="test-container"
            )
            raise enhanced_error

        async def operation_level_1():
            try:
                await operation_level_2()
            except ContainerError as e:
                # Create final error with full context chain
                final_error = FapilogError(
                    "Top-level operation failed",
                    cause=e,
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.CRITICAL,
                )
                raise final_error from e

        # Execute with context
        async with execution_context(
            request_id="context-test-456",
            user_id="context-user",
            operation_name="nested_operations",
        ):
            with pytest.raises(FapilogError) as exc_info:
                await operation_level_1()

            error = exc_info.value
            assert error.context.request_id == "context-test-456"
            assert error.context.user_id == "context-user"
            assert error.context.category == ErrorCategory.SYSTEM
            assert error.context.severity == ErrorSeverity.CRITICAL

            # Check error chain
            assert isinstance(error.__cause__, ContainerError)
            assert isinstance(error.__cause__.__cause__, ComponentError)

    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test performance monitoring and timing in error handling."""
        async with execution_context(operation_name="performance_test") as ctx:
            start_time = ctx.start_time

            # Simulate some work
            await asyncio.sleep(0.01)

            # Check timing
            assert ctx.start_time == start_time
            assert ctx.duration is None  # Should be None until completed

        # After context exit
        assert ctx.is_completed
        assert isinstance(ctx.duration, float) and ctx.duration > 0.01

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self):
        """Test error handling under concurrent load."""

        async def concurrent_operation(operation_id: str):
            async with execution_context(
                operation_name=f"concurrent_op_{operation_id}",
                request_id=f"req-{operation_id}",
            ):
                if operation_id == "fail":
                    raise NetworkError(f"Operation {operation_id} failed")
                return f"success-{operation_id}"

        # Run multiple operations concurrently
        tasks = [
            concurrent_operation("1"),
            concurrent_operation("2"),
            concurrent_operation("fail"),
            concurrent_operation("3"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        assert results[0] == "success-1"
        assert results[1] == "success-2"
        assert isinstance(results[2], NetworkError)
        assert results[3] == "success-3"


# Configuration for pytest-asyncio
pytestmark = pytest.mark.asyncio
