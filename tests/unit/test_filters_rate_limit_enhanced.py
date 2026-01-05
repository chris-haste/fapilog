from __future__ import annotations

import pytest

from fapilog.plugins.filters.rate_limit import RateLimitFilter, RateLimitFilterConfig


@pytest.mark.asyncio
async def test_rate_limit_lru_eviction_and_isolation() -> None:
    filt = RateLimitFilter(
        config=RateLimitFilterConfig(
            capacity=5,
            refill_rate_per_sec=1.0,
            key_field="user",
            max_keys=2,
        )
    )

    await filt.start()
    await filt.filter({"user": "a"})
    await filt.filter({"user": "b"})
    assert set(filt._buckets.keys()) == {"a", "b"}

    await filt.filter({"user": "c"})
    assert set(filt._buckets.keys()) == {"b", "c"}


@pytest.mark.asyncio
async def test_rate_limit_overflow_action_mark_instead_of_drop() -> None:
    filt = RateLimitFilter(
        config=RateLimitFilterConfig(
            capacity=1,
            refill_rate_per_sec=0.0,
            key_field="account",
            overflow_action="mark",
        )
    )

    await filt.start()
    first = await filt.filter({"account": "x"})
    assert first == {"account": "x"}

    second = await filt.filter({"account": "x"})
    assert second is not None
    assert second.get("rate_limited") is True


@pytest.mark.asyncio
async def test_rate_limit_health_check_warns_near_capacity() -> None:
    filt = RateLimitFilter(
        config=RateLimitFilterConfig(
            capacity=1,
            refill_rate_per_sec=0.0,
            key_field="user",
            max_keys=10,
        )
    )

    await filt.start()
    for i in range(10):
        await filt.filter({"user": f"u{i}"})

    assert await filt.health_check() is False
