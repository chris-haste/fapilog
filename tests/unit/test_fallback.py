import asyncio
from typing import Any

import pytest

from fapilog.core.fallback import (
    AsyncFallbackWrapper,
    CacheFallback,
    FallbackConfig,
    FallbackManager,
    FallbackStrategy,
    FallbackTrigger,
    StaticValueFallback,
    with_fallback,
)
from fapilog.core.fallback import (
    fallback as fallback_decorator,
)


@pytest.mark.asyncio
async def test_fallback_config_defaults_and_stats_rates() -> None:
    cfg = FallbackConfig()
    assert cfg.strategy == FallbackStrategy.STATIC_VALUE
    # Defaults set when not provided
    assert cfg.triggers == [FallbackTrigger.EXCEPTION, FallbackTrigger.TIMEOUT]

    # FallbackStats rates
    from fapilog.core.fallback import FallbackStats

    stats = FallbackStats()
    assert stats.fallback_rate == 0.0
    assert stats.primary_success_rate == 0.0
    stats.total_calls = 10
    stats.fallback_calls = 4
    stats.primary_success = 6
    assert stats.fallback_rate == 0.4
    assert stats.primary_success_rate == 1.0  # 6/6 primary attempts


@pytest.mark.asyncio
async def test_cache_fallback_and_cache_result_on_success() -> None:
    # Prepare cache fallback provider
    cache: dict[str, Any] = {}

    def key_gen(x: int) -> str:  # noqa: D401
        return f"k:{x}"

    provider = CacheFallback(cache, key_gen, default_value=-1)
    # Configure wrapper to cache primary successes
    cfg = FallbackConfig(
        strategy=FallbackStrategy.CACHE_LOOKUP,
        cache_key_generator=key_gen,
    )
    wrapper = AsyncFallbackWrapper("cache-test", provider, cfg)

    async def primary(x: int) -> int:
        return x * 2

    # First call: primary succeeds and caches (wrapper maintains its own cache)
    out = await wrapper.execute(primary, 5)
    assert out == 10
    assert wrapper._cache.get("k:5", None) == 10  # type: ignore[attr-defined]

    # Fallback provider returns from cache on miss/hit
    res = await provider.provide_fallback(6)  # miss -> default
    assert res == -1
    cache["k:6"] = 12
    res2 = await provider.provide_fallback(6)
    assert res2 == 12


@pytest.mark.asyncio
async def test_high_latency_triggers_fallback_and_updates_stats() -> None:
    provider = StaticValueFallback("slow_fallback")
    cfg = FallbackConfig(
        strategy=FallbackStrategy.STATIC_VALUE,
        latency_threshold=0.01,
        triggers=[FallbackTrigger.HIGH_LATENCY],
    )
    wrapper = AsyncFallbackWrapper("latency-op", provider, cfg)

    async def slow() -> str:
        await asyncio.sleep(0.02)
        return "ok"

    out = await wrapper.execute(slow)
    assert out == "slow_fallback"
    # Trigger count updated
    assert wrapper.stats.trigger_counts[FallbackTrigger.HIGH_LATENCY] == 1


@pytest.mark.asyncio
async def test_decorator_preserves_metadata_and_calls() -> None:
    fallback_provider = StaticValueFallback("decor_fallback")
    dec = fallback_decorator(fallback_provider)

    async def fn(a: int) -> int:
        """Docstring."""
        raise RuntimeError("fail")

    wrapped = dec(fn)
    assert wrapped.__name__ == fn.__name__
    assert wrapped.__doc__ == fn.__doc__
    assert wrapped.__annotations__ == fn.__annotations__
    out = await wrapped(1)
    assert out == "decor_fallback"


@pytest.mark.asyncio
async def test_manager_register_get_unregister_cleanup_and_with_fallback() -> None:
    mgr = FallbackManager()
    prov = StaticValueFallback("val")
    # Register
    wrapper = await mgr.register("w1", prov, FallbackConfig())
    assert (await mgr.get("w1")) is wrapper
    # Duplicate register should error
    with pytest.raises(ValueError):
        await mgr.register("w1", prov, FallbackConfig())
    # List
    assert "w1" in mgr.list_fallback_wrappers()
    # Stats available shape
    stats = await mgr.get_all_stats()
    assert "w1" in stats
    # Unregister true/false
    assert await mgr.unregister("w1") is True
    assert await mgr.unregister("w1") is False
    # Cleanup
    await mgr.register("w2", prov, FallbackConfig())
    await mgr.cleanup()
    assert mgr.list_fallback_wrappers() == []
    # with_fallback creates or reuses global manager instance
    w_a = await with_fallback("wf", StaticValueFallback("A"))
    w_b = await with_fallback("wf", StaticValueFallback("B"))
    assert w_a is w_b
