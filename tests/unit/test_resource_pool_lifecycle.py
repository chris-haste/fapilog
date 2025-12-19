from __future__ import annotations

import pytest

from fapilog.core.resources import HttpClientPool


@pytest.mark.asyncio
async def test_http_client_pool_lifecycle() -> None:
    pool = HttpClientPool(max_size=1)
    await pool.start()
    async with pool.acquire() as client:
        assert client is not None
    await pool.stop()
