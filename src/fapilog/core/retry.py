"""
Retry Mechanism with Exponential Backoff for Fapilog v3.

This module provides comprehensive retry functionality with exponential backoff,
jitter, and integration with the circuit breaker patterns for async operations.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, List, Optional, Type, TypeVar

from .errors import (
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    NetworkError,
    TimeoutError,
)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    """Retry strategy types."""

    FIXED = "fixed"  # Fixed delay between retries
    LINEAR = "linear"  # Linear backoff (delay increases linearly)
    EXPONENTIAL = "exponential"  # Exponential backoff
    FIBONACCI = "fibonacci"  # Fibonacci sequence backoff


class JitterType(str, Enum):
    """Types of jitter for retry delays."""

    NONE = "none"  # No jitter
    FULL = "full"  # Full jitter (0 to computed delay)
    EQUAL = "equal"  # Equal jitter (50% to 100% of computed delay)
    DECORRELATED = "decorrelated"  # Decorrelated jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    # Basic retry settings
    max_attempts: int = 3  # Maximum number of retry attempts
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay between retries

    # Backoff strategy
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    multiplier: float = 2.0  # Multiplier for exponential/linear backoff

    # Jitter settings
    jitter: JitterType = JitterType.EQUAL
    jitter_factor: float = 0.1  # Jitter randomization factor

    # Timeout settings
    timeout_per_attempt: Optional[float] = None  # Timeout for each attempt
    total_timeout: Optional[float] = None  # Total timeout for all attempts

    # Error handling
    retryable_exceptions: List[Type[Exception]] = field(default_factory=list)
    non_retryable_exceptions: List[Type[Exception]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set default retryable exceptions."""
        if not self.retryable_exceptions:
            self.retryable_exceptions = [
                NetworkError,
                TimeoutError,
                ConnectionError,
                asyncio.TimeoutError,
                OSError,  # Includes socket errors
            ]

        if not self.non_retryable_exceptions:
            self.non_retryable_exceptions = [
                ValueError,
                TypeError,
                AttributeError,
                ImportError,
                ModuleNotFoundError,
            ]


@dataclass
class RetryStats:
    """Statistics for retry operations."""

    attempt_count: int = 0
    total_delay: float = 0.0
    start_time: float = 0.0
    end_time: Optional[float] = None
    last_exception: Optional[Exception] = None
    attempt_times: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize attempt times list."""
        if not self.attempt_times:
            self.attempt_times = []

    @property
    def total_duration(self) -> float:
        """Get total duration of retry operation."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time


class RetryExhaustedError(FapilogError):
    """Error raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None,
        retry_stats: Optional[RetryStats] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            cause=original_exception,
            **kwargs,
        )
        self.retry_stats = retry_stats


class AsyncRetrier:
    """
    Async retry mechanism with exponential backoff and jitter.

    This class provides comprehensive retry functionality including:
    - Multiple backoff strategies (exponential, linear, fibonacci, fixed)
    - Configurable jitter to prevent thundering herd
    - Timeout management per attempt and total operation
    - Exception classification for retry decisions
    - Comprehensive statistics and monitoring
    - Integration with Fapilog error hierarchy
    """

    def __init__(self, config: Optional[RetryConfig] = None) -> None:
        """
        Initialize retrier with configuration.

        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        self.stats = RetryStats()

    async def __call__(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryExhaustedError: When all retry attempts are exhausted
            Any non-retryable exception from the function
        """
        return await self.retry(func, *args, **kwargs)

    async def retry(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            RetryExhaustedError: When all retry attempts are exhausted
            Any non-retryable exception from the function
        """
        self.stats = RetryStats()
        self.stats.start_time = time.time()

        last_exception: Optional[Exception] = None

        for attempt in range(self.config.max_attempts):
            self.stats.attempt_count = attempt + 1
            attempt_start = time.time()

            try:
                # Apply per-attempt timeout if configured
                if self.config.timeout_per_attempt:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=self.config.timeout_per_attempt
                    )
                else:
                    result = await func(*args, **kwargs)

                # Success - record stats and return
                self.stats.end_time = time.time()
                self.stats.attempt_times.append(time.time() - attempt_start)
                return result

            except Exception as e:
                last_exception = e
                self.stats.last_exception = e
                self.stats.attempt_times.append(time.time() - attempt_start)

                # Check if exception is retryable
                if not self._is_retryable_exception(e):
                    # Non-retryable exception, raise immediately
                    raise e

                # Check total timeout
                if self.config.total_timeout:
                    elapsed = time.time() - self.stats.start_time
                    if elapsed >= self.config.total_timeout:
                        break

                # If this was the last attempt, break
                if attempt == self.config.max_attempts - 1:
                    break

                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                self.stats.total_delay += delay

                # Check if delay would exceed total timeout
                if self.config.total_timeout:
                    elapsed = time.time() - self.stats.start_time
                    if elapsed + delay >= self.config.total_timeout:
                        break

                # Wait before next attempt
                await asyncio.sleep(delay)

        # All attempts exhausted
        self.stats.end_time = time.time()

        # Create comprehensive error message
        error_msg = (
            f"All {self.stats.attempt_count} retry attempts exhausted. "
            f"Total duration: {self.stats.total_duration:.2f}s, "
            f"Total delay: {self.stats.total_delay:.2f}s"
        )

        if last_exception:
            error_msg += f". Last error: {str(last_exception)}"

        raise RetryExhaustedError(
            error_msg,
            original_exception=last_exception,
            retry_stats=self.stats,
            attempt_count=self.stats.attempt_count,
            total_duration=self.stats.total_duration,
            total_delay=self.stats.total_delay,
        )

    def _is_retryable_exception(self, exception: Exception) -> bool:
        """
        Check if exception is retryable based on configuration.

        Args:
            exception: Exception to check

        Returns:
            True if exception is retryable
        """
        # Check non-retryable exceptions first
        for exc_type in self.config.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Check retryable exceptions
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        # If not explicitly configured, check for common retryable patterns
        if isinstance(exception, (ConnectionError, OSError, asyncio.TimeoutError)):
            return True

        # If it's a FapilogError, check the category and recovery strategy
        if isinstance(exception, FapilogError):
            retryable_categories = {
                ErrorCategory.NETWORK,
                ErrorCategory.TIMEOUT,
                ErrorCategory.EXTERNAL,
                ErrorCategory.IO,
            }
            return exception.context.category in retryable_categories

        # Default to not retryable
        return False

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.

        Args:
            attempt: Zero-based attempt number

        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.FIXED:
            delay = self.config.base_delay

        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay * (attempt + 1) * self.config.multiplier

        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (self.config.multiplier**attempt)

        elif self.config.strategy == RetryStrategy.FIBONACCI:
            delay = self.config.base_delay * self._fibonacci(attempt + 1)

        else:
            # All strategies covered above, this should never be reached
            raise AssertionError(
                f"Unknown retry strategy: {self.config.strategy}"
            )  # pragma: no cover

        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)

        # Apply jitter
        delay = self._apply_jitter(delay, attempt)

        return max(0.0, delay)

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 0:
            return 0
        elif n == 1:
            return 1
        else:
            a, b = 0, 1
            for _ in range(2, n + 1):
                a, b = b, a + b
            return b

    def _apply_jitter(self, delay: float, attempt: int) -> float:
        """
        Apply jitter to delay based on configuration.

        Args:
            delay: Base delay
            attempt: Attempt number

        Returns:
            Delay with jitter applied
        """
        if self.config.jitter == JitterType.NONE:
            return delay

        elif self.config.jitter == JitterType.FULL:
            # Random delay between 0 and computed delay
            return random.uniform(0, delay)

        elif self.config.jitter == JitterType.EQUAL:
            # Random delay between 50% and 100% of computed delay
            return delay * random.uniform(0.5, 1.0)

        elif self.config.jitter == JitterType.DECORRELATED:
            # Decorrelated jitter based on previous delay
            if attempt == 0:
                return delay * random.uniform(0.5, 1.0)
            else:
                # Use some of the previous delay calculation
                base = self.config.base_delay
                return random.uniform(base, delay * 3)

        # All jitter types covered above, this should never be reached
        raise AssertionError(
            f"Unknown jitter type: {self.config.jitter}"
        )  # pragma: no cover

    def get_stats(self) -> dict:
        """Get retry statistics."""
        return {
            "attempt_count": self.stats.attempt_count,
            "total_delay": self.stats.total_delay,
            "total_duration": self.stats.total_duration,
            "success": self.stats.end_time is not None
            and self.stats.last_exception is None,
            "last_exception": str(self.stats.last_exception)
            if self.stats.last_exception
            else None,
            "attempt_times": self.stats.attempt_times,
            "config": {
                "max_attempts": self.config.max_attempts,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay,
                "strategy": self.config.strategy.value,
                "jitter": self.config.jitter.value,
            },
        }


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any,
) -> T:
    """
    Convenience function for retrying async operations.

    Args:
        func: Async function to retry
        *args: Function arguments
        config: Retry configuration
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryExhaustedError: When all retry attempts are exhausted
    """
    retrier = AsyncRetrier(config)
    return await retrier.retry(func, *args, **kwargs)


class retry:
    """
    Decorator for adding retry functionality to async functions.

    Usage:
        @retry(max_attempts=3, base_delay=1.0)
        async def my_function():
            # function implementation
            pass
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        multiplier: float = 2.0,
        jitter: JitterType = JitterType.EQUAL,
        timeout_per_attempt: Optional[float] = None,
        total_timeout: Optional[float] = None,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        non_retryable_exceptions: Optional[List[Type[Exception]]] = None,
    ):
        """Initialize retry decorator with configuration."""
        self.config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            strategy=strategy,
            multiplier=multiplier,
            jitter=jitter,
            timeout_per_attempt=timeout_per_attempt,
            total_timeout=total_timeout,
            retryable_exceptions=retryable_exceptions or [],
            non_retryable_exceptions=non_retryable_exceptions or [],
        )

    def __call__(
        self, func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        """Apply retry logic to function."""

        async def wrapper(*args: Any, **kwargs: Any) -> T:
            retrier = AsyncRetrier(self.config)
            return await retrier.retry(func, *args, **kwargs)

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__

        return wrapper


# Predefined retry configurations for common scenarios
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL,
    multiplier=2.0,
    jitter=JitterType.EQUAL,
    timeout_per_attempt=10.0,
    retryable_exceptions=[NetworkError, ConnectionError, OSError, asyncio.TimeoutError],
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=10.0,
    strategy=RetryStrategy.EXPONENTIAL,
    multiplier=1.5,
    jitter=JitterType.FULL,
    timeout_per_attempt=30.0,
)

EXTERNAL_SERVICE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL,
    multiplier=2.0,
    jitter=JitterType.DECORRELATED,
    timeout_per_attempt=15.0,
    total_timeout=120.0,
)
