"""
Graceful Degradation with Fallback Mechanisms for Fapilog v3.

This module provides fallback patterns for graceful degradation when primary
operations fail, ensuring system resilience and availability.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, cast
from uuid import uuid4

from .errors import (
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
)

T = TypeVar("T")


class FallbackStrategy(str, Enum):
    """Fallback strategy types."""

    STATIC_VALUE = "static_value"  # Return a static fallback value
    FUNCTION_CALL = "function_call"  # Call a fallback function
    CACHE_LOOKUP = "cache_lookup"  # Look up cached value
    DEGRADED_SERVICE = "degraded_service"  # Use degraded service functionality
    CIRCUIT_BREAKER = "circuit_breaker"  # Use circuit breaker fallback
    CHAIN = "chain"  # Chain multiple fallback strategies


class FallbackTrigger(str, Enum):
    """Conditions that trigger fallback mechanisms."""

    EXCEPTION = "exception"  # Any exception occurred
    TIMEOUT = "timeout"  # Operation timed out
    CIRCUIT_OPEN = "circuit_open"  # Circuit breaker is open
    HIGH_LATENCY = "high_latency"  # Operation took too long
    RATE_LIMIT = "rate_limit"  # Rate limit exceeded
    CUSTOM = "custom"  # Custom condition


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""

    # Strategy configuration
    strategy: FallbackStrategy = FallbackStrategy.STATIC_VALUE
    triggers: List[FallbackTrigger] = field(default_factory=list)

    # Timing configuration
    timeout: Optional[float] = None  # Timeout before fallback
    latency_threshold: Optional[float] = None  # Latency threshold for fallback

    # Static value fallback
    static_value: Any = None

    # Function fallback
    fallback_function: Optional[Callable[..., Awaitable[T]]] = None

    # Cache configuration
    cache_key_generator: Optional[Callable[..., str]] = None
    cache_ttl: Optional[float] = None

    # Monitoring
    track_fallback_usage: bool = True
    log_fallback_events: bool = True

    def __post_init__(self) -> None:
        """Set default triggers."""
        if not self.triggers:
            self.triggers = [FallbackTrigger.EXCEPTION, FallbackTrigger.TIMEOUT]


@dataclass
class FallbackStats:
    """Statistics for fallback operations."""

    total_calls: int = 0
    fallback_calls: int = 0
    primary_success: int = 0
    fallback_success: int = 0
    fallback_failures: int = 0

    # Timing statistics
    average_primary_latency: float = 0.0
    average_fallback_latency: float = 0.0

    # Trigger statistics
    trigger_counts: Dict[FallbackTrigger, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize trigger counts."""
        if not self.trigger_counts:
            self.trigger_counts = dict.fromkeys(FallbackTrigger, 0)

    @property
    def fallback_rate(self) -> float:
        """Calculate fallback usage rate."""
        if self.total_calls == 0:
            return 0.0
        return self.fallback_calls / self.total_calls

    @property
    def primary_success_rate(self) -> float:
        """Calculate primary operation success rate."""
        primary_attempts = self.total_calls - self.fallback_calls
        if primary_attempts == 0:
            return 0.0
        return self.primary_success / primary_attempts if primary_attempts > 0 else 0.0


class FallbackError(FapilogError):
    """Error raised when fallback mechanisms fail."""

    def __init__(
        self,
        message: str,
        primary_error: Optional[Exception] = None,
        fallback_error: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            **kwargs,
        )
        self.primary_error = primary_error
        self.fallback_error = fallback_error


class FallbackProvider(ABC):
    """Abstract base class for fallback providers."""

    @abstractmethod
    async def provide_fallback(
        self,
        *args: Any,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Provide fallback value or behavior.

        Args:
            *args: Original function arguments
            error: Error that triggered fallback
            context: Additional context information
            **kwargs: Original function keyword arguments

        Returns:
            Fallback value or result
        """
        pass


class StaticValueFallback(FallbackProvider):
    """Fallback provider that returns a static value."""

    def __init__(self, value: Any) -> None:
        """
        Initialize with static value.

        Args:
            value: Static value to return as fallback
        """
        self.value = value

    async def provide_fallback(
        self,
        *args: Any,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Return the static fallback value."""
        return self.value


class FunctionFallback(FallbackProvider):
    """Fallback provider that calls a fallback function."""

    def __init__(self, fallback_func: Callable[..., Awaitable[Any]]) -> None:
        """
        Initialize with fallback function.

        Args:
            fallback_func: Async function to call for fallback
        """
        self.fallback_func = fallback_func

    async def provide_fallback(
        self,
        *args: Any,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Call the fallback function."""
        return await self.fallback_func(*args, **kwargs)


class CacheFallback(FallbackProvider):
    """Fallback provider that uses cached values."""

    def __init__(
        self,
        cache: Dict[str, Any],
        key_generator: Callable[..., str],
        default_value: Any = None,
    ) -> None:
        """
        Initialize with cache and key generator.

        Args:
            cache: Cache dictionary
            key_generator: Function to generate cache keys
            default_value: Default value if cache miss
        """
        self.cache = cache
        self.key_generator = key_generator
        self.default_value = default_value

    async def provide_fallback(
        self,
        *args: Any,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Look up cached value."""
        cache_key = self.key_generator(*args, **kwargs)
        return self.cache.get(cache_key, self.default_value)


class ChainedFallback(FallbackProvider):
    """Fallback provider that chains multiple fallback providers."""

    def __init__(self, providers: List[FallbackProvider]) -> None:
        """
        Initialize with list of fallback providers.

        Args:
            providers: List of fallback providers to try in order
        """
        self.providers = providers

    async def provide_fallback(
        self,
        *args: Any,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Try fallback providers in order."""
        last_error = error

        for provider in self.providers:
            try:
                return await provider.provide_fallback(
                    *args, error=last_error, context=context, **kwargs
                )
            except Exception as e:
                last_error = e
                continue

        # All fallback providers failed
        raise FallbackError(
            "All fallback providers failed",
            primary_error=error,
            fallback_error=last_error,
        )


class AsyncFallbackWrapper:
    """
    Async wrapper that provides fallback functionality for operations.

    This wrapper monitors primary operations and automatically triggers
    fallback mechanisms based on configured conditions like timeouts,
    exceptions, or custom triggers.
    """

    def __init__(
        self,
        name: str,
        fallback_provider: FallbackProvider,
        config: Optional[FallbackConfig] = None,
    ) -> None:
        """
        Initialize fallback wrapper.

        Args:
            name: Unique name for this fallback wrapper
            fallback_provider: Provider for fallback values/behavior
            config: Fallback configuration
        """
        self.name = name
        self.fallback_provider = fallback_provider
        self.config = config or FallbackConfig()

        # Statistics and monitoring
        self.stats = FallbackStats()
        self._lock = asyncio.Lock()

        # Cache for cache-based fallbacks
        self._cache: Dict[str, Any] = {}

        # Unique identifier
        self.wrapper_id = str(uuid4())

    async def execute(
        self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute function with fallback protection.

        Args:
            func: Primary async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Result from primary function or fallback

        Raises:
            FallbackError: When both primary and fallback fail
        """
        async with self._lock:
            self.stats.total_calls += 1

        start_time = time.time()

        try:
            # Try primary operation with timeout if configured
            if self.config.timeout:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=self.config.timeout
                )
            else:
                result = await func(*args, **kwargs)

            # Check latency threshold
            latency = time.time() - start_time
            if (
                self.config.latency_threshold
                and latency > self.config.latency_threshold
                and FallbackTrigger.HIGH_LATENCY in self.config.triggers
            ):
                # High latency detected, trigger fallback
                await self._trigger_fallback(
                    FallbackTrigger.HIGH_LATENCY, args, kwargs, latency=latency
                )
                return cast(T, await self._execute_fallback(*args, **kwargs))

            # Primary operation succeeded
            async with self._lock:
                self.stats.primary_success += 1
                self.stats.average_primary_latency = (
                    self.stats.average_primary_latency
                    * (self.stats.primary_success - 1)
                    + latency
                ) / self.stats.primary_success

            # Cache result if caching is configured
            await self._cache_result(result, *args, **kwargs)

            return result

        except asyncio.TimeoutError as e:
            if FallbackTrigger.TIMEOUT in self.config.triggers:
                await self._trigger_fallback(
                    FallbackTrigger.TIMEOUT, args, kwargs, error=e
                )
                return cast(T, await self._execute_fallback(*args, error=e, **kwargs))
            raise

        except Exception as e:
            if FallbackTrigger.EXCEPTION in self.config.triggers:
                await self._trigger_fallback(
                    FallbackTrigger.EXCEPTION, args, kwargs, error=e
                )
                return cast(T, await self._execute_fallback(*args, error=e, **kwargs))
            raise

    async def _execute_fallback(
        self, *args: Any, error: Optional[Exception] = None, **kwargs: Any
    ) -> Any:
        """Execute fallback mechanism."""
        fallback_start = time.time()

        async with self._lock:
            self.stats.fallback_calls += 1

        try:
            context = {
                "wrapper_name": self.name,
                "wrapper_id": self.wrapper_id,
                "execution_time": time.time(),
            }

            result = await self.fallback_provider.provide_fallback(
                *args, error=error, context=context, **kwargs
            )

            # Record successful fallback
            fallback_latency = time.time() - fallback_start
            async with self._lock:
                self.stats.fallback_success += 1
                self.stats.average_fallback_latency = (
                    self.stats.average_fallback_latency
                    * (self.stats.fallback_success - 1)
                    + fallback_latency
                ) / self.stats.fallback_success

            return result

        except Exception as fallback_error:
            async with self._lock:
                self.stats.fallback_failures += 1

            raise FallbackError(
                f"Both primary operation and fallback failed for {self.name}",
                primary_error=error,
                fallback_error=fallback_error,
                wrapper_name=self.name,
                wrapper_id=self.wrapper_id,
            ) from error

    async def _trigger_fallback(
        self, trigger: FallbackTrigger, args: tuple, kwargs: dict, **context: Any
    ) -> None:
        """Record fallback trigger event."""
        async with self._lock:
            self.stats.trigger_counts[trigger] += 1

        if self.config.log_fallback_events:
            # Log fallback event (implementation would integrate with logging system)
            pass

    async def _cache_result(self, result: Any, *args: Any, **kwargs: Any) -> None:
        """Cache result if caching is configured."""
        if (
            self.config.cache_key_generator
            and self.config.strategy == FallbackStrategy.CACHE_LOOKUP
        ):
            cache_key = self.config.cache_key_generator(*args, **kwargs)
            self._cache[cache_key] = result

            # TODO: Implement TTL-based cache expiration

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        return {
            "name": self.name,
            "wrapper_id": self.wrapper_id,
            "stats": {
                "total_calls": self.stats.total_calls,
                "fallback_calls": self.stats.fallback_calls,
                "primary_success": self.stats.primary_success,
                "fallback_success": self.stats.fallback_success,
                "fallback_failures": self.stats.fallback_failures,
                "fallback_rate": self.stats.fallback_rate,
                "primary_success_rate": self.stats.primary_success_rate,
                "average_primary_latency": self.stats.average_primary_latency,
                "average_fallback_latency": self.stats.average_fallback_latency,
                "trigger_counts": dict(self.stats.trigger_counts),
            },
            "config": {
                "strategy": self.config.strategy.value,
                "triggers": [t.value for t in self.config.triggers],
                "timeout": self.config.timeout,
                "latency_threshold": self.config.latency_threshold,
            },
        }

    async def reset_stats(self) -> None:
        """Reset fallback statistics."""
        async with self._lock:
            self.stats = FallbackStats()


class FallbackManager:
    """
    Manager for multiple fallback wrappers with centralized monitoring.

    This manager provides:
    - Centralized fallback wrapper registration and lookup
    - Global fallback statistics and monitoring
    - Bulk operations and management
    - Integration with container lifecycle
    """

    def __init__(self) -> None:
        """Initialize fallback manager."""
        self._fallback_wrappers: Dict[str, AsyncFallbackWrapper] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        name: str,
        fallback_provider: FallbackProvider,
        config: Optional[FallbackConfig] = None,
    ) -> AsyncFallbackWrapper:
        """
        Register a new fallback wrapper.

        Args:
            name: Unique name for the wrapper
            fallback_provider: Fallback provider
            config: Fallback configuration

        Returns:
            Registered fallback wrapper
        """
        async with self._lock:
            if name in self._fallback_wrappers:
                raise ValueError(f"Fallback wrapper '{name}' already registered")

            wrapper = AsyncFallbackWrapper(name, fallback_provider, config)
            self._fallback_wrappers[name] = wrapper
            return wrapper

    async def get(self, name: str) -> Optional[AsyncFallbackWrapper]:
        """Get fallback wrapper by name."""
        return self._fallback_wrappers.get(name)

    async def unregister(self, name: str) -> bool:
        """Remove fallback wrapper by name."""
        async with self._lock:
            if name in self._fallback_wrappers:
                del self._fallback_wrappers[name]
                return True
            return False

    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all fallback wrappers."""
        return {
            name: wrapper.get_stats()
            for name, wrapper in self._fallback_wrappers.items()
        }

    async def reset_all_stats(self) -> None:
        """Reset statistics for all fallback wrappers."""
        for wrapper in self._fallback_wrappers.values():
            await wrapper.reset_stats()

    def list_fallback_wrappers(self) -> List[str]:
        """List all fallback wrapper names."""
        return list(self._fallback_wrappers.keys())

    async def cleanup(self) -> None:
        """Clean up all fallback wrappers."""
        async with self._lock:
            self._fallback_wrappers.clear()


class fallback:
    """
    Decorator for adding fallback functionality to async functions.

    Usage:
        @fallback(StaticValueFallback(None), timeout=10.0)
        async def my_function():
            # function implementation
            pass
    """

    def __init__(
        self,
        fallback_provider: FallbackProvider,
        name: Optional[str] = None,
        config: Optional[FallbackConfig] = None,
    ):
        """Initialize fallback decorator."""
        self.fallback_provider = fallback_provider
        self.name = name
        self.config = config

    def __call__(
        self, func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        """Apply fallback logic to function."""
        wrapper_name = self.name or f"{func.__name__}_fallback"
        wrapper = AsyncFallbackWrapper(
            wrapper_name, self.fallback_provider, self.config
        )

        async def decorated(*args: Any, **kwargs: Any) -> T:
            return await wrapper.execute(func, *args, **kwargs)

        # Preserve function metadata
        decorated.__name__ = func.__name__
        decorated.__doc__ = func.__doc__
        decorated.__annotations__ = func.__annotations__

        return decorated


# Global fallback manager instance
_fallback_manager: Optional[FallbackManager] = None


async def get_fallback_manager() -> FallbackManager:
    """Get global fallback manager."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = FallbackManager()
    return _fallback_manager


async def with_fallback(
    name: str,
    fallback_provider: FallbackProvider,
    config: Optional[FallbackConfig] = None,
) -> AsyncFallbackWrapper:
    """
    Get or create a fallback wrapper.

    Args:
        name: Wrapper name
        fallback_provider: Fallback provider
        config: Configuration

    Returns:
        Fallback wrapper instance
    """
    manager = await get_fallback_manager()
    existing = await manager.get(name)
    if existing:
        return existing
    return await manager.register(name, fallback_provider, config)
