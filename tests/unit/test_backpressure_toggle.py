import asyncio

import pytest

from fapilog.core import diagnostics
from fapilog.core.logger import AsyncLoggerFacade


@pytest.mark.asyncio
async def test_async_enqueue_drops_when_drop_on_full_true():
    async def sink_write(entry: dict) -> None:
        return None

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=1,
        batch_max_size=1,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink_write,
    )

    # Fill queue to capacity, then attempt another enqueue
    assert logger._queue.try_enqueue({"id": 1})

    result = await asyncio.wait_for(
        logger._async_enqueue({"id": 2}, timeout=0.005), timeout=0.5
    )

    assert result is False
    assert logger._queue.qsize() == 1


@pytest.mark.asyncio
async def test_async_enqueue_waits_when_drop_on_full_false():
    async def sink_write(entry: dict) -> None:
        return None

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=1,
        batch_max_size=1,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=5,
        drop_on_full=False,
        sink_write=sink_write,
    )

    # Fill queue to capacity
    assert logger._queue.try_enqueue({"id": 1})

    async def free_capacity() -> None:
        await asyncio.sleep(0.01)
        logger._queue.try_dequeue()

    freer = asyncio.create_task(free_capacity())

    result = await asyncio.wait_for(
        logger._async_enqueue({"id": 2}, timeout=0.005), timeout=0.5
    )

    await freer

    assert result is True
    assert logger._queue.qsize() == 1


@pytest.mark.asyncio
async def test_flush_emits_diagnostics_on_sink_error(monkeypatch):
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")

    captured: list[dict] = []
    diagnostics.set_writer_for_tests(lambda payload: captured.append(payload))

    async def sink_write(entry: dict) -> None:
        raise RuntimeError("boom")

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=4,
        batch_max_size=2,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink_write,
    )

    batch = [{"id": 1}]
    await logger._flush_batch(batch)

    assert any(
        p.get("component") == "sink" and p.get("message") == "flush error"
        for p in captured
    ), captured

    # Cleanup env for isolation
    monkeypatch.delenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", raising=False)


class _FailingEnricher:
    name = "failing"

    async def enrich(self, entry: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("enrich boom")


@pytest.mark.asyncio
async def test_flush_emits_diagnostics_on_enricher_error(monkeypatch):
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")
    captured: list[dict] = []
    diagnostics.set_writer_for_tests(lambda payload: captured.append(payload))

    async def sink_write(entry: dict) -> None:
        return None

    logger = AsyncLoggerFacade(
        name="test",
        queue_capacity=4,
        batch_max_size=2,
        batch_timeout_seconds=1.0,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=sink_write,
        enrichers=[_FailingEnricher()],  # type: ignore[arg-type]
    )

    batch = [{"id": 1}]
    await logger._flush_batch(batch)

    assert any(
        p.get("component") == "enricher" and p.get("message") == "enrichment error"
        for p in captured
    ), captured

    # Cleanup env for isolation
    monkeypatch.delenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", raising=False)
