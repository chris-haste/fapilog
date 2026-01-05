from __future__ import annotations

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.events import LogEvent
from fapilog.core.worker import LoggerWorker, strict_envelope_mode_enabled
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.filters import BaseFilter, filter_in_order


class DropAllFilter(BaseFilter):
    name = "drop_all"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def filter(self, event: dict) -> dict | None:  # noqa: D401
        return None


class AppendFieldFilter(BaseFilter):
    name = "append_field"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def filter(self, event: dict) -> dict | None:  # noqa: D401
        new = dict(event)
        new["filtered"] = True
        return new


class ErrorFilter(BaseFilter):
    name = "error"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def filter(self, event: dict) -> dict | None:  # noqa: D401
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_filter_in_order_drops_and_short_circuits() -> None:
    metrics = MetricsCollector(enabled=True)
    event = {"level": "INFO"}
    result = await filter_in_order(
        event,
        [AppendFieldFilter(), DropAllFilter(), AppendFieldFilter()],
        metrics=metrics,
    )
    assert result is None
    snap = await metrics.snapshot()
    assert snap.events_filtered == 1


@pytest.mark.asyncio
async def test_filter_in_order_contains_errors_and_continues(monkeypatch) -> None:
    warned: list[dict] = []

    def fake_warn(_c, _m, **attrs):
        warned.append(attrs)

    monkeypatch.setattr("fapilog.plugins.filters.diagnostics.warn", fake_warn)

    event = {"level": "INFO"}
    out = await filter_in_order(
        event,
        [ErrorFilter(), AppendFieldFilter()],
        metrics=None,
    )
    assert out is not None and out.get("filtered") is True
    assert warned and warned[-1]["filter"] == "error"


@pytest.mark.asyncio
async def test_worker_applies_filters_before_enrichers(monkeypatch) -> None:
    queue: NonBlockingRingQueue[dict[str, object]] = NonBlockingRingQueue(capacity=2)
    counters = {"processed": 0, "dropped": 0}
    metrics = MetricsCollector(enabled=True)
    events: list[dict] = []

    async def sink_write(entry: dict[str, object]) -> None:
        events.append(entry)

    # Ensure enrichers not called if filter drops
    class EnricherCalled(Exception):
        pass

    async def enricher(event: dict) -> dict:
        raise EnricherCalled

    worker = LoggerWorker(
        queue=queue,
        batch_max_size=2,
        batch_timeout_seconds=0.01,
        sink_write=sink_write,
        sink_write_serialized=None,
        filters_getter=lambda: [DropAllFilter()],
        enrichers_getter=lambda: [enricher],  # type: ignore[list-item]
        redactors_getter=lambda: [],
        processors_getter=lambda: [],
        metrics=metrics,
        serialize_in_flush=False,
        strict_envelope_mode_provider=strict_envelope_mode_enabled,
        stop_flag=lambda: False,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_filter_diagnostics=True,
        emit_enricher_diagnostics=True,
        emit_redactor_diagnostics=True,
        emit_processor_diagnostics=True,
        counters=counters,
    )

    evt = LogEvent(level="DEBUG", message="msg").to_mapping()
    await worker.flush_batch([evt])

    assert events == []  # dropped
    snap = await metrics.snapshot()
    assert snap.events_filtered == 1
