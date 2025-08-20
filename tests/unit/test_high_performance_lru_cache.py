"""
Tests for HighPerformanceLRUCache implementation.

This module provides comprehensive testing for the dual interface cache
implementation, covering both synchronous and asynchronous operations,
LRU eviction behavior, and edge cases.
"""

import asyncio
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

    def test_performance_characteristics(self):
        """Test that operations maintain O(1) performance
        characteristics."""
        cache = HighPerformanceLRUCache(capacity=10000)

        # Measure set performance
        import time

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


# Event Loop Isolation Tests
class TestEventLoopIsolation:
    """Test suite for event loop isolation functionality."""

    def test_init_with_event_loop(self):
        """Test cache initialization with explicit event loop."""
        # Create a new event loop for testing
        loop = asyncio.new_event_loop()
        try:
            cache = HighPerformanceLRUCache(capacity=100, event_loop=loop)
            assert cache.get_bound_event_loop() is loop
            assert cache.is_bound_to_event_loop() is True
        finally:
            loop.close()

    def test_init_without_event_loop(self):
        """Test cache initialization without event loop in sync context."""
        cache = HighPerformanceLRUCache(capacity=100)
        assert cache.get_bound_event_loop() is None
        assert cache.is_bound_to_event_loop() is False

    @pytest.mark.asyncio
    async def test_init_with_running_loop(self):
        """Test cache initialization with running event loop."""
        cache = HighPerformanceLRUCache(capacity=100)
        current_loop = asyncio.get_running_loop()
        assert cache.get_bound_event_loop() is current_loop
        assert cache.is_bound_to_event_loop() is True

    @pytest.mark.asyncio
    async def test_async_operations_on_bound_loop(self):
        """Test async operations work on bound event loop."""
        cache = HighPerformanceLRUCache(capacity=100)

        # These should work without errors
        await cache.aset("key1", "value1")
        result = await cache.aget("key1")
        assert result == "value1"

        await cache.aclear()
        assert cache.get_size() == 0

    @pytest.mark.asyncio
    async def test_cross_event_loop_prevention(self):
        """Test that cache prevents cross-event-loop usage."""
        # Create cache bound to current event loop
        cache = HighPerformanceLRUCache(capacity=100)
        current_loop = asyncio.get_running_loop()
        assert cache.get_bound_event_loop() is current_loop

        # Test that cache works normally on current loop
        await cache.aset("key1", "value1")
        assert await cache.aget("key1") == "value1"

        # Test that rebinding to a different loop works
        # (This simulates what would happen in a real cross-loop scenario)
        new_loop = asyncio.new_event_loop()
        try:
            cache.rebind_to_event_loop(new_loop)
            assert cache.get_bound_event_loop() is new_loop

            # Now using the cache should fail because we're on the wrong loop
            with pytest.raises(
                RuntimeError, match="Cache bound to different event loop"
            ):
                await cache.aget("key1")
        finally:
            new_loop.close()

    @pytest.mark.asyncio
    async def test_sync_operations_work_without_loop(self):
        """Test that sync operations work without event loop binding."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Sync operations should work regardless of event loop binding
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get_size() == 1

        # Dictionary interface should also work
        cache["key2"] = "value2"
        assert cache["key2"] == "value2"
        assert "key2" in cache

    @pytest.mark.asyncio
    async def test_rebind_to_event_loop(self):
        """Test rebinding cache to different event loop."""
        cache = HighPerformanceLRUCache(capacity=100)
        original_loop = asyncio.get_running_loop()
        assert cache.get_bound_event_loop() is original_loop

        # Test that cache works on original loop
        await cache.aset("key1", "value1")
        assert await cache.aget("key1") == "value1"

        # Create new event loop
        new_loop = asyncio.new_event_loop()
        try:
            # Rebind to new loop
            cache.rebind_to_event_loop(new_loop)
            assert cache.get_bound_event_loop() is new_loop

            # Now using the cache should fail because we're on the wrong loop
            with pytest.raises(
                RuntimeError, match="Cache bound to different event loop"
            ):
                await cache.aset("key2", "value2")
        finally:
            new_loop.close()

    @pytest.mark.asyncio
    async def test_multiple_caches_different_loops(self):
        """Test multiple caches bound to different event loops."""
        # Create first cache in current loop
        cache1 = HighPerformanceLRUCache(capacity=100)
        loop1 = asyncio.get_running_loop()

        # Create second event loop and cache
        loop2 = asyncio.new_event_loop()
        try:
            cache2 = HighPerformanceLRUCache(capacity=100, event_loop=loop2)

            # Each cache should be bound to its respective loop
            assert cache1.get_bound_event_loop() is loop1
            assert cache2.get_bound_event_loop() is loop2

            # Caches should be isolated
            assert cache1.get_bound_event_loop() is not cache2.get_bound_event_loop()

            # Each cache should work in its own loop
            await cache1.aset("key1", "value1")
            assert await cache1.aget("key1") == "value1"

            # Cache2 should fail when used from loop1 (wrong loop)
            with pytest.raises(
                RuntimeError, match="Cache bound to different event loop"
            ):
                await cache2.aset("key2", "value2")
        finally:
            loop2.close()

    @pytest.mark.asyncio
    async def test_cache_pool_with_event_loop_isolation(self):
        """Test that cache resource pool respects event loop isolation."""
        from fapilog.core.resources import CacheResourcePool

        pool = CacheResourcePool(
            name="test-pool",
            max_size=2,
            cache_capacity=100,
            acquire_timeout_seconds=0.1,
        )

        # Acquire cache from pool
        async with pool.acquire() as cache:
            current_loop = asyncio.get_running_loop()
            assert cache.get_bound_event_loop() is current_loop

            # Cache should work normally
            await cache.aset("key1", "value1")
            assert await cache.aget("key1") == "value1"

        await pool.cleanup()

    @pytest.mark.asyncio
    async def test_event_loop_validation_performance(self):
        """Test that event loop validation doesn't impact performance."""
        cache = HighPerformanceLRUCache(capacity=1000)

        # Measure performance with event loop validation
        import time

        start_time = time.time()
        for i in range(1000):
            await cache.aset(f"key{i}", f"value{i}")
        set_time = time.time() - start_time

        start_time = time.time()
        for i in range(1000):
            await cache.aget(f"key{i}")
        get_time = time.time() - start_time

        # Performance should still be good (O(1) + minimal validation
        # overhead)
        assert set_time < 0.2  # Should complete in under 200ms
        assert get_time < 0.2  # Should complete in under 200ms

    def test_event_loop_binding_edge_cases(self):
        """Test edge cases for event loop binding."""
        # Test with None event loop
        cache = HighPerformanceLRUCache(capacity=100, event_loop=None)
        assert cache.get_bound_event_loop() is None
        assert cache.is_bound_to_event_loop() is False

        # Test rebinding to None
        cache.rebind_to_event_loop(None)
        assert cache.get_bound_event_loop() is None
        assert cache.is_bound_to_event_loop() is False

    @pytest.mark.asyncio
    async def test_container_integration_event_loop_isolation(self):
        """Test that container integration maintains event loop isolation."""
        from fapilog.containers.container import AsyncLoggingContainer

        container = AsyncLoggingContainer()

        # Register cache component with event loop binding
        async def create_cache() -> HighPerformanceLRUCache:
            current_loop = asyncio.get_running_loop()
            return HighPerformanceLRUCache(capacity=100, event_loop=current_loop)

        container.register_component(
            "cache", HighPerformanceLRUCache, create_cache, is_singleton=True
        )

        await container.initialize()

        # Get cache from container
        cache = await container.get_component("cache", HighPerformanceLRUCache)
        current_loop = asyncio.get_running_loop()

        # Cache should be bound to current loop
        assert cache.get_bound_event_loop() is current_loop

        # Cache should work normally
        await cache.aset("key1", "value1")
        assert await cache.aget("key1") == "value1"

        await container.cleanup()


# Cache Cleanup Tests
class TestCacheCleanup:
    """Test suite for cache cleanup functionality."""

    def test_sync_clear_method(self):
        """Test that sync clear method works correctly."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Add some data
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert cache.get_size() == 2

        # Clear cache
        cache.clear()
        assert cache.get_size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_async_clear_method(self):
        """Test that async clear method works correctly."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Add some data
        await cache.aset("key1", "value1")
        await cache.aset("key2", "value2")
        assert cache.get_size() == 2

        # Clear cache
        await cache.aclear()
        assert cache.get_size() == 0

        # Keys should be cleared - should raise CacheMissError
        from fapilog.core.errors import CacheMissError

        with pytest.raises(CacheMissError):
            await cache.aget("key1")
        with pytest.raises(CacheMissError):
            await cache.aget("key2")

    @pytest.mark.asyncio
    async def test_cleanup_method(self):
        """Test that cleanup method works correctly."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Add some data
        await cache.aset("key1", "value1")
        await cache.aset("key2", "value2")
        assert cache.get_size() == 2
        assert cache.get_capacity() == 100
        assert cache.is_bound_to_event_loop() is True

        # Call cleanup
        await cache.cleanup()

        # Verify cleanup effects
        assert cache.get_size() == 0
        assert cache.get_capacity() == 100  # Capacity should remain unchanged
        assert cache.is_bound_to_event_loop() is False  # Event loop binding cleared

        # Cache should still be usable after cleanup
        await cache.aset("key3", "value3")
        assert cache.get_size() == 1
        assert await cache.aget("key3") == "value3"

    @pytest.mark.asyncio
    async def test_cleanup_never_raises_exceptions(self):
        """Test that cleanup method never raises exceptions."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Add some data
        await cache.aset("key1", "value1")

        # Mock the clear method to raise an exception
        original_clear = cache._ordered_dict.clear
        cache._ordered_dict.clear = lambda: (_ for _ in ()).throw(
            Exception("Test exception")
        )

        # Cleanup should not raise exceptions
        try:
            await cache.cleanup()
            # Should reach here without exceptions
        except Exception:
            pytest.fail("Cleanup method should not raise exceptions")
        finally:
            # Restore original method
            cache._ordered_dict.clear = original_clear

    @pytest.mark.asyncio
    async def test_cleanup_with_empty_cache(self):
        """Test cleanup method with empty cache."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Cache starts empty
        assert cache.get_size() == 0
        assert cache.get_capacity() == 100

        # Cleanup should work without issues
        await cache.cleanup()

        # Verify state
        assert cache.get_size() == 0
        assert cache.get_capacity() == 100  # Capacity should remain unchanged
        assert cache.is_bound_to_event_loop() is False

    @pytest.mark.asyncio
    async def test_cleanup_with_large_cache(self):
        """Test cleanup method with large cache."""
        cache = HighPerformanceLRUCache(capacity=1000)

        # Fill cache
        for i in range(1000):
            await cache.aset(f"key{i}", f"value{i}")

        assert cache.get_size() == 1000
        assert cache.is_full()

        # Cleanup should work efficiently
        start_time = time.time()
        await cache.cleanup()
        cleanup_time = time.time() - start_time

        # Cleanup should be fast (O(n) where n is cache size)
        assert cleanup_time < 0.1  # Should complete in under 100ms

        # Verify cleanup
        assert cache.get_size() == 0
        assert cache.get_capacity() == 1000  # Capacity should remain unchanged

    @pytest.mark.asyncio
    async def test_cache_resource_pool_cleanup(self):
        """Test that CacheResourcePool cleanup works correctly."""
        from fapilog.core.resources import CacheResourcePool

        pool = CacheResourcePool(
            name="test-pool",
            max_size=3,
            cache_capacity=100,
            acquire_timeout_seconds=0.1,
        )

        # Acquire and use some caches
        async with pool.acquire() as cache1:
            await cache1.aset("key1", "value1")
            assert await cache1.aget("key1") == "value1"

        async with pool.acquire() as cache2:
            await cache2.aset("key2", "value2")
            assert await cache2.aget("key2") == "value2"

        # Verify caches have data
        stats = await pool.stats()
        assert stats.created >= 1  # Pool may reuse instances

        # Cleanup pool
        await pool.cleanup()

        # Verify cleanup
        stats_after = await pool.stats()
        assert stats_after.in_use == 0
        assert stats_after.idle == 0

    @pytest.mark.asyncio
    async def test_container_integration_with_cache_cleanup(self):
        """Test that container integration works with cache cleanup."""
        from fapilog.containers.container import AsyncLoggingContainer

        container = AsyncLoggingContainer()

        # Register cache component
        async def create_cache() -> HighPerformanceLRUCache:
            current_loop = asyncio.get_running_loop()
            cache = HighPerformanceLRUCache(capacity=100, event_loop=current_loop)

            # Add cleanup callback to container
            container.add_cleanup_callback(cache.cleanup)

            return cache

        container.register_component(
            "cache", HighPerformanceLRUCache, create_cache, is_singleton=True
        )

        await container.initialize()

        # Get cache and add data
        cache = await container.get_component("cache", HighPerformanceLRUCache)
        await cache.aset("key1", "value1")
        assert await cache.aget("key1") == "value1"
        assert cache.get_size() == 1

        # Cleanup container
        await container.cleanup()

        # Cache should be cleaned up
        assert cache.get_size() == 0
        assert cache.get_capacity() == 100  # Capacity should remain unchanged
        assert cache.is_bound_to_event_loop() is False

    @pytest.mark.asyncio
    async def test_multiple_caches_cleanup_in_container(self):
        """Test cleanup of multiple caches in container."""
        from fapilog.containers.container import AsyncLoggingContainer

        container = AsyncLoggingContainer()

        # Initialize container first
        await container.initialize()

        # Create multiple caches
        caches = []
        for i in range(3):
            cache = HighPerformanceLRUCache(capacity=100)
            await cache.aset(f"key{i}", f"value{i}")
            caches.append(cache)

            # Add cleanup callback for each cache
            container.add_cleanup_callback(cache.cleanup)

        # Verify caches have data
        for i, cache in enumerate(caches):
            assert cache.get_size() == 1
            assert await cache.aget(f"key{i}") == f"value{i}"

        # Cleanup container
        await container.cleanup()

        # All caches should be cleaned up
        for cache in caches:
            assert cache.get_size() == 0
            assert cache.get_capacity() == 100  # Capacity should remain unchanged
            assert cache.is_bound_to_event_loop() is False

    @pytest.mark.asyncio
    async def test_cleanup_during_error_conditions(self):
        """Test cleanup behavior during error conditions."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Add data
        await cache.aset("key1", "value1")
        await cache.aset("key2", "value2")

        # Simulate error condition by corrupting internal state
        # This tests that cleanup is robust even with corrupted state
        cache._ordered_dict = None  # Corrupt the dict

        # Cleanup should not crash
        try:
            await cache.cleanup()
            # Should complete without exceptions
        except Exception:
            pytest.fail("Cleanup should handle corrupted state gracefully")

        # Cache should be in a clean state after cleanup
        assert cache.get_capacity() == 100  # Capacity should remain unchanged
        assert cache.is_bound_to_event_loop() is False

    @pytest.mark.asyncio
    async def test_cleanup_performance_characteristics(self):
        """Test that cleanup maintains good performance characteristics."""
        cache = HighPerformanceLRUCache(capacity=10000)

        # Fill cache with data
        for i in range(10000):
            await cache.aset(f"key{i}", f"value{i}")

        assert cache.get_size() == 10000

        # Measure cleanup performance
        start_time = time.time()
        await cache.cleanup()
        cleanup_time = time.time() - start_time

        # Cleanup should be fast and scale linearly with cache size
        # For 10k items, should complete in reasonable time
        assert cleanup_time < 0.5  # Should complete in under 500ms

        # Verify complete cleanup
        assert cache.get_size() == 0
        assert cache.get_capacity() == 10000  # Capacity should remain unchanged

    def test_cleanup_method_signature(self):
        """Test that cleanup method has correct signature."""
        cache = HighPerformanceLRUCache()

        # Verify method exists and is async
        assert hasattr(cache, "cleanup")
        assert asyncio.iscoroutinefunction(cache.cleanup)

        # Verify method signature
        import inspect

        sig = inspect.signature(cache.cleanup)
        assert str(sig) == "() -> None"


# Cache Error Handling Tests
class TestCacheErrorHandling:
    """Test suite for cache error handling functionality."""

    @pytest.mark.asyncio
    async def test_cache_miss_error_raised(self):
        """Test that CacheMissError is raised for missing keys."""
        from fapilog.core.errors import CacheMissError

        cache = HighPerformanceLRUCache(capacity=100)

        # Try to get non-existent key
        with pytest.raises(CacheMissError) as exc_info:
            await cache.aget("nonexistent_key")

        error = exc_info.value
        assert error.cache_key == "nonexistent_key"
        assert error.context.category.value == "system"
        assert error.context.severity.value == "low"
        assert error.context.recovery_strategy.value == "fallback"

    @pytest.mark.asyncio
    async def test_cache_operation_error_on_exception(self):
        """Test that CacheOperationError is raised for operation failures."""
        from fapilog.core.errors import CacheOperationError

        cache = HighPerformanceLRUCache(capacity=100)

        # Corrupt the cache to cause an exception
        cache._ordered_dict = None

        # Try to get a key - should raise CacheOperationError
        with pytest.raises(CacheOperationError) as exc_info:
            await cache.aget("test_key")

        error = exc_info.value
        assert error.operation == "get"
        assert error.cache_key == "test_key"
        assert error.context.category.value == "system"
        assert error.context.severity.value == "medium"
        assert error.context.recovery_strategy.value == "fallback"

    @pytest.mark.asyncio
    async def test_cache_operation_error_on_set_failure(self):
        """Test that CacheOperationError is raised for set failures."""
        from fapilog.core.errors import CacheOperationError

        cache = HighPerformanceLRUCache(capacity=100)

        # Corrupt the cache to cause an exception
        cache._ordered_dict = None

        # Try to set a key - should raise CacheOperationError
        with pytest.raises(CacheOperationError) as exc_info:
            await cache.aset("test_key", "test_value")

        error = exc_info.value
        assert error.operation == "set"
        assert error.cache_key == "test_key"
        assert error.context.category.value == "system"
        assert error.context.severity.value == "medium"
        assert error.context.recovery_strategy.value == "fallback"

    @pytest.mark.asyncio
    async def test_cache_operation_error_on_clear_failure(self):
        """Test that CacheOperationError is raised for clear failures."""
        from fapilog.core.errors import CacheOperationError

        cache = HighPerformanceLRUCache(capacity=100)

        # Corrupt the cache to cause an exception
        cache._ordered_dict = None

        # Try to clear cache - should raise CacheOperationError
        with pytest.raises(CacheOperationError) as exc_info:
            await cache.aclear()

        error = exc_info.value
        assert error.operation == "clear"
        assert error.cache_key == ""  # Empty string for clear operation
        assert error.context.category.value == "system"
        assert error.context.severity.value == "medium"
        assert error.context.recovery_strategy.value == "fallback"

    @pytest.mark.asyncio
    async def test_runtime_error_preserved(self):
        """Test that RuntimeError (event loop mismatch) is preserved."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Create a mock loop with different ID
        class MockLoop:
            def __init__(self, loop_id):
                self.loop_id = loop_id

            def __eq__(self, other):
                return False  # Always different

        mock_loop = MockLoop(999)

        # Bind cache to mock loop
        cache.rebind_to_event_loop(mock_loop)

        # Try to use cache from current loop - should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            await cache.aget("test_key")

        # Should be the event loop mismatch error
        assert "Cache bound to different event loop" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_type_error_preserved(self):
        """Test that TypeError (invalid key type) is preserved."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Try to use invalid key type - should raise TypeError
        with pytest.raises(TypeError) as exc_info:
            await cache.aget(123)  # Invalid key type

        assert "Cache key must be a string" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_context_preservation(self):
        """Test that error context is properly preserved."""
        from fapilog.core.errors import CacheMissError

        cache = HighPerformanceLRUCache(capacity=100)

        try:
            await cache.aget("nonexistent_key")
        except CacheMissError as e:
            # Verify error context is captured
            assert e.context is not None
            assert e.context.error_id is not None
            assert e.context.timestamp is not None
            assert e.context.category.value == "system"
            assert e.context.severity.value == "low"
            assert e.context.recovery_strategy.value == "fallback"

            # Verify cache key is preserved
            assert e.cache_key == "nonexistent_key"
        else:
            pytest.fail("Expected CacheMissError to be raised")

    @pytest.mark.asyncio
    async def test_error_cause_preservation(self):
        """Test that error cause is properly preserved."""
        from fapilog.core.errors import CacheOperationError

        cache = HighPerformanceLRUCache(capacity=100)

        # Corrupt the cache to cause an exception
        original_dict = cache._ordered_dict
        cache._ordered_dict = None

        try:
            await cache.aset("test_key", "test_value")
        except CacheOperationError as e:
            # Verify cause is preserved
            assert e.__cause__ is not None
            assert "TypeError" in str(type(e.__cause__))

            # Verify operation details
            assert e.operation == "set"
            assert e.cache_key == "test_key"
        else:
            pytest.fail("Expected CacheOperationError to be raised")
        finally:
            # Restore cache
            cache._ordered_dict = original_dict

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_cache_failure(self):
        """Test that cache failures don't crash the system."""
        cache = HighPerformanceLRUCache(capacity=100)

        # Add some data first
        await cache.aset("key1", "value1")
        assert await cache.aget("key1") == "value1"

        # Corrupt the cache
        cache._ordered_dict = None

        # Cache operations should fail gracefully with proper errors
        from fapilog.core.errors import CacheOperationError

        with pytest.raises(CacheOperationError):
            await cache.aget("key1")

        with pytest.raises(CacheOperationError):
            await cache.aset("key2", "test_value")

        with pytest.raises(CacheOperationError):
            await cache.aclear()

    @pytest.mark.asyncio
    async def test_cache_miss_vs_cache_failure_distinction(self):
        """Test that cache miss and cache failure are properly distinguished."""
        from fapilog.core.errors import CacheMissError, CacheOperationError

        cache = HighPerformanceLRUCache(capacity=100)

        # Cache miss - should raise CacheMissError
        with pytest.raises(CacheMissError):
            await cache.aget("nonexistent_key")

        # Corrupt cache to cause failure
        cache._ordered_dict = None

        # Cache failure - should raise CacheOperationError
        with pytest.raises(CacheOperationError):
            await cache.aget("nonexistent_key")

    @pytest.mark.asyncio
    async def test_error_inheritance_hierarchy(self):
        """Test that cache errors follow proper inheritance hierarchy."""
        from fapilog.core.errors import (
            CacheError,
            CacheMissError,
            CacheOperationError,
            FapilogError,
        )

        # Test inheritance
        assert issubclass(CacheError, FapilogError)
        assert issubclass(CacheMissError, CacheError)
        assert issubclass(CacheOperationError, CacheError)

        # Test that instances are of correct types
        cache = HighPerformanceLRUCache(capacity=100)

        # Cache miss error
        with pytest.raises(CacheMissError) as exc_info:
            await cache.aget("nonexistent_key")

        error = exc_info.value
        assert isinstance(error, CacheMissError)
        assert isinstance(error, CacheError)
        assert isinstance(error, FapilogError)

    @pytest.mark.asyncio
    async def test_error_message_formatting(self):
        """Test that error messages are properly formatted."""
        from fapilog.core.errors import CacheMissError, CacheOperationError

        cache = HighPerformanceLRUCache(capacity=100)

        # Test cache miss error message
        with pytest.raises(CacheMissError) as exc_info:
            await cache.aget("test_key")

        error = exc_info.value
        assert "Cache key not found: test_key" in str(error)

        # Test cache operation error message
        cache._ordered_dict = None

        with pytest.raises(CacheOperationError) as exc_info:
            await cache.aset("test_key", "test_value")

        error = exc_info.value
        assert "Cache operation 'set' failed for key 'test_key'" in str(error)

    @pytest.mark.asyncio
    async def test_error_context_metadata(self):
        """Test that error context metadata is properly set."""
        from fapilog.core.errors import CacheMissError

        cache = HighPerformanceLRUCache(capacity=100)

        try:
            await cache.aget("nonexistent_key")
        except CacheMissError as e:
            # Verify metadata is captured
            assert e.context.metadata is not None

            # Verify error context has required fields
            assert e.context.error_id is not None
            assert e.context.timestamp is not None
            assert e.context.category.value == "system"
            assert e.context.severity.value == "low"
            assert e.context.recovery_strategy.value == "fallback"
        else:
            pytest.fail("Expected CacheMissError to be raised")
