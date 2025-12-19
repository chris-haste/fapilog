"""
High-performance LRU cache with dual sync/async interfaces.

This module provides a cache implementation that supports both synchronous
and asynchronous operations, maintaining backward compatibility with existing
cache APIs while providing O(1) performance characteristics.
"""

import asyncio
from collections import OrderedDict
from typing import Any, Iterator, Optional

from typing_extensions import Protocol

from ..core.errors import (
    CacheCapacityError,
    CacheMissError,
    CacheOperationError,
)


class CacheProtocol(Protocol):
    """Protocol defining the interface for cache implementations."""

    def get(self, key: str) -> Any:
        """Get value from cache."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        ...

    def __getitem__(self, key: str) -> Any:
        """Get value using dictionary-style access."""
        ...

    def __setitem__(self, key: str, value: Any) -> None:
        """Set value using dictionary-style access."""
        ...

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...


class HighPerformanceLRUCache:
    """
    High-performance LRU cache with dual sync/async interfaces.

    This cache implementation provides both synchronous and asynchronous
    methods while maintaining O(1) performance characteristics for all
    operations. It uses collections.OrderedDict for efficient LRU eviction.

    The cache supports both dictionary-style access and explicit get/set
    methods, making it compatible with existing CacheFallback and
    AsyncFallbackWrapper implementations.
    """

    def __init__(
        self,
        capacity: int = 1000,
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize the cache with specified capacity and event loop binding.

        Args:
            capacity: Maximum number of items in cache
            event_loop: Event loop to bind this cache to
                (defaults to current running loop)
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self._capacity = capacity
        self._ordered_dict: OrderedDict[str, Any] = OrderedDict()

        # Bind to specific event loop for async operations
        try:
            self._loop: Optional[asyncio.AbstractEventLoop] = (
                event_loop or asyncio.get_running_loop()
            )
        except RuntimeError:
            # No running loop in current context
            self._loop = None

        self._lock = asyncio.Lock()

    def _validate_event_loop(self) -> None:
        """
        Validate that the current event loop matches the bound event loop.

        Raises:
            RuntimeError: If cache is bound to a different event loop
        """
        if self._loop is not None:
            try:
                current_loop = asyncio.get_running_loop()
                if current_loop is not self._loop:
                    raise RuntimeError(
                        f"Cache bound to different event loop. "
                        f"Expected: {id(self._loop)}, Got: {id(current_loop)}"
                    )
            except RuntimeError as e:
                # Only ignore RuntimeError if it's "no running loop"
                # Re-raise if it's our own event loop mismatch error
                if "Cache bound to different event loop" in str(e):
                    raise
                # No running loop, which is fine for sync operations
                pass

    # Sync interface for SyncLoggerFacade and existing code
    def get(self, key: str) -> Any:
        """
        Get value from cache (synchronous).

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not isinstance(key, str):
            raise TypeError("Cache key must be a string")

        if key in self._ordered_dict:
            # Move to end (most recently used)
            value = self._ordered_dict.pop(key)
            self._ordered_dict[key] = value
            return value
        return None

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache (synchronous).

        Args:
            key: Cache key
            value: Value to cache
        """
        if not isinstance(key, str):
            raise TypeError("Cache key must be a string")

        if key in self._ordered_dict:
            # Update existing key (move to end)
            self._ordered_dict.pop(key)
        elif len(self._ordered_dict) >= self._capacity:
            # Remove least recently used item
            self._ordered_dict.popitem(last=False)

        self._ordered_dict[key] = value

    # Async interface for AsyncLoggingContainer
    async def aget(self, key: str) -> Any:
        """
        Get value from cache (asynchronous).

        Args:
            key: Cache key

        Returns:
            Cached value

        Raises:
            CacheMissError: If cache key is not found
            RuntimeError: If cache is bound to a different event loop
            CacheOperationError: If cache operation fails
        """
        if not isinstance(key, str):
            raise TypeError("Cache key must be a string")

        try:
            # Ensure operation executes on correct event loop
            self._validate_event_loop()

            async with self._lock:
                if key in self._ordered_dict:
                    # Move to end (most recently used)
                    value = self._ordered_dict.pop(key)
                    self._ordered_dict[key] = value
                    return value
                else:
                    # Cache miss - raise specific error
                    raise CacheMissError(key)
        except (CacheMissError, RuntimeError):
            # Re-raise these specific errors
            raise
        except Exception as e:
            # Log error and degrade gracefully
            # Re-raise as cache operation error with proper context
            raise CacheOperationError("get", key, cause=e) from e

    async def aset(self, key: str, value: Any) -> None:
        """
        Set value in cache (asynchronous).

        Args:
            key: Cache key
            value: Value to cache

        Raises:
            RuntimeError: If cache is bound to a different event loop
            CacheCapacityError: If cache capacity is exceeded
            CacheOperationError: If cache operation fails
        """
        if not isinstance(key, str):
            raise TypeError("Cache key must be a string")

        try:
            # Ensure operation executes on correct event loop
            self._validate_event_loop()

            async with self._lock:
                if key in self._ordered_dict:
                    # Update existing key (move to end)
                    self._ordered_dict.pop(key)
                elif len(self._ordered_dict) >= self._capacity:
                    # Remove least recently used item
                    self._ordered_dict.popitem(last=False)

                self._ordered_dict[key] = value
        except (RuntimeError, CacheCapacityError):
            # Re-raise these specific errors
            raise
        except Exception as e:
            # Log error and degrade gracefully
            # Re-raise as cache operation error with proper context
            raise CacheOperationError("set", key, cause=e) from e

    # Dictionary-style interface for compatibility
    def __getitem__(self, key: str) -> Any:
        """Get value using dictionary-style access."""
        if key not in self._ordered_dict:
            raise KeyError(key)
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set value using dictionary-style access."""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._ordered_dict

    def __len__(self) -> int:
        """Get current number of items in cache."""
        return len(self._ordered_dict)

    def __iter__(self) -> Iterator[str]:
        """Iterate over cache keys."""
        return iter(self._ordered_dict)

    # Utility methods
    def clear(self) -> None:
        """Clear all items from cache."""
        self._ordered_dict.clear()

    async def aclear(self) -> None:
        """
        Clear all items from cache (asynchronous).

        Raises:
            RuntimeError: If cache is bound to a different event loop
            CacheOperationError: If cache operation fails
        """
        try:
            # Ensure operation executes on correct event loop
            self._validate_event_loop()

            async with self._lock:
                self._ordered_dict.clear()
        except RuntimeError:
            # Re-raise runtime errors
            raise
        except Exception as e:
            # Log error and degrade gracefully
            # Re-raise as cache operation error with proper context
            raise CacheOperationError("clear", "", cause=e) from e

    def keys(self) -> list[str]:
        """Get all cache keys."""
        return list(self._ordered_dict.keys())

    def values(self) -> list[Any]:
        """Get all cache values."""
        return list(self._ordered_dict.values())

    def items(self) -> list[tuple[str, Any]]:
        """Get all cache key-value pairs."""
        return list(self._ordered_dict.items())

    def get_capacity(self) -> int:
        """Get cache capacity."""
        return self._capacity

    def get_size(self) -> int:
        """Get current cache size."""
        return len(self._ordered_dict)

    def is_full(self) -> bool:
        """Check if cache is at capacity."""
        return len(self._ordered_dict) >= self._capacity

    def get_bound_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """Get the event loop this cache is bound to."""
        return self._loop

    def is_bound_to_event_loop(self) -> bool:
        """Check if this cache is bound to a specific event loop."""
        return self._loop is not None

    def rebind_to_event_loop(self, event_loop: asyncio.AbstractEventLoop) -> None:
        """
        Rebind the cache to a different event loop.

        This is useful for testing or when the cache needs to be moved
        to a different event loop context.

        Args:
            event_loop: New event loop to bind to
        """
        self._loop = event_loop

    async def cleanup(self) -> None:
        """
        Guaranteed cleanup that never raises exceptions.

        This method ensures all cache resources are properly released
        and internal state is reset. It's designed to be called during
        container cleanup and never raises exceptions.
        """
        try:
            # Clear cache contents
            if hasattr(self, "_ordered_dict") and self._ordered_dict is not None:
                self._ordered_dict.clear()

            # Don't reset capacity to 0 as it breaks cache functionality
            # Just clear the contents to release memory

            # Clear event loop binding
            self._loop = None

            # Note: self._lock is not cleared as it's a simple asyncio.Lock
        except Exception:
            # Log but never raise during cleanup
            # This ensures container cleanup can complete
            pass


# Mark public API methods as used for static analyzers
_ = (
    HighPerformanceLRUCache.get_capacity,
    HighPerformanceLRUCache.get_size,
    HighPerformanceLRUCache.get_bound_event_loop,
    HighPerformanceLRUCache.is_bound_to_event_loop,
    HighPerformanceLRUCache.rebind_to_event_loop,
)  # pragma: no cover
