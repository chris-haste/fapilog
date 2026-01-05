from __future__ import annotations

import pytest

from fapilog.plugins.filters.adaptive_sampling import (
    AdaptiveSamplingConfig,
    AdaptiveSamplingFilter,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


@pytest.mark.asyncio
async def test_adaptive_sampling_adjusts_rates(monkeypatch: pytest.MonkeyPatch) -> None:
    from fapilog.plugins.filters import adaptive_sampling as module

    clock = _FakeClock()
    monkeypatch.setattr(module, "time", clock)

    filt = AdaptiveSamplingFilter(
        config=AdaptiveSamplingConfig(
            target_eps=2.0,
            window_seconds=10.0,
            min_sample_rate=0.05,
            max_sample_rate=1.0,
            smoothing_factor=1.0,
        )
    )

    # High throughput should drive the rate down but stay above the minimum
    clock.now = 5.0
    filt._timestamps.extend([4.5, 4.55, 4.6, 4.65, 4.7])
    filt._last_adjustment = 3.0
    filt._current_rate = 1.0
    filt._maybe_adjust_rate()
    rate_after_high = filt.current_sample_rate
    assert rate_after_high < 1.0
    assert rate_after_high >= 0.05

    # Low throughput should allow the rate to move back up toward max
    filt._timestamps.clear()
    filt._timestamps.extend([19.0])
    clock.now = 20.0
    filt._last_adjustment = 18.0
    filt._current_rate = 0.1
    filt._maybe_adjust_rate()
    rate_after_low = filt.current_sample_rate
    assert rate_after_low > 0.1
    assert rate_after_low <= 1.0


@pytest.mark.asyncio
async def test_adaptive_sampling_prunes_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from fapilog.plugins.filters import adaptive_sampling as module

    clock = _FakeClock()
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module.random, "random", lambda: 0.0)

    filt = AdaptiveSamplingFilter(
        config=AdaptiveSamplingConfig(window_seconds=5.0, smoothing_factor=1.0)
    )
    await filt.start()

    clock.now = 0.0
    await filt.filter({"level": "INFO"})

    clock.advance(10.0)
    await filt.filter({"level": "INFO"})

    assert len(filt._timestamps) == 1
    assert filt._timestamps[0] >= clock.now - filt._window


@pytest.mark.asyncio
async def test_adaptive_sampling_priority_levels_always_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fapilog.plugins.filters import adaptive_sampling as module

    clock = _FakeClock()
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module.random, "random", lambda: 1.0)

    filt = AdaptiveSamplingFilter(
        config=AdaptiveSamplingConfig(min_sample_rate=0.0, max_sample_rate=0.2)
    )

    event = {"level": "error", "message": "fail"}
    assert await filt.filter(event) == event
