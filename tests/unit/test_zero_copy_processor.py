import asyncio

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
async def test_process_returns_identical_memoryview_instance() -> None:
    evt = LogEvent(level="INFO", message="zcp-id")
    view = serialize_mapping_to_json_bytes(evt.to_mapping())
    proc = ZeroCopyProcessor()
    in_mv = view.view
    out = await proc.process(in_mv)
    # Zero-copy contract: same memoryview instance (identity)
    assert out is in_mv


@pytest.mark.asyncio
async def test_process_many_counts() -> None:
    proc = ZeroCopyProcessor()
    events = [LogEvent(level="DEBUG", message=f"m{i}") for i in range(5)]
    views = [serialize_mapping_to_json_bytes(e.to_mapping()).view for e in events]
    n = await proc.process_many(views)
    assert n == len(views)


@pytest.mark.asyncio
async def test_process_many_with_generator_iterable() -> None:
    proc = ZeroCopyProcessor()
    events = (LogEvent(level="DEBUG", message=f"g{i}") for i in range(7))
    views = (serialize_mapping_to_json_bytes(e.to_mapping()).view for e in events)
    n = await proc.process_many(views)
    assert n == 7


@pytest.mark.asyncio
async def test_process_many_serializes_access_with_lock() -> None:
    proc = ZeroCopyProcessor()

    current: int = 0
    max_seen: int = 0

    orig = proc.process

    async def slow_process(v):  # type: ignore[no-untyped-def]
        nonlocal current, max_seen
        current += 1
        if current > max_seen:
            max_seen = current
        # Simulate work while the lock is held by process_many
        await asyncio.sleep(0.005)
        result = await orig(v)
        current -= 1
        return result

    # Monkeypatch the instance method to introduce measurable latency
    proc.process = slow_process  # type: ignore[assignment]

    # Two overlapping batches should be processed without concurrent entry
    # to the slow_process because process_many holds a lock around the loop
    events1 = [LogEvent(level="INFO", message=f"a{i}") for i in range(5)]
    events2 = [LogEvent(level="INFO", message=f"b{i}") for i in range(5)]
    views1 = [serialize_mapping_to_json_bytes(e.to_mapping()).view for e in events1]
    views2 = [serialize_mapping_to_json_bytes(e.to_mapping()).view for e in events2]

    await asyncio.gather(proc.process_many(views1), proc.process_many(views2))
    # If the lock serialized access, the maximum concurrent invocations is 1
    assert max_seen == 1


@pytest.mark.asyncio
async def test_process_many_empty_iterable_returns_zero() -> None:
    proc = ZeroCopyProcessor()
    n = await proc.process_many(())
    assert n == 0
