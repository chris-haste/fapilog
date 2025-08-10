import asyncio

import pytest

from fapilog.core.errors import BackpressureError
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
