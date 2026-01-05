from __future__ import annotations

import pytest

from fapilog.plugins.filters.first_occurrence import (
    FirstOccurrenceConfig,
    FirstOccurrenceFilter,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


@pytest.mark.asyncio
async def test_first_occurrence_passes_then_drops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fapilog.plugins.filters import first_occurrence as module

    clock = _FakeClock()
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module.random, "random", lambda: 0.99)

    filt = FirstOccurrenceFilter(
        config=FirstOccurrenceConfig(subsequent_sample_rate=0.0)
    )
    await filt.start()

    evt = {"message": "hello"}
    assert await filt.filter(evt) == evt
    assert await filt.filter(evt) is None


@pytest.mark.asyncio
async def test_first_occurrence_window_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fapilog.plugins.filters import first_occurrence as module

    clock = _FakeClock()
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module.random, "random", lambda: 0.0)

    filt = FirstOccurrenceFilter(
        config=FirstOccurrenceConfig(window_seconds=2.0, subsequent_sample_rate=0.0)
    )
    await filt.start()

    evt = {"message": "event"}
    assert await filt.filter(evt) == evt

    clock.advance(3.0)
    assert await filt.filter(evt) == evt


@pytest.mark.asyncio
async def test_first_occurrence_lru_eviction(monkeypatch: pytest.MonkeyPatch) -> None:
    from fapilog.plugins.filters import first_occurrence as module

    clock = _FakeClock()
    monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(module.random, "random", lambda: 0.0)

    filt = FirstOccurrenceFilter(
        config=FirstOccurrenceConfig(max_keys=2, subsequent_sample_rate=0.0)
    )
    await filt.start()

    await filt.filter({"message": "a"})
    await filt.filter({"message": "b"})
    await filt.filter({"message": "c"})

    assert set(filt._seen.keys()) == {"b", "c"}
