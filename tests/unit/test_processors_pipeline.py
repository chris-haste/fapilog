from __future__ import annotations

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.events import LogEvent
from fapilog.core.worker import LoggerWorker, strict_envelope_mode_enabled
from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.processors import BaseProcessor


class _AppendProcessor(BaseProcessor):
    """Test processor that appends a marker for order assertions."""

    def __init__(self, marker: bytes) -> None:
        self.marker = marker
        self.name = f"append-{marker.decode()}"

    async def process(self, view: memoryview) -> memoryview:
        return memoryview(view.tobytes() + self.marker)


class _FailingProcessor(BaseProcessor):
    name = "failing"

    async def process(self, view: memoryview) -> memoryview:  # noqa: D401
        raise RuntimeError("boom")


class _PassthroughProcessor(BaseProcessor):
    name = "passthrough"

    async def process(self, view: memoryview) -> memoryview:  # noqa: D401
        return view


def _make_worker(
    *,
    sink_write_serialized,
    sink_write,
    processors_getter,
    metrics=None,
    emit_processor_diagnostics: bool = True,
):
    return LoggerWorker(
        queue=NonBlockingRingQueue(capacity=4),
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        sink_write=sink_write,
        sink_write_serialized=sink_write_serialized,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=metrics,
        serialize_in_flush=True,
        strict_envelope_mode_provider=strict_envelope_mode_enabled,
        stop_flag=lambda: False,
        drained_event=None,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=True,
        emit_redactor_diagnostics=True,
        counters={"processed": 0, "dropped": 0},
        processors_getter=processors_getter,
        emit_processor_diagnostics=emit_processor_diagnostics,
    )


def _log_batch() -> list[dict]:
    return [LogEvent(level="INFO", message="hello").to_mapping()]


@pytest.mark.asyncio
async def test_worker_applies_processors_in_order() -> None:
    serialized: list[bytes] = []

    async def sink_write_serialized(view):
        serialized.append(bytes(view))

    fallback: list[dict] = []

    async def sink_write(entry):
        fallback.append(entry)

    worker = _make_worker(
        sink_write_serialized=sink_write_serialized,
        sink_write=sink_write,
        processors_getter=lambda: [
            _AppendProcessor(b"1"),
            _AppendProcessor(b"2"),
        ],
    )

    batch = _log_batch()
    await worker.flush_batch(batch)

    assert fallback == []  # fast-path used
    assert serialized  # sink_write_serialized was called
    # Order preserved: markers appended sequentially
    assert serialized[0].endswith(b"12")


@pytest.mark.asyncio
async def test_worker_contains_processor_errors_and_records_metrics(
    monkeypatch,
) -> None:
    serialized: list[bytes] = []
    diagnostics: list[dict] = []

    async def sink_write_serialized(view):
        serialized.append(bytes(view))

    async def sink_write(entry):
        serialized.append(str(entry).encode())

    metrics = MetricsCollector(enabled=True)

    def fake_warn(_category, _message, **attrs):
        diagnostics.append(attrs)

    monkeypatch.setattr("fapilog.core.worker.warn", fake_warn)

    worker = _make_worker(
        sink_write_serialized=sink_write_serialized,
        sink_write=sink_write,
        processors_getter=lambda: [
            _FailingProcessor(),
            _AppendProcessor(b"x"),
        ],
        metrics=metrics,
    )

    batch = _log_batch()
    await worker.flush_batch(batch)

    # Error should not block subsequent processors or sinks
    assert serialized
    assert serialized[0].endswith(b"x")
    # Diagnostics emitted for failing processor
    assert diagnostics
    assert diagnostics[-1].get("processor") == "failing"
    # Metrics recorded plugin error
    snap = await metrics.snapshot()
    assert snap.plugin_errors == 1


@pytest.mark.asyncio
async def test_worker_preserves_original_view_on_failure(monkeypatch) -> None:
    serialized: list[bytes] = []

    async def sink_write_serialized(view):
        serialized.append(bytes(view))

    async def sink_write(entry):
        serialized.append(str(entry).encode())

    # Capture the bytes produced before processor mutation
    original_bytes: list[bytes] = []

    class CaptureProcessor(BaseProcessor):
        name = "capture"

        async def process(self, view: memoryview) -> memoryview:
            original_bytes.append(view.tobytes())
            raise RuntimeError("stop here")

    worker = _make_worker(
        sink_write_serialized=sink_write_serialized,
        sink_write=sink_write,
        processors_getter=lambda: [CaptureProcessor()],
        emit_processor_diagnostics=False,
    )

    batch = _log_batch()
    await worker.flush_batch(batch)

    assert serialized  # fallback to original view written
    assert original_bytes
    assert serialized[0] == original_bytes[0]
