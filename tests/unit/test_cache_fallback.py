"""
Tests for cache fallback functionality.

This module tests the cache fallback provider and wrapper classes
that ensure graceful degradation when cache operations fail.
"""

import pytest

from fapilog.caching.cache import HighPerformanceLRUCache
from fapilog.caching.fallback import CacheFallbackProvider, CacheFallbackWrapper
from fapilog.core.errors import CacheError, CacheMissError
from fapilog.core.fallback import FallbackConfig, FallbackStrategy, FallbackTrigger


class TestCacheFallbackProvider:
    """Test suite for CacheFallbackProvider."""

    @pytest.mark.asyncio
    async def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        assert provider.cache == cache
        assert provider.default_value == "fallback_value"
        assert provider.fallback_config.strategy == FallbackStrategy.STATIC_VALUE
        assert FallbackTrigger.EXCEPTION in provider.fallback_config.triggers

    @pytest.mark.asyncio
    async def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        cache = HighPerformanceLRUCache(capacity=100)
        custom_config = FallbackConfig(
            strategy=FallbackStrategy.FUNCTION_CALL,
            triggers=[FallbackTrigger.TIMEOUT],
            static_value="custom_fallback",
        )

        provider = CacheFallbackProvider(cache, fallback_config=custom_config)

        assert provider.fallback_config.strategy == FallbackStrategy.FUNCTION_CALL
        assert FallbackTrigger.TIMEOUT in provider.fallback_config.triggers
        assert provider.fallback_config.static_value == "custom_fallback"

    @pytest.mark.asyncio
    async def test_get_with_fallback_on_cache_miss(self):
        """Test fallback behavior on cache miss."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Try to get non-existent key
        result = await provider.get_with_fallback("nonexistent_key")

        assert result == "fallback_value"
        assert provider.stats.fallback_calls == 1
        assert provider.stats.fallback_success == 1
        assert provider.stats.primary_success == 0

    @pytest.mark.asyncio
    async def test_get_with_fallback_on_cache_failure(self):
        """Test fallback behavior on cache failure."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Corrupt cache to cause failure
        cache._ordered_dict = None

        # Try to get key - should use fallback
        result = await provider.get_with_fallback("test_key")

        assert result == "fallback_value"
        assert provider.stats.fallback_calls == 1
        assert provider.stats.fallback_success == 1
        assert provider.stats.primary_success == 0

    @pytest.mark.asyncio
    async def test_get_with_fallback_on_success(self):
        """Test successful cache get without fallback."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Set value in cache
        await cache.aset("test_key", "cached_value")

        # Get value - should succeed without fallback
        result = await provider.get_with_fallback("test_key")

        assert result == "cached_value"
        assert provider.stats.primary_success == 1
        assert provider.stats.fallback_calls == 0

    @pytest.mark.asyncio
    async def test_get_with_fallback_no_fallback_value(self):
        """Test behavior when no fallback value is available."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache)  # No default value

        # Try to get non-existent key - should raise CacheError
        with pytest.raises(CacheError) as exc_info:
            await provider.get_with_fallback("nonexistent_key")

        assert "No fallback value for cache key" in str(exc_info.value)
        assert provider.stats.fallback_calls == 1
        assert provider.stats.fallback_success == 0

    @pytest.mark.asyncio
    async def test_set_with_fallback_on_success(self):
        """Test successful cache set without fallback."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Set value - should succeed
        await provider.set_with_fallback("test_key", "test_value")

        assert provider.stats.primary_success == 1
        assert provider.stats.fallback_calls == 0

        # Verify value was set
        result = await cache.aget("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_fallback_on_failure(self):
        """Test fallback behavior on cache set failure."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Corrupt cache to cause failure
        cache._ordered_dict = None

        # Set value - should fail gracefully
        await provider.set_with_fallback("test_key", "test_value")

        assert provider.stats.fallback_calls == 1
        assert provider.stats.primary_success == 0
        # Set operations don't fail the operation, just log the failure

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test that statistics are properly tracked."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Perform various operations
        await provider.set_with_fallback("key1", "value1")  # Success
        await provider.get_with_fallback("key1")  # Success
        await provider.get_with_fallback("key2")  # Fallback

        # Verify stats
        stats = provider.stats
        assert stats.primary_success == 2  # set + get
        assert stats.fallback_calls == 1  # get key2
        assert stats.fallback_success == 1
        assert stats.total_calls == 3

    @pytest.mark.asyncio
    async def test_stats_reset(self):
        """Test that statistics can be reset."""
        cache = HighPerformanceLRUCache(capacity=100)
        provider = CacheFallbackProvider(cache, default_value="fallback_value")

        # Perform some operations
        await provider.get_with_fallback("nonexistent_key")

        # Verify stats are recorded
        assert provider.stats.fallback_calls == 1

        # Reset stats
        provider.reset_stats()

        # Verify stats are reset
        assert provider.stats.fallback_calls == 0
        assert provider.stats.total_calls == 0


class TestCacheFallbackWrapper:
    """Test suite for CacheFallbackWrapper."""

    @pytest.mark.asyncio
    async def test_init_with_fallback_enabled(self):
        """Test initialization with fallback enabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, default_value="fallback_value")

        assert wrapper.cache == cache
        assert wrapper.default_value == "fallback_value"
        assert wrapper.enable_fallback is True
        assert wrapper.fallback_provider is not None

    @pytest.mark.asyncio
    async def test_init_with_fallback_disabled(self):
        """Test initialization with fallback disabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, enable_fallback=False)

        assert wrapper.enable_fallback is False
        assert wrapper.fallback_provider is None

    @pytest.mark.asyncio
    async def test_get_with_fallback_enabled(self):
        """Test get operation with fallback enabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, default_value="fallback_value")

        # Try to get non-existent key
        result = await wrapper.get("nonexistent_key")

        assert result == "fallback_value"

        # Verify fallback was used
        stats = wrapper.get_fallback_stats()
        assert stats is not None
        assert stats.fallback_calls == 1

    @pytest.mark.asyncio
    async def test_get_with_fallback_disabled(self):
        """Test get operation with fallback disabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, enable_fallback=False)

        # Try to get non-existent key - should raise CacheMissError
        with pytest.raises(CacheMissError):
            await wrapper.get("nonexistent_key")

        # Verify no fallback stats
        assert wrapper.get_fallback_stats() is None

    @pytest.mark.asyncio
    async def test_set_with_fallback_enabled(self):
        """Test set operation with fallback enabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, default_value="fallback_value")

        # Set value
        await wrapper.set("test_key", "test_value")

        # Verify value was set
        result = await cache.aget("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_fallback_disabled(self):
        """Test set operation with fallback disabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, enable_fallback=False)

        # Set value
        await wrapper.set("test_key", "test_value")

        # Verify value was set
        result = await cache.aget("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_clear_with_fallback_enabled(self):
        """Test clear operation with fallback enabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, default_value="fallback_value")

        # Add some data
        await cache.aset("key1", "value1")
        await cache.aset("key2", "value2")

        # Clear cache
        await wrapper.clear()

        # Verify cache is cleared
        assert cache.get_size() == 0

    @pytest.mark.asyncio
    async def test_fallback_stats_access(self):
        """Test access to fallback statistics."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, default_value="fallback_value")

        # Perform operation that triggers fallback
        await wrapper.get("nonexistent_key")

        # Get stats
        stats = wrapper.get_fallback_stats()
        assert stats is not None
        assert stats.fallback_calls == 1
        assert stats.fallback_success == 1

    @pytest.mark.asyncio
    async def test_fallback_stats_none_when_disabled(self):
        """Test that fallback stats are None when fallback is disabled."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, enable_fallback=False)

        # Get stats - should be None
        stats = wrapper.get_fallback_stats()
        assert stats is None

    @pytest.mark.asyncio
    async def test_integration_with_cache_errors(self):
        """Test integration with cache error handling."""
        cache = HighPerformanceLRUCache(capacity=100)
        wrapper = CacheFallbackWrapper(cache, default_value="fallback_value")

        # Corrupt cache to cause failures
        cache._ordered_dict = None

        # Operations should still work with fallback
        result = await wrapper.get("test_key")
        assert result == "fallback_value"

        # Set operations should not fail
        await wrapper.set("test_key", "test_value")

        # Verify fallback was used
        stats = wrapper.get_fallback_stats()
        assert stats is not None
        assert stats.fallback_calls >= 1
