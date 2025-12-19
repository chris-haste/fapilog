"""
Cache Fallback Provider for Fapilog v3.

This module provides fallback strategies for cache operations, ensuring
graceful degradation when cache operations fail.
"""

from typing import Any, Optional

from ..core.errors import CacheError, CacheMissError
from ..core.fallback import (
    FallbackConfig,
    FallbackStats,
    FallbackStrategy,
    FallbackTrigger,
)


class CacheFallbackProvider:
    """
    Fallback provider for cache operations.

    This provider implements fallback strategies when cache operations fail,
    ensuring the system can continue operating even when the cache is
    unavailable.
    """

    def __init__(
        self,
        cache: Any,
        default_value: Optional[Any] = None,
        fallback_config: Optional[FallbackConfig] = None,
    ) -> None:
        """
        Initialize cache fallback provider.

        Args:
            cache: Cache instance to use
            default_value: Default value to return on cache failures
            fallback_config: Configuration for fallback behavior
        """
        if fallback_config is None:
            fallback_config = FallbackConfig(
                strategy=FallbackStrategy.STATIC_VALUE,
                triggers=[FallbackTrigger.EXCEPTION],
                static_value=default_value,
            )

        self.cache = cache
        self.default_value = default_value
        self.fallback_config = fallback_config
        self.stats = FallbackStats()

    async def get_with_fallback(self, key: str) -> Any:
        """
        Get value from cache with fallback strategy.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value or fallback value

        Raises:
            CacheError: If both cache and fallback fail
        """
        try:
            # Try to get from cache
            value = await self.cache.aget(key)
            self.stats.primary_success += 1
            self.stats.total_calls += 1
            return value
        except CacheMissError:
            # Cache miss - use fallback value
            self.stats.fallback_calls += 1
            self.stats.total_calls += 1
            self.stats.trigger_counts[FallbackTrigger.EXCEPTION] += 1

            if self.fallback_config.static_value is not None:
                self.stats.fallback_success += 1
                return self.fallback_config.static_value
            else:
                # No fallback value available
                raise CacheError(f"No fallback value for cache key: {key}") from None

        except CacheError as e:
            # Cache failure - use fallback value and log
            self.stats.fallback_calls += 1
            self.stats.total_calls += 1
            self.stats.trigger_counts[FallbackTrigger.EXCEPTION] += 1

            if self.fallback_config.static_value is not None:
                self.stats.fallback_success += 1
                return self.fallback_config.static_value
            else:
                # Re-raise if no fallback available
                raise e

        except Exception as e:
            # Unexpected error - use fallback value
            self.stats.fallback_calls += 1
            self.stats.fallback_failures += 1
            self.stats.trigger_counts[FallbackTrigger.EXCEPTION] += 1

            if self.fallback_config.static_value is not None:
                self.stats.fallback_success += 1
                return self.fallback_config.static_value
            else:
                # Wrap unexpected error in CacheError
                raise CacheError(f"Unexpected cache error: {e}") from e

    async def set_with_fallback(self, key: str, value: Any) -> None:
        """
        Set value in cache with fallback strategy.

        Args:
            key: Cache key to set
            value: Value to cache
        """
        try:
            # Try to set in cache
            await self.cache.aset(key, value)
            self.stats.primary_success += 1
            self.stats.total_calls += 1
        except Exception:
            # Cache set failed - log but don't fail the operation
            self.stats.fallback_calls += 1
            self.stats.total_calls += 1
            self.stats.trigger_counts[FallbackTrigger.EXCEPTION] += 1

            # For set operations, we don't fail the operation
            # Just log that the cache set failed
            # The value will be available on next get (if not cached)
            pass

    async def get_stats(self) -> FallbackStats:
        """Get fallback statistics."""
        return self.stats

    def reset_stats(self) -> None:
        """Reset fallback statistics."""
        self.stats = FallbackStats()


class CacheFallbackWrapper:
    """
    Wrapper for cache operations with automatic fallback.

    This wrapper provides a simple interface for cache operations
    with automatic fallback when the cache fails.
    """

    def __init__(
        self,
        cache: Any,
        default_value: Optional[Any] = None,
        enable_fallback: bool = True,
    ) -> None:
        """
        Initialize cache fallback wrapper.

        Args:
            cache: Cache instance to wrap
            default_value: Default value for fallback
            enable_fallback: Whether to enable fallback behavior
        """
        self.fallback_provider: Optional[CacheFallbackProvider]
        self.cache = cache
        self.default_value = default_value
        self.enable_fallback = enable_fallback

        if enable_fallback:
            self.fallback_provider = CacheFallbackProvider(cache, default_value)
        else:
            self.fallback_provider = None

    async def get(self, key: str) -> Any:
        """
        Get value from cache with optional fallback.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value or fallback value
        """
        if self.enable_fallback and self.fallback_provider:
            return await self.fallback_provider.get_with_fallback(key)
        else:
            return await self.cache.aget(key)

    async def set(self, key: str, value: Any) -> None:
        """
        Set value in cache with optional fallback.

        Args:
            key: Cache key to set
            value: Value to cache
        """
        if self.enable_fallback and self.fallback_provider:
            await self.fallback_provider.set_with_fallback(key, value)
        else:
            await self.cache.aset(key, value)

    async def clear(self) -> None:
        """
        Clear cache with optional fallback.

        Args:
            key: Cache key to clear
        """
        if self.enable_fallback and self.fallback_provider:
            await self.fallback_provider.cache.aclear()
        else:
            await self.cache.aclear()

    def get_fallback_stats(self) -> Optional[FallbackStats]:
        """Get fallback statistics if fallback is enabled."""
        if self.fallback_provider:
            return self.fallback_provider.stats
        return None


__all__ = [
    "CacheFallbackProvider",
    "CacheFallbackWrapper",
    "FallbackStats",
]

# Preserve public API usage for static analyzers
_ = CacheFallbackWrapper.get_fallback_stats  # pragma: no cover
