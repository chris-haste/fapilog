from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fapilog.plugins.filters.level import LEVEL_PRIORITY, LevelFilter

pytestmark = pytest.mark.property

LEVEL_NAMES = list(LEVEL_PRIORITY.keys())


def maybe_lower(level: str) -> st.SearchStrategy[str]:
    return st.sampled_from([level, level.lower()])


level_names = st.sampled_from(LEVEL_NAMES).flatmap(maybe_lower)


@pytest.mark.asyncio
@given(min_level=level_names, event_level=level_names)
async def test_level_filter_respects_hierarchy(
    min_level: str, event_level: str
) -> None:
    filt = LevelFilter(config={"min_level": min_level, "drop_below": True})
    event = {"level": event_level}

    result = await filt.filter(event)
    min_priority = LEVEL_PRIORITY[min_level.upper()]
    event_priority = LEVEL_PRIORITY[event_level.upper()]

    if event_priority < min_priority:
        assert result is None
    else:
        assert result == event


@pytest.mark.asyncio
@given(min_level=level_names, event_level=level_names)
async def test_level_filter_drop_below_false_keeps_event(
    min_level: str, event_level: str
) -> None:
    filt = LevelFilter(config={"min_level": min_level, "drop_below": False})
    event = {"level": event_level}

    result = await filt.filter(event)
    assert result == event
