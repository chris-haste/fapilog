from __future__ import annotations

import asyncio

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.worker import LoggerWorker, strict_envelope_mode_enabled


@pytest.mark.asyncio
async def test_worker_run_flushes_and_signals_drained() -> None:
    queue: NonBlockingRingQueue[dict[str, object]] = NonBlockingRingQueue(capacity=4)
    assert queue.try_enqueue({"id": 1})

    drained = asyncio.Event()
    counters = {"processed": 0, "dropped": 0}
    stop_flag = False
    sink_calls: list[dict[str, object]] = []

    async def sink_write(entry: dict[str, object]) -> None:
        sink_calls.append(entry)

    worker = LoggerWorker(
        queue=queue,
        batch_max_size=2,
        batch_timeout_seconds=0.01,
        sink_write=sink_write,
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=strict_envelope_mode_enabled,
        stop_flag=lambda: stop_flag,
        drained_event=drained,
        flush_event=None,
        flush_done_event=None,
        emit_enricher_diagnostics=True,
        emit_redactor_diagnostics=True,
        counters=counters,
    )

    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.01)
    stop_flag = True

    await asyncio.wait_for(task, timeout=1.0)

    assert drained.is_set()
    assert counters["processed"] == 1
    assert counters["dropped"] == 0
    assert sink_calls == [{"id": 1}]


@pytest.mark.asyncio
async def test_worker_flush_event_triggers_immediate_flush() -> None:
    queue: NonBlockingRingQueue[dict[str, object]] = NonBlockingRingQueue(capacity=4)
    assert queue.try_enqueue({"id": 99})

    flush_event = asyncio.Event()
    flush_done = asyncio.Event()
    drained = asyncio.Event()
    counters = {"processed": 0, "dropped": 0}
    stop_flag = False
    sink_calls: list[dict[str, object]] = []

    async def sink_write(entry: dict[str, object]) -> None:
        sink_calls.append(entry)

    worker = LoggerWorker(
        queue=queue,
        batch_max_size=1,
        batch_timeout_seconds=0.5,
        sink_write=sink_write,
        sink_write_serialized=None,
        enrichers_getter=lambda: [],
        redactors_getter=lambda: [],
        metrics=None,
        serialize_in_flush=False,
        strict_envelope_mode_provider=strict_envelope_mode_enabled,
        stop_flag=lambda: stop_flag,
        drained_event=drained,
        flush_event=flush_event,
        flush_done_event=flush_done,
        emit_enricher_diagnostics=True,
        emit_redactor_diagnostics=True,
        counters=counters,
    )

    task = asyncio.create_task(worker.run())

    flush_event.set()
    await asyncio.wait_for(flush_done.wait(), timeout=1.0)
    stop_flag = True

    await asyncio.wait_for(task, timeout=1.0)

    assert sink_calls == [{"id": 99}]
    assert counters["processed"] == 1
    assert drained.is_set()
