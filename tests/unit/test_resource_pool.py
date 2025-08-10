import asyncio

import pytest

from fapilog.core.errors import BackpressureError, FapilogError
from fapilog.core.resources import (
    AsyncResourcePool,
    HttpClientPool,
    ResourceManager,
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
