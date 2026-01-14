"""
Tests for HighPerformanceLRUCache basic operations.

Scope:
- Cache initialization with valid/invalid capacity
- Synchronous get/set operations
- LRU eviction behavior
- Dictionary interface compatibility
- Utility methods (keys, values, items, clear)
- Performance characteristics
- Edge cases
"""

import asyncio
import os
import time

import pytest

from fapilog.caching import HighPerformanceLRUCache


class TestHighPerformanceLRUCache:
    """Test suite for HighPerformanceLRUCache class."""

    def test_init_with_valid_capacity(self):
        """Test cache initialization with valid capacity."""
        cache = HighPerformanceLRUCache(capacity=100)
        assert cache.get_capacity() == 100
        assert cache.get_size() == 0
        assert not cache.is_full()

    def test_init_with_invalid_capacity(self):
        """Test cache initialization with invalid capacity."""
        with pytest.raises(ValueError, match="Capacity must be positive"):
            HighPerformanceLRUCache(capacity=0)

        with pytest.raises(ValueError, match="Capacity must be positive"):
            HighPerformanceLRUCache(capacity=-1)

    def test_init_with_default_capacity(self):
        """Test cache initialization with default capacity."""
        cache = HighPerformanceLRUCache()
        assert cache.get_capacity() == 1000
        assert cache.get_size() == 0

    def test_sync_get_set_operations(self):
        """Test synchronous get and set operations."""
        cache = HighPerformanceLRUCache(capacity=3)

        # Test basic set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get_size() == 1

        # Test updating existing key
        cache.set("key1", "updated_value1")
        assert cache.get("key1") == "updated_value1"
        assert cache.get_size() == 1

        # Test multiple keys
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get_size() == 3

    def test_sync_get_nonexistent_key(self):
        """Test getting nonexistent key returns None."""
        cache = HighPerformanceLRUCache()
        assert cache.get("nonexistent") is None

    def test_sync_lru_eviction(self):
        """Test LRU eviction behavior."""
        cache = HighPerformanceLRUCache(capacity=2)

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert cache.get_size() == 2
        assert cache.is_full()

        # Access key1 to make it most recently used
        cache.get("key1")

        # Add new key, should evict key2 (least recently used)
        cache.set("key3", "value3")
        assert cache.get_size() == 2
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key3") == "value3"  # New key
        assert cache.get("key2") is None  # Evicted

    def test_sync_invalid_key_type(self):
        """Test that non-string keys raise TypeError."""
        cache = HighPerformanceLRUCache()

        with pytest.raises(TypeError, match="Cache key must be a string"):
            cache.get(123)  # type: ignore

        with pytest.raises(TypeError, match="Cache key must be a string"):
            cache.set(123, "value")  # type: ignore

    @pytest.mark.asyncio
    async def test_async_get_set_operations(self):
        """Test asynchronous get and set operations."""
        cache = HighPerformanceLRUCache(capacity=3)

        # Test basic async set and get
        await cache.aset("key1", "value1")
        result = await cache.aget("key1")
        assert result == "value1"
        assert cache.get_size() == 1

        # Test updating existing key
        await cache.aset("key1", "updated_value1")
        result = await cache.aget("key1")
        assert result == "updated_value1"
        assert cache.get_size() == 1

        # Test multiple keys
        await cache.aset("key2", "value2")
        await cache.aset("key3", "value3")
        assert await cache.aget("key2") == "value2"
        assert await cache.aget("key3") == "value3"
        assert cache.get_size() == 3

    @pytest.mark.asyncio
    async def test_async_get_nonexistent_key(self):
        """Test getting nonexistent key raises CacheMissError."""
        from fapilog.core.errors import CacheMissError

        cache = HighPerformanceLRUCache()
        with pytest.raises(CacheMissError):
            await cache.aget("nonexistent")

    @pytest.mark.asyncio
    async def test_async_lru_eviction(self):
        """Test LRU eviction behavior with async operations."""
        cache = HighPerformanceLRUCache(capacity=2)

        # Fill cache
        await cache.aset("key1", "value1")
        await cache.aset("key2", "value2")
        assert cache.get_size() == 2
        assert cache.is_full()

        # Access key1 to make it most recently used
        await cache.aget("key1")

        # Add new key, should evict key2 (least recently used)
        await cache.aset("key3", "value3")
        assert cache.get_size() == 2
        assert await cache.aget("key1") == "value1"  # Still there
        assert await cache.aget("key3") == "value3"  # New key

        # key2 should be evicted - should raise CacheMissError
        from fapilog.core.errors import CacheMissError

        with pytest.raises(CacheMissError):
            await cache.aget("key2")

    @pytest.mark.asyncio
    async def test_async_invalid_key_type(self):
        """Test that non-string keys raise TypeError in async operations."""
        cache = HighPerformanceLRUCache()

        with pytest.raises(TypeError, match="Cache key must be a string"):
            await cache.aget(123)  # type: ignore

        with pytest.raises(TypeError, match="Cache key must be a string"):
            await cache.aset(123, "value")  # type: ignore

    def test_dictionary_interface(self):
        """Test dictionary-style interface compatibility."""
        cache = HighPerformanceLRUCache(capacity=2)

        # Test __setitem__ and __getitem__
        cache["key1"] = "value1"
        assert cache["key1"] == "value1"

        # Test __contains__
        assert "key1" in cache
        assert "nonexistent" not in cache

        # Test __len__
        assert len(cache) == 1

        # Test iteration
        keys = list(cache)
        assert keys == ["key1"]

    def test_dictionary_interface_key_error(self):
        """Test that __getitem__ raises KeyError for missing keys."""
        cache = HighPerformanceLRUCache()

        with pytest.raises(KeyError):
            _ = cache["nonexistent"]

    def test_utility_methods(self):
        """Test utility methods."""
        cache = HighPerformanceLRUCache(capacity=3)

        # Test keys, values, items
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.keys() == ["key1", "key2"]
        assert cache.values() == ["value1", "value2"]
        assert cache.items() == [("key1", "value1"), ("key2", "value2")]

        # Test clear
        cache.clear()
        assert cache.get_size() == 0
        assert cache.keys() == []
        assert cache.values() == []
        assert cache.items() == []

    @pytest.mark.asyncio
    async def test_async_utility_methods(self):
        """Test asynchronous utility methods."""
        cache = HighPerformanceLRUCache(capacity=3)

        # Test async clear
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        await cache.aclear()
        assert cache.get_size() == 0

    def test_mixed_sync_async_operations(self):
        """Test that sync and async operations work together."""
        cache = HighPerformanceLRUCache(capacity=3)

        # Set with sync, get with async
        cache.set("key1", "value1")
        assert asyncio.run(cache.aget("key1")) == "value1"

        # Set with async, get with sync
        asyncio.run(cache.aset("key2", "value2"))
        assert cache.get("key2") == "value2"

    def test_concurrent_access_safety(self):
        """Test that concurrent access is handled safely."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Fill cache
        for i in range(50):
            cache.set(f"key{i}", f"value{i}")

        # Simulate concurrent access
        async def concurrent_operations():
            tasks = []
            for i in range(100):
                if i % 2 == 0:
                    tasks.append(
                        cache.aset(f"concurrent_key{i}", f"concurrent_value{i}")
                    )
                else:
                    tasks.append(cache.aget(f"concurrent_key{i - 1}"))

            await asyncio.gather(*tasks, return_exceptions=True)

        # Run concurrent operations
        asyncio.run(concurrent_operations())

        # Verify cache is still functional
        assert cache.get_size() <= cache.get_capacity()

    def test_cache_protocol_compliance(self):
        """Test that HighPerformanceLRUCache implements CacheProtocol."""
        cache = HighPerformanceLRUCache()

        # Verify it has all required methods
        assert hasattr(cache, "get")
        assert hasattr(cache, "set")
        assert hasattr(cache, "__getitem__")
        assert hasattr(cache, "__setitem__")
        assert hasattr(cache, "__contains__")

        # Test protocol compliance
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        assert cache["test_key"] == "test_value"
        assert "test_key" in cache

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Performance test with absolute timing thresholds; skip in CI",
    )
    def test_performance_characteristics(self):
        """Test that operations maintain O(1) performance
        characteristics."""
        cache = HighPerformanceLRUCache(capacity=10000)

        # Measure set performance

        start_time = time.time()
        for i in range(1000):
            cache.set(f"key{i}", f"value{i}")
        set_time = time.time() - start_time

        # Measure get performance
        start_time = time.time()
        for i in range(1000):
            cache.get(f"key{i}")
        get_time = time.time() - start_time

        # Both operations should be very fast (O(1))
        assert set_time < 0.1  # Should complete in under 100ms
        assert get_time < 0.1  # Should complete in under 100ms

    def test_edge_cases(self):
        """Test various edge cases."""
        cache = HighPerformanceLRUCache(capacity=1)

        # Test with empty string key
        cache.set("", "empty_key_value")
        assert cache.get("") == "empty_key_value"

        # Test with very long key
        long_key = "x" * 1000
        cache.set(long_key, "long_key_value")
        assert cache.get(long_key) == "long_key_value"

        # Test with None value
        cache.set("none_key", None)
        assert cache.get("none_key") is None

        # Test with complex objects
        complex_obj = {"nested": {"data": [1, 2, 3]}}
        cache.set("complex_key", complex_obj)
        assert cache.get("complex_key") == complex_obj

    def test_capacity_boundary_conditions(self):
        """Test capacity boundary conditions."""
        cache = HighPerformanceLRUCache(capacity=1)

        # Test exactly at capacity
        cache.set("key1", "value1")
        assert cache.get_size() == 1
        assert cache.is_full()

        # Test exceeding capacity (should evict oldest)
        cache.set("key2", "value2")
        assert cache.get_size() == 1
        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == "value2"  # Newest

    def test_lru_order_maintenance(self):
        """Test that LRU order is maintained correctly."""
        cache = HighPerformanceLRUCache(capacity=3)

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Access key1 to make it most recently used
        cache.get("key1")

        # Access key2 to make it most recently used
        cache.get("key2")

        # Now key3 should be least recently used
        cache.set("key4", "value4")
        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") == "value2"  # Still there
        assert cache.get("key3") is None  # Evicted
        assert cache.get("key4") == "value4"  # Newest
