"""
Tests for HighPerformanceLRUCache event loop isolation.

Scope:
- Event loop binding during initialization
- Cross-event-loop prevention
- Event loop rebinding
- Multiple caches on different loops
- Container integration with event loop isolation
- Performance with event loop validation
"""

import asyncio
import os
import time

import pytest

from fapilog.caching import HighPerformanceLRUCache


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

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Performance test with absolute timing thresholds; skip in CI",
    )
    @pytest.mark.asyncio
    async def test_event_loop_validation_performance(self):
        """Test that event loop validation doesn't impact performance."""
        cache = HighPerformanceLRUCache(capacity=1000)

        # Measure performance with event loop validation

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
