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


@pytest.mark.asyncio
async def test_sampling_filter_uses_per_instance_rng() -> None:
    """Two SamplingFilters with same seed should produce identical sequences.

    This tests that each filter has its own RNG instance rather than using
    global random state, which would cause interference between filters.
    """
    seed = 12345
    filt1 = SamplingFilter(config=SamplingFilterConfig(sample_rate=0.5, seed=seed))
    filt2 = SamplingFilter(config=SamplingFilterConfig(sample_rate=0.5, seed=seed))

    results1 = []
    results2 = []

    for _ in range(50):
        r1 = await filt1.filter({"level": "INFO"})
        r2 = await filt2.filter({"level": "INFO"})
        results1.append(r1 is not None)
        results2.append(r2 is not None)

    # With per-instance RNG, identical seeds produce identical sequences
    assert results1 == results2


@pytest.mark.asyncio
async def test_sampling_filter_instances_do_not_interfere() -> None:
    """Creating a new filter should not affect another filter's sequence.

    If using global random.seed(), creating filt2 would reset the global state
    and interfere with filt1's sequence.
    """
    filt1 = SamplingFilter(config=SamplingFilterConfig(sample_rate=0.5, seed=999))

    # Collect first 20 results from filt1
    first_run = []
    for _ in range(20):
        r = await filt1.filter({"level": "INFO"})
        first_run.append(r is not None)

    # Create fresh filter with same seed, collect 40 results
    filt1_fresh = SamplingFilter(config=SamplingFilterConfig(sample_rate=0.5, seed=999))
    # Create another filter mid-sequence (would interfere with global state)
    _filt_interfere = SamplingFilter(
        config=SamplingFilterConfig(sample_rate=0.5, seed=1)
    )

    full_run = []
    for _ in range(40):
        r = await filt1_fresh.filter({"level": "INFO"})
        full_run.append(r is not None)

    # The first 20 results should match regardless of other filter creation
    assert first_run == full_run[:20]
