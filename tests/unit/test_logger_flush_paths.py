import pytest

import fapilog.core.logger as logger_mod
from fapilog.core.logger import AsyncLoggerFacade


@pytest.mark.asyncio
async def test_flush_serialization_strict_drops(monkeypatch):
    monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "true")

    async def sink_write(entry: dict) -> None:  # pragma: no cover - not used
        raise AssertionError("should not be called in strict drop path")

    async def sink_write_serialized(view: object) -> None:
        raise AssertionError("should not be called in strict drop path")

    monkeypatch.setattr(
        logger_mod,
        "serialize_envelope",
        lambda entry: (_ for _ in ()).throw(ValueError("boom")),
    )

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=4,
        batch_max_size=2,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        serialize_in_flush=True,
    )

    batch = [{"id": 1}]
    await logger._flush_batch(batch)

    assert logger._processed == 0
    assert logger._dropped == 0


@pytest.mark.asyncio
async def test_flush_serialization_best_effort_uses_fallback(monkeypatch):
    monkeypatch.setenv("FAPILOG_CORE__STRICT_ENVELOPE_MODE", "false")

    serialized_calls: list[object] = []
    sink_calls: list[dict] = []

    async def sink_write(entry: dict) -> None:
        sink_calls.append(entry)

    async def sink_write_serialized(view: object) -> None:
        serialized_calls.append(view)

    monkeypatch.setattr(
        logger_mod,
        "serialize_envelope",
        lambda entry: (_ for _ in ()).throw(ValueError("boom")),
    )

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=4,
        batch_max_size=2,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        serialize_in_flush=True,
    )

    batch = [{"id": 1}]
    await logger._flush_batch(batch)

    assert logger._processed == 1
    assert len(serialized_calls) == 1
    assert len(sink_calls) == 0


@pytest.mark.asyncio
async def test_flush_sink_error_increments_dropped(monkeypatch):
    async def sink_write(entry: dict) -> None:
        raise RuntimeError("sink failure")

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=4,
        batch_max_size=2,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink_write,
        serialize_in_flush=False,
    )

    batch = [{"id": 1}, {"id": 2}]
    await logger._flush_batch(batch)

    assert logger._processed == 0
    assert logger._dropped == 2
