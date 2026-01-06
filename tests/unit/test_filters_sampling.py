from __future__ import annotations

import pytest

from fapilog.plugins.filters.sampling import SamplingFilter, SamplingFilterConfig


@pytest.mark.asyncio
async def test_sampling_filter_all_or_none() -> None:
    keep_all = SamplingFilter(config=SamplingFilterConfig(sample_rate=1.0, seed=42))
    drop_all = SamplingFilter(config=SamplingFilterConfig(sample_rate=0.0, seed=42))

    evt = {"level": "INFO"}
    assert await keep_all.filter(evt) == evt
    assert await drop_all.filter(evt) is None


@pytest.mark.asyncio
async def test_sampling_filter_probabilistic_with_seed() -> None:
    filt = SamplingFilter(config=SamplingFilterConfig(sample_rate=0.5, seed=1234))
    kept = 0
    total = 200
    for _ in range(total):
        if await filt.filter({"level": "INFO"}):
            kept += 1
    assert 60 < kept < 140


@pytest.mark.asyncio
async def test_sampling_filter_accepts_dict_and_coerces() -> None:
    filt = SamplingFilter(config={"config": {"sample_rate": "0.25", "seed": 1}})
    assert pytest.approx(filt.current_sample_rate) == 0.25
