import asyncio

import pytest

from fapilog.core.errors import BackpressureError, FapilogError
from fapilog.core.resources import (
    AsyncResourcePool,
    CacheResourcePool,
    HttpClientPool,
    ResourceManager,
)


@pytest.mark.asyncio
async def test_generic_pool_constructor_validation():
    """Test AsyncResourcePool constructor validation."""
    created: list[int] = []

    async def create_item() -> int:
        item = len(created) + 1
        created.append(item)
        await asyncio.sleep(0)
        return item

    async def close_item(item: int) -> None:
        await asyncio.sleep(0)

    # Test invalid max_size
    with pytest.raises(ValueError, match="max_size must be > 0"):
        AsyncResourcePool[int](
            name="test",
            create_resource=create_item,
            close_resource=close_item,
            max_size=0,
            acquire_timeout_seconds=0.1,
        )

    with pytest.raises(ValueError, match="max_size must be > 0"):
        AsyncResourcePool[int](
            name="test",
            create_resource=create_item,
            close_resource=close_item,
            max_size=-1,
            acquire_timeout_seconds=0.1,
        )

    # Test invalid acquire_timeout_seconds
    with pytest.raises(ValueError, match="acquire_timeout_seconds must be > 0"):
        AsyncResourcePool[int](
            name="test",
            create_resource=create_item,
            close_resource=close_item,
            max_size=2,
            acquire_timeout_seconds=0,
        )

    with pytest.raises(ValueError, match="acquire_timeout_seconds must be > 0"):
        AsyncResourcePool[int](
            name="test",
            create_resource=create_item,
            close_resource=close_item,
            max_size=2,
            acquire_timeout_seconds=-1,
        )


@pytest.mark.asyncio
async def test_generic_pool_acquire_release():
    created: list[int] = []

    async def create_item() -> int:
        item = len(created) + 1
        created.append(item)
        await asyncio.sleep(0)
        return item

    async def close_item(item: int) -> None:
        await asyncio.sleep(0)

    pool = AsyncResourcePool[int](
        name="test",
        create_resource=create_item,
        close_resource=close_item,
        max_size=2,
        acquire_timeout_seconds=0.1,
    )

    async with pool.acquire() as a:
        assert a == 1
        async with pool.acquire() as b:
            assert b == 2

            # Third concurrent acquire should fail immediately via nowait
            with pytest.raises(BackpressureError):
                await pool.acquire_nowait()

    s = await pool.stats()
    assert s.created == 2
    assert s.in_use == 0

    await pool.cleanup()


@pytest.mark.asyncio
async def test_http_client_pool_basic():
    pool = HttpClientPool(max_size=2, acquire_timeout_seconds=0.1)
    async with pool.acquire() as client:
        assert client is not None
        # Do not perform real HTTP calls in unit test
    await pool.cleanup()


@pytest.mark.asyncio
async def test_resource_manager_register_and_cleanup():
    created: list[int] = []

    async def create_item() -> int:
        item = len(created) + 1
        created.append(item)
        await asyncio.sleep(0)
        return item

    async def close_item(item: int) -> None:
        await asyncio.sleep(0)

    pool = AsyncResourcePool[int](
        name="mgr",
        create_resource=create_item,
        close_resource=close_item,
        max_size=1,
        acquire_timeout_seconds=0.1,
    )

    manager = ResourceManager()
    await manager.register_pool("p1", pool)
    assert manager.get_pool("p1") is pool

    await manager.cleanup_all()
    stats = await manager.stats()
    assert "p1" in stats


@pytest.mark.asyncio
async def test_pool_acquire_timeout_backpressure():
    created: list[int] = []

    async def create_item() -> int:
        item = len(created) + 1
        created.append(item)
        await asyncio.sleep(0)
        return item

    async def close_item(item: int) -> None:
        await asyncio.sleep(0)

    # Single-capacity pool so second acquire must wait and then time out
    pool = AsyncResourcePool[int](
        name="timeout",
        create_resource=create_item,
        close_resource=close_item,
        max_size=1,
        acquire_timeout_seconds=0.05,
    )

    # Hold the only resource
    cm = pool.acquire()
    await cm.__aenter__()

    async def try_second_acquire() -> bool:
        second = pool.acquire()
        try:
            await second.__aenter__()
        except BackpressureError:
            return True
        finally:
            # Ensure context closed if it ever succeeded unexpectedly
            try:
                await second.__aexit__(None, None, None)
            except Exception:
                pass
        return False

    ok = await try_second_acquire()
    assert ok is True

    # Cleanup while first resource is still in use
    await pool.cleanup()


@pytest.mark.asyncio
async def test_cleanup_closes_in_use_resource():
    closed: list[int] = []

    async def create_item() -> int:
        return 1

    async def close_item(item: int) -> None:
        closed.append(item)

    pool = AsyncResourcePool[int](
        name="inuse",
        create_resource=create_item,
        close_resource=close_item,
        max_size=1,
        acquire_timeout_seconds=0.1,
    )

    # Acquire but do not release so it's considered in-use
    cm = pool.acquire()
    await cm.__aenter__()

    await pool.cleanup()
    assert closed == [1]


@pytest.mark.asyncio
async def test_resource_manager_duplicate_register_error():
    created: list[int] = []

    async def create_item() -> int:
        item = len(created) + 1
        created.append(item)
        return item

    async def close_item(item: int) -> None:
        pass

    pool = AsyncResourcePool[int](
        name="dup",
        create_resource=create_item,
        close_resource=close_item,
        max_size=1,
        acquire_timeout_seconds=0.1,
    )

    manager = ResourceManager()
    await manager.register_pool("p", pool)
    with pytest.raises(FapilogError):
        await manager.register_pool("p", pool)


@pytest.mark.asyncio
async def test_http_client_pool_cleanup_calls_aclose(monkeypatch):
    import fapilog.core.resources as res

    closed = {"count": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            pass

        async def aclose(self) -> None:  # noqa: D401
            closed["count"] += 1

    monkeypatch.setattr(res.httpx, "AsyncClient", FakeClient)

    pool = res.HttpClientPool(max_size=2, acquire_timeout_seconds=0.1)
    # Create two distinct clients by holding the first while acquiring the
    # second
    cm1 = pool.acquire()
    await cm1.__aenter__()
    cm2 = pool.acquire()
    await cm2.__aenter__()
    # Release both
    await cm2.__aexit__(None, None, None)
    await cm1.__aexit__(None, None, None)

    await pool.cleanup()
    assert closed["count"] >= 2


@pytest.mark.asyncio
async def test_manager_parallel_cleanup_two_pools(monkeypatch):
    import fapilog.core.resources as res

    closed_counts = {"http": 0, "other": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            pass

        async def aclose(self) -> None:  # noqa: D401
            closed_counts["http"] += 1

    monkeypatch.setattr(res.httpx, "AsyncClient", FakeClient)

    http_pool = res.HttpClientPool(max_size=1, acquire_timeout_seconds=0.1)

    async def create_other() -> int:
        return 1

    async def close_other(_: int) -> None:
        closed_counts["other"] += 1

    other_pool = res.AsyncResourcePool[int](
        name="other",
        create_resource=create_other,
        close_resource=close_other,
        max_size=1,
        acquire_timeout_seconds=0.1,
    )

    mgr = res.ResourceManager()
    await mgr.register_pool("http", http_pool)
    await mgr.register_pool("other", other_pool)

    # Create both resources
    async with http_pool.acquire():
        pass
    async with other_pool.acquire():
        pass

    # Ensure cleanup_all does not raise
    await mgr.cleanup_all()
    assert closed_counts["http"] >= 1
    assert closed_counts["other"] >= 1


# CacheResourcePool Tests
@pytest.mark.asyncio
async def test_cache_resource_pool_basic():
    """Test basic cache resource pool functionality."""
    pool = CacheResourcePool(
        name="test-cache",
        max_size=2,
        cache_capacity=100,
        acquire_timeout_seconds=0.1,
    )

    # Acquire cache instances
    async with pool.acquire() as cache1:
        assert cache1 is not None
        assert hasattr(cache1, "get")
        assert hasattr(cache1, "set")
        assert hasattr(cache1, "aget")
        assert hasattr(cache1, "aset")

        # Test cache functionality
        cache1.set("key1", "value1")
        assert cache1.get("key1") == "value1"

    async with pool.acquire() as cache2:
        assert cache2 is not None
        # Cache instances may be reused from the pool
        # The key should still be there if the same instance is reused
        assert cache2.get("key1") == "value1"

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_capacity_limits():
    """Test that cache resource pool respects capacity limits."""
    pool = CacheResourcePool(
        name="capacity-test",
        max_size=2,
        cache_capacity=50,
        acquire_timeout_seconds=0.1,
    )

    # Acquire first cache
    cm1 = pool.acquire()
    await cm1.__aenter__()

    # Acquire second cache
    cm2 = pool.acquire()
    await cm2.__aenter__()

    # Third acquire should fail immediately
    with pytest.raises(BackpressureError):
        await pool.acquire_nowait()

    # Release resources
    await cm2.__aexit__(None, None, None)
    await cm1.__aexit__(None, None, None)

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_timeout_backpressure():
    """Test timeout behavior when pool is at capacity."""
    pool = CacheResourcePool(
        name="timeout-test",
        max_size=1,
        cache_capacity=100,
        acquire_timeout_seconds=0.05,
    )

    # Hold the only resource
    cm = pool.acquire()
    await cm.__aenter__()

    # Second acquire should timeout and raise BackpressureError
    async def try_second_acquire() -> bool:
        second = pool.acquire()
        try:
            await second.__aenter__()
        except BackpressureError:
            return True
        finally:
            try:
                await second.__aexit__(None, None, None)
            except Exception:
                pass
        return False

    ok = await try_second_acquire()
    assert ok is True

    # Cleanup while first resource is still in use
    await cm.__aexit__(None, None, None)
    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_cleanup_clears_caches():
    """Test that cleanup properly clears cache contents."""
    pool = CacheResourcePool(
        name="cleanup-test",
        max_size=2,
        cache_capacity=100,
        acquire_timeout_seconds=0.1,
    )

    # Acquire and populate caches
    async with pool.acquire() as cache1:
        cache1.set("key1", "value1")
        cache1.set("key2", "value2")
        assert cache1.get_size() == 2

    async with pool.acquire() as cache2:
        cache2.set("key3", "value3")
        # Cache instance may be reused, so size could be 3 (key1, key2, key3)
        assert cache2.get_size() >= 1

    # Cleanup should clear all caches
    await pool.cleanup()

    # Verify caches are cleared
    async with pool.acquire() as cache3:
        assert cache3.get_size() == 0
        assert cache3.get("key1") is None
        assert cache3.get("key2") is None

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_with_resource_manager():
    """Test CacheResourcePool integration with ResourceManager."""
    pool = CacheResourcePool(
        name="manager-test",
        max_size=3,
        cache_capacity=200,
        acquire_timeout_seconds=0.1,
    )

    manager = ResourceManager()
    await manager.register_pool("cache-pool", pool)

    assert manager.get_pool("cache-pool") is pool

    # Use the pool through the manager
    async with pool.acquire() as cache:
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

    # Cleanup through manager
    await manager.cleanup_all()

    # Verify pool is cleaned up
    stats = await manager.stats()
    assert "cache-pool" in stats


@pytest.mark.asyncio
async def test_cache_resource_pool_stats():
    """Test that CacheResourcePool provides accurate statistics."""
    pool = CacheResourcePool(
        name="stats-test",
        max_size=2,
        cache_capacity=100,
        acquire_timeout_seconds=0.1,
    )

    # Initial stats
    stats = await pool.stats()
    assert stats.name == "stats-test"
    assert stats.max_size == 2
    assert stats.created == 0
    assert stats.in_use == 0
    assert stats.idle == 0

    # Acquire first cache
    async with pool.acquire() as _:
        stats = await pool.stats()
        assert stats.created == 1
        assert stats.in_use == 1
        assert stats.idle == 0

        # Acquire second cache
        async with pool.acquire() as _:
            stats = await pool.stats()
            assert stats.created == 2
            assert stats.in_use == 2
            assert stats.idle == 0

    # After release, both should be idle
    stats = await pool.stats()
    assert stats.created == 2
    assert stats.in_use == 0
    assert stats.idle == 2

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_concurrent_access():
    """Test concurrent access to cache resource pool."""
    pool = CacheResourcePool(
        name="concurrent-test",
        max_size=5,
        cache_capacity=100,
        acquire_timeout_seconds=0.1,
    )

    async def use_cache(cache_id: int) -> None:
        async with pool.acquire() as cache:
            cache.set(f"key_{cache_id}", f"value_{cache_id}")
            await asyncio.sleep(0.01)  # Simulate work
            assert cache.get(f"key_{cache_id}") == f"value_{cache_id}"

    # Create multiple concurrent tasks
    tasks = [use_cache(i) for i in range(10)]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Verify pool stats
    stats = await pool.stats()
    assert stats.created <= 5  # Should not exceed max_size
    assert stats.in_use == 0  # All should be released
    assert stats.idle <= 5  # Should not exceed max_size

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_custom_capacity():
    """Test CacheResourcePool with custom cache capacity."""
    pool = CacheResourcePool(
        name="custom-capacity",
        max_size=2,
        cache_capacity=500,
        acquire_timeout_seconds=0.1,
    )

    async with pool.acquire() as cache:
        # Test that cache respects the custom capacity
        for i in range(600):  # Exceed capacity
            cache.set(f"key_{i}", f"value_{i}")

        # Should not exceed capacity
        assert cache.get_size() <= 500

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_metrics_integration():
    """Test CacheResourcePool integration with metrics collector."""
    from fapilog.metrics.metrics import MetricsCollector

    # Create a simple metrics collector
    metrics = MetricsCollector()

    pool = CacheResourcePool(
        name="metrics-test",
        max_size=2,
        cache_capacity=100,
        acquire_timeout_seconds=0.1,
        metrics=metrics,
    )

    # Use the pool to trigger metrics
    async with pool.acquire() as cache:
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

    await pool.cleanup()


@pytest.mark.asyncio
async def test_cache_resource_pool_error_handling():
    """Test error handling in CacheResourcePool."""
    pool = CacheResourcePool(
        name="error-test",
        max_size=1,
        cache_capacity=100,
        acquire_timeout_seconds=0.1,
    )

    # Test that cleanup never raises exceptions
    try:
        await pool.cleanup()
    except Exception as e:
        pytest.fail(f"Cleanup should not raise exceptions: {e}")

    # Test that acquire after cleanup creates new resources
    async with pool.acquire() as cache:
        assert cache is not None
        cache.set("key", "value")
        assert cache.get("key") == "value"

    await pool.cleanup()
