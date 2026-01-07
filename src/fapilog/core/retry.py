"""
Simplified retry logic tailored for logging sinks.

Provides exponential backoff with jitter and a protocol that allows swapping in
alternative retry implementations (for example Tenacity) without coupling the
core package to extra dependencies.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from .errors import (
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    NetworkError,
    TimeoutError,
)

T = TypeVar("T")


@runtime_checkable
class RetryCallable(Protocol):
    """Protocol for retry implementations."""

    async def __call__(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T: ...


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    timeout_per_attempt: float | None = None
    retryable_exceptions: list[type[Exception]] = field(default_factory=list)
    jitter: str = "equal"  # "equal" (default) or "full"

    def __post_init__(self) -> None:
        if not self.retryable_exceptions:
            self.retryable_exceptions = [
                NetworkError,
                TimeoutError,
                ConnectionError,
                asyncio.TimeoutError,
                OSError,
            ]

        if self.jitter not in {"equal", "full"}:
            raise ValueError("jitter must be 'equal' or 'full'")


@dataclass
class RetryStats:
    """Statistics for retry operations."""

    attempt_count: int = 0
    total_delay: float = 0.0
    start_time: float = 0.0
    end_time: float | None = None
    last_exception: Exception | None = None
    attempt_times: list[float] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        """Total duration including delays."""
        end = self.end_time or time.time()
        return end - self.start_time


class RetryExhaustedError(FapilogError):
    """Error raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str,
        original_exception: Exception | None = None,
        retry_stats: RetryStats | None = None,
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
    """Async retry mechanism with exponential backoff and jitter."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()
        self.stats = RetryStats()

    async def __call__(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        return await self.retry(func, *args, **kwargs)

    async def retry(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        self.stats = RetryStats()
        self.stats.start_time = time.time()

        last_exception: Exception | None = None

        for attempt in range(self.config.max_attempts):
            self.stats.attempt_count = attempt + 1
            attempt_start = time.time()

            try:
                if self.config.timeout_per_attempt:
                    result = await asyncio.wait_for(
                        func(*args, **kwargs), timeout=self.config.timeout_per_attempt
                    )
                else:
                    result = await func(*args, **kwargs)

                self.stats.end_time = time.time()
                self.stats.attempt_times.append(time.time() - attempt_start)
                return result

            except Exception as exc:  # pragma: no cover - exercised in tests
                last_exception = exc
                self.stats.last_exception = exc
                self.stats.attempt_times.append(time.time() - attempt_start)

                if not self._is_retryable_exception(exc):
                    raise

                if attempt == self.config.max_attempts - 1:
                    break

                delay = self._calculate_delay(attempt)
                self.stats.total_delay += delay
                await asyncio.sleep(delay)

        self.stats.end_time = time.time()

        error_msg = (
            f"All {self.stats.attempt_count} retry attempts exhausted. "
            f"Total duration: {self.stats.total_duration:.2f}s, "
            f"Total delay: {self.stats.total_delay:.2f}s"
        )

        if last_exception:
            error_msg += f". Last error: {last_exception}"

        raise RetryExhaustedError(
            error_msg,
            original_exception=last_exception,
            retry_stats=self.stats,
            attempt_count=self.stats.attempt_count,
            total_duration=self.stats.total_duration,
            total_delay=self.stats.total_delay,
        )

    def _is_retryable_exception(self, exception: Exception) -> bool:
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        if isinstance(exception, FapilogError):
            retryable_categories = {
                ErrorCategory.NETWORK,
                ErrorCategory.TIMEOUT,
                ErrorCategory.EXTERNAL,
                ErrorCategory.IO,
            }
            return exception.context.category in retryable_categories

        return False

    def _calculate_delay(self, attempt: int) -> float:
        delay = self.config.base_delay * (self.config.multiplier**attempt)
        delay = min(delay, self.config.max_delay)

        if self.config.jitter == "full":
            return max(0.0, random.uniform(0, delay))

        # Equal jitter: 50%-100% of computed delay
        return max(0.0, delay * random.uniform(0.5, 1.0))

    def get_stats(self) -> dict[str, Any]:
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
                "multiplier": self.config.multiplier,
                "jitter": self.config.jitter,
            },
        }


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    """Convenience function for retrying async operations."""
    retrier = AsyncRetrier(config)
    return await retrier.retry(func, *args, **kwargs)
