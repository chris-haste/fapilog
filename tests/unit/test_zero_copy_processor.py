import pytest

from fapilog.core.events import LogEvent
from fapilog.core.serialization import serialize_mapping_to_json_bytes
from fapilog.plugins.processors.zero_copy import ZeroCopyProcessor


@pytest.mark.asyncio
async def test_process_returns_same_view() -> None:
    evt = LogEvent(level="INFO", message="zcp")
    view = serialize_mapping_to_json_bytes(evt.to_mapping())
    proc = ZeroCopyProcessor()
    out = await proc.process(view.view)
    # Ensure zero-copy: identity or at least same bytes
    assert out.tobytes() == view.view.tobytes()


@pytest.mark.asyncio
async def test_process_many_counts() -> None:
    proc = ZeroCopyProcessor()
    events = [LogEvent(level="DEBUG", message=f"m{i}") for i in range(5)]
    views = [serialize_mapping_to_json_bytes(e.to_mapping()).view for e in events]
    n = await proc.process_many(views)
    assert n == len(views)
