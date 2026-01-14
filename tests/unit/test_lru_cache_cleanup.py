"""
Tests for HighPerformanceLRUCache cleanup and error handling.

Scope:
- Cache cleanup functionality
- Resource pool cleanup
- Container integration cleanup
- Error handling during cleanup
- Cache error types (CacheMissError, CacheOperationError)
- Error context preservation
- Graceful degradation on failures
"""

import asyncio
import inspect
import time
from datetime import datetime

import pytest

from fapilog.caching import HighPerformanceLRUCache


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

        # Acquire two caches simultaneously to force creation of 2 instances
        async with pool.acquire() as cache1:
            await cache1.aset("key1", "value1")
            assert await cache1.aget("key1") == "value1"

            async with pool.acquire() as cache2:
                await cache2.aset("key2", "value2")
                assert await cache2.aget("key2") == "value2"

        # Verify caches were created (2 instances, both now idle)
        stats = await pool.stats()
        assert stats.created == 2

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
        sig = inspect.signature(cache.cleanup)
        assert str(sig) == "() -> None"


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
            # Verify error context is captured with correct types
            assert isinstance(e.context.error_id, str)
            assert len(e.context.error_id) == 36  # UUID format
            assert isinstance(e.context.timestamp, datetime)
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
            # Verify cause is preserved as TypeError
            assert isinstance(e.__cause__, TypeError)

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
            # Verify metadata is captured (dict with cache info)
            assert isinstance(e.context.metadata, dict)

            # Verify error context has required fields with correct types
            assert isinstance(e.context.error_id, str) and len(e.context.error_id) == 36
            assert isinstance(e.context.timestamp, datetime)
            assert e.context.category.value == "system"
            assert e.context.severity.value == "low"
            assert e.context.recovery_strategy.value == "fallback"
        else:
            pytest.fail("Expected CacheMissError to be raised")
