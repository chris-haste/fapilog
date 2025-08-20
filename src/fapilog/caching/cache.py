"""
High-performance LRU cache with dual sync/async interfaces.

This module provides a cache implementation that supports both synchronous
and asynchronous operations, maintaining backward compatibility with existing
cache APIs while providing O(1) performance characteristics.
"""

import asyncio
from collections import OrderedDict
from typing import Any, Iterator

from typing_extensions import Protocol


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

    def __init__(self, capacity: int = 1000) -> None:
        """
        Initialize the cache with specified capacity.

        Args:
            capacity: Maximum number of items in cache
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self._capacity = capacity
        self._ordered_dict: OrderedDict[str, Any] = OrderedDict()
        self._lock = asyncio.Lock()

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
            Cached value or None if not found
        """
        if not isinstance(key, str):
            raise TypeError("Cache key must be a string")

        async with self._lock:
            if key in self._ordered_dict:
                # Move to end (most recently used)
                value = self._ordered_dict.pop(key)
                self._ordered_dict[key] = value
                return value
            return None

    async def aset(self, key: str, value: Any) -> None:
        """
        Set value in cache (asynchronous).

        Args:
            key: Cache key
            value: Value to cache
        """
        if not isinstance(key, str):
            raise TypeError("Cache key must be a string")

        async with self._lock:
            if key in self._ordered_dict:
                # Update existing key (move to end)
                self._ordered_dict.pop(key)
            elif len(self._ordered_dict) >= self._capacity:
                # Remove least recently used item
                self._ordered_dict.popitem(last=False)

            self._ordered_dict[key] = value

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
        """Clear all items from cache (asynchronous)."""
        async with self._lock:
            self._ordered_dict.clear()

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
