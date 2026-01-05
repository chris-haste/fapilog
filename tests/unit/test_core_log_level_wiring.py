from __future__ import annotations

import pytest

from fapilog import Settings, _build_pipeline
from fapilog.core.worker import LoggerWorker, strict_envelope_mode_enabled
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.filters import BaseFilter


class CaptureFilter(BaseFilter):
    name = "capture"

    def __init__(self) -> None:
        self.seen = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def filter(self, event: dict) -> dict | None:
        self.seen.append(event)
        return event


@pytest.mark.asyncio
async def test_core_log_level_auto_injects_level_filter() -> None:
    settings = Settings(core={"log_level": "INFO", "enable_metrics": True})
    sinks, enrichers, redactors, processors, filters, metrics = _build_pipeline(
        settings
    )
    names = [getattr(f, "name", "") for f in filters]
    assert "level" in names


@pytest.mark.asyncio
async def test_level_filter_drops_debug_before_enrichers(monkeypatch) -> None:
    metrics = MetricsCollector(enabled=True)
    captured = []

    class DummySink:
        async def write(self, entry: dict) -> None:
            captured.append(entry)

    settings = Settings(core={"log_level": "INFO", "enable_metrics": True})
    sinks, enrichers, redactors, processors, filters, metrics = _build_pipeline(
        settings
    )

    worker = LoggerWorker(
        queue=None,  # type: ignore[arg-type]
        batch_max_size=1,
        batch_timeout_seconds=0.01,
        sink_write=DummySink().write,
        sink_write_serialized=None,
        filters_getter=lambda: filters,
        enrichers_getter=lambda: enrichers,
        redactors_getter=lambda: redactors,
        processors_getter=lambda: processors,
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
        counters={"processed": 0, "dropped": 0},
    )

    debug_evt = {
        "level": "DEBUG",
        "message": "drop me",
        "context": {},
        "diagnostics": {},
    }
    info_evt = {"level": "INFO", "message": "keep me", "context": {}, "diagnostics": {}}
    await worker.flush_batch([debug_evt, info_evt])

    snap = await metrics.snapshot()
    assert snap.events_filtered == 1
    assert len(captured) == 1
    assert captured[0]["message"] == "keep me"
