from __future__ import annotations

import pytest

from fapilog.plugins.filters.level import LevelFilter, LevelFilterConfig


@pytest.mark.asyncio
async def test_level_filter_drops_below_threshold() -> None:
    filt = LevelFilter(config=LevelFilterConfig(min_level="INFO"))
    assert await filt.filter({"level": "DEBUG"}) is None
    assert await filt.filter({"level": "info"}) == {"level": "info"}
    assert await filt.filter({"level": "WARNING"}) == {"level": "WARNING"}


@pytest.mark.asyncio
async def test_level_filter_drop_below_false_keeps_all() -> None:
    filt = LevelFilter(config=LevelFilterConfig(min_level="ERROR", drop_below=False))
    evt = {"level": "DEBUG", "msg": "keep"}
    assert await filt.filter(evt) == evt
