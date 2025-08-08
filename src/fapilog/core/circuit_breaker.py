"""
Circuit Breaker Patterns for Fapilog v3.

This module provides circuit breaker implementations to prevent cascading failures
and enable graceful degradation in async operations.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, cast
from uuid import uuid4

from .errors import (
    ErrorCategory,
    ErrorSeverity,
    ExternalServiceError,
    FapilogError,
)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    # Failure threshold
    failure_threshold: int = 5  # Number of failures before opening
    failure_rate_threshold: float = 0.5  # Failure rate threshold (0.0-1.0)

    # Timeout settings
    timeout: Optional[float] = 30.0  # Timeout for protected operations (None disables)
    open_timeout: float = 60.0  # How long to keep circuit open

    # Recovery settings
    success_threshold: int = 3  # Successes needed to close circuit
    half_open_max_calls: int = 10  # Max calls in half-open state

    # Monitoring
    window_size: int = 100  # Size of sliding window for statistics
    min_calls: int = 10  # Minimum calls before circuit can open


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeouts: int = 0
    circuit_open_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

    # Sliding window for rate calculation
    call_history: List[bool] = field(
        default_factory=list
    )  # True = success, False = failure

    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate."""
        if not self.call_history:
            return 0.0

        failures = sum(1 for success in self.call_history if not success)
        return failures / len(self.call_history)

    @property
    def success_rate(self) -> float:
        """Calculate current success rate."""
        return 1.0 - self.failure_rate


class CircuitBreakerOpenError(FapilogError):
    """Error raised when circuit breaker is open."""

    def __init__(
        self, service_name: str, message: Optional[str] = None, **kwargs: Any
    ) -> None:
        if message is None:
            message = f"Circuit breaker is open for service: {service_name}"

        super().__init__(
            message,
            category=ErrorCategory.EXTERNAL,
            severity=ErrorSeverity.HIGH,
            service_name=service_name,
            **kwargs,
        )


class AsyncCircuitBreaker:
    """
    Async circuit breaker for preventing cascading failures.

    The circuit breaker monitors the failure rate of operations and prevents
    calls when the failure rate exceeds the threshold. It provides:

    - Automatic failure detection and circuit opening
    - Configurable timeouts and thresholds
    - Half-open state for testing recovery
    - Comprehensive statistics and monitoring
    - Integration with Fapilog error hierarchy
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[..., Awaitable[T]]] = None,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            name: Unique name for this circuit breaker
            config: Circuit breaker configuration
            fallback: Optional fallback function when circuit is open
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback

        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.next_attempt_time: Optional[float] = None
        self.half_open_calls = 0

        # Statistics
        self.stats = CircuitBreakerStats()

        # Thread safety
        self._lock = asyncio.Lock()

        # Unique identifier
        self.circuit_id = str(uuid4())

    async def __aenter__(self) -> "AsyncCircuitBreaker":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        pass

    async def call(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is open
            TimeoutError: When operation times out
            Any exception from the protected function
        """
        # Simple state check without complex locking
        if self.state == CircuitState.OPEN:
            current_time = time.time()
            if not (self.next_attempt_time and current_time >= self.next_attempt_time):
                # Circuit is open, try fallback or raise error
                if self.fallback:
                    try:
                        return cast(T, await self.fallback(*args, **kwargs))
                    except Exception:
                        self._simple_record_failure()
                        raise
                else:
                    error = CircuitBreakerOpenError(
                        self.name,
                        circuit_id=self.circuit_id,
                        failure_count=self.failure_count,
                        last_failure_time=self.last_failure_time,
                    )
                    self._simple_record_failure()
                    raise error

        # Execute the function with timeout
        try:
            if self.config.timeout:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=self.config.timeout
                )
            else:
                result = await func(*args, **kwargs)

            self._simple_record_success()
            return result

        except TimeoutError:
            self._simple_record_failure()
            # Re-raise the TimeoutError as-is (asyncio.wait_for raises built-in TimeoutError in Python 3.11+)
            raise

        except Exception as e:
            # Wrap in Fapilog error if not already
            if not isinstance(e, FapilogError):
                wrapped_error = ExternalServiceError(
                    f"Operation failed: {str(e)}",
                    service_name=self.name,
                    circuit_id=self.circuit_id,
                    cause=e,
                )
                await self._record_failure(wrapped_error)
                raise wrapped_error from e
            else:
                await self._record_failure(e)
                raise e

    async def _can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        current_time = time.time()

        if self.state == CircuitState.CLOSED:
            return True

        elif self.state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if self.next_attempt_time and current_time >= self.next_attempt_time:
                await self._transition_to_half_open()
                return True
            return False

        elif self.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self.half_open_calls < self.config.half_open_max_calls

        # All states are covered above, this should never be reached
        raise AssertionError(f"Unknown circuit state: {self.state}")  # pragma: no cover

    async def _record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.last_success_time = time.time()

            # Update sliding window
            self.stats.call_history.append(True)
            if len(self.stats.call_history) > self.config.window_size:
                self.stats.call_history.pop(0)

            # Handle state transitions
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    await self._transition_to_closed()
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

    async def _record_failure(self, error: Exception) -> None:
        """Record failed operation."""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.last_failure_time = time.time()

            # Update sliding window
            self.stats.call_history.append(False)
            if len(self.stats.call_history) > self.config.window_size:
                self.stats.call_history.pop(0)

            # Count specific error types
            if isinstance(error, TimeoutError):
                self.stats.timeouts += 1

            # Handle state transitions
            if self.state == CircuitState.CLOSED:
                self.failure_count += 1
                await self._check_failure_threshold()
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open state reopens circuit
                await self._transition_to_open()

    async def _check_failure_threshold(self) -> None:
        """Check if failure threshold is exceeded."""
        # Need minimum number of calls before opening circuit
        if self.stats.total_calls < self.config.min_calls:
            return

        # Check failure count threshold
        if self.failure_count >= self.config.failure_threshold:
            await self._transition_to_open()
            return

        # Check failure rate threshold
        if (
            len(self.stats.call_history) >= self.config.min_calls
            and self.stats.failure_rate >= self.config.failure_rate_threshold
        ):
            await self._transition_to_open()

    async def _transition_to_open(self) -> None:
        """Transition circuit to open state."""
        self.state = CircuitState.OPEN
        self.stats.circuit_open_count += 1
        current_time = time.time()
        self.last_failure_time = current_time
        self.next_attempt_time = current_time + self.config.open_timeout

        # Reset counters
        self.half_open_calls = 0
        self.success_count = 0

    async def _transition_to_half_open(self) -> None:
        """Transition circuit to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0

    async def _transition_to_closed(self) -> None:
        """Transition circuit to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.success_count = 0
        self.next_attempt_time = None

    def _simple_record_success(self) -> None:
        """Record successful operation without async locks."""
        self.stats.total_calls += 1
        self.stats.successful_calls += 1
        self.stats.last_success_time = time.time()

        # Handle state transitions
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _simple_record_failure(self) -> None:
        """Record failed operation without async locks."""
        self.stats.total_calls += 1
        self.stats.failed_calls += 1
        self.stats.last_failure_time = time.time()
        self.failure_count += 1

        # Check if circuit should open
        if (
            self.state == CircuitState.CLOSED
            and self.failure_count >= self.config.failure_threshold
        ):
            self.state = CircuitState.OPEN
            self.next_attempt_time = time.time() + self.config.open_timeout

    async def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.next_attempt_time = None
            self.half_open_calls = 0

            # Reset statistics
            self.stats = CircuitBreakerStats()

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "circuit_id": self.circuit_id,
            "state": self.state.value,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "timeouts": self.stats.timeouts,
                "circuit_open_count": self.stats.circuit_open_count,
                "failure_rate": self.stats.failure_rate,
                "success_rate": self.stats.success_rate,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "timeout": self.config.timeout,
                "open_timeout": self.config.open_timeout,
                "success_threshold": self.config.success_threshold,
            },
        }

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers with centralized monitoring.

    This manager provides:
    - Centralized circuit breaker registration and lookup
    - Global circuit breaker statistics and monitoring
    - Bulk operations and management
    - Integration with container lifecycle
    """

    def __init__(self) -> None:
        """Initialize circuit breaker manager."""
        self._circuit_breakers: Dict[str, AsyncCircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[..., Awaitable[T]]] = None,
    ) -> AsyncCircuitBreaker:
        """
        Get existing circuit breaker or create new one.

        Args:
            name: Circuit breaker name
            config: Configuration for new circuit breaker
            fallback: Fallback function for new circuit breaker

        Returns:
            Circuit breaker instance
        """
        async with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = AsyncCircuitBreaker(
                    name, config, fallback
                )
            return self._circuit_breakers[name]

    async def get(self, name: str) -> Optional[AsyncCircuitBreaker]:
        """Get circuit breaker by name."""
        return self._circuit_breakers.get(name)

    async def remove(self, name: str) -> bool:
        """Remove circuit breaker by name."""
        async with self._lock:
            if name in self._circuit_breakers:
                del self._circuit_breakers[name]
                return True
            return False

    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        async with self._lock:
            for cb in self._circuit_breakers.values():
                await cb.reset()

    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}

    def list_circuit_breakers(self) -> List[str]:
        """List all circuit breaker names."""
        return list(self._circuit_breakers.keys())

    async def cleanup(self) -> None:
        """Clean up all circuit breakers."""
        async with self._lock:
            self._circuit_breakers.clear()


# Global circuit breaker manager instance
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


async def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager."""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager


async def circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable[..., Awaitable[T]]] = None,
) -> AsyncCircuitBreaker:
    """
    Get or create a circuit breaker.

    Args:
        name: Circuit breaker name
        config: Configuration
        fallback: Fallback function

    Returns:
        Circuit breaker instance
    """
    manager = await get_circuit_breaker_manager()
    return await manager.get_or_create(name, config, fallback)
