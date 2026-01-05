from __future__ import annotations

import hashlib

import pytest

from fapilog.plugins.filters.trace_sampling import (
    TraceSamplingConfig,
    TraceSamplingFilter,
)


def _should_sample(trace_id: str, rate: float) -> bool:
    hash_value = int(hashlib.md5(str(trace_id).encode()).hexdigest(), 16)
    threshold = int(rate * (2**128))
    return hash_value < threshold


@pytest.mark.asyncio
async def test_trace_sampling_is_deterministic() -> None:
    cfg = TraceSamplingConfig(sample_rate=0.5)
    filt = TraceSamplingFilter(config=cfg)

    evt = {"trace_id": "abc123", "level": "INFO"}
    first = await filt.filter(evt)
    second = await filt.filter(evt)

    expected = _should_sample("abc123", cfg.sample_rate)
    assert bool(first) == expected
    assert bool(second) == expected


@pytest.mark.asyncio
async def test_trace_sampling_respects_field_name() -> None:
    cfg = TraceSamplingConfig(sample_rate=0.8, trace_id_field="tid")
    filt = TraceSamplingFilter(config=cfg)

    evt = {"tid": "custom-trace", "level": "INFO"}
    result = await filt.filter(evt)
    expected = _should_sample("custom-trace", cfg.sample_rate)
    assert bool(result) == expected


@pytest.mark.asyncio
async def test_trace_sampling_falls_back_to_random(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filt = TraceSamplingFilter(config=TraceSamplingConfig(sample_rate=0.2))

    monkeypatch.setattr(
        "fapilog.plugins.filters.trace_sampling.random.random", lambda: 0.99
    )
    assert await filt.filter({"level": "INFO"}) is None

    monkeypatch.setattr(
        "fapilog.plugins.filters.trace_sampling.random.random", lambda: 0.0
    )
    assert await filt.filter({"level": "INFO"}) == {"level": "INFO"}


@pytest.mark.asyncio
async def test_trace_sampling_priority_levels_pass() -> None:
    filt = TraceSamplingFilter(
        config=TraceSamplingConfig(sample_rate=0.0, always_pass_levels=["error"])
    )

    evt = {"level": "ERROR", "trace_id": "ignored"}
    assert await filt.filter(evt) == evt
