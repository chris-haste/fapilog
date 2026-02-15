import pytest

from fapilog.core import diagnostics
from fapilog.core.logger import AsyncLoggerFacade


@pytest.mark.asyncio
async def test_enqueue_drops_when_queue_full():
    """Direct try_enqueue drops when queue is full."""

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

    # Fill queue to capacity
    assert logger._queue.try_enqueue({"id": 1})

    # Direct try_enqueue should fail when full
    result = logger._try_enqueue_with_metrics({"id": 2})

    assert result is False
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
