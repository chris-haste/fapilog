from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog.core.logger import SyncLoggerFacade


class _SimpleEnricher:
    name = "x_enricher"

    async def start(self) -> None:  # pragma: no cover - optional
        return None

    async def stop(self) -> None:  # pragma: no cover - optional
        return None

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"x": 1}


class _ExplodingEnricher:
    name = "boom"

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")


class _SimpleRedactor:
    name = "mask_x"

    async def redact(self, event: dict[str, Any]) -> dict[str, Any]:
        # Remove x if present and add marker
        e = dict(event)
        e.pop("x", None)
        e["redacted"] = True
        return e


@pytest.mark.asyncio
async def test_enable_disable_enricher_affects_output() -> None:
    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()

    # Enable custom enricher
    logger.enable_enricher(_SimpleEnricher())
    logger.info("m1")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert any("x" in evt for evt in collected)

    # Disable the enricher and ensure future logs don't include it
    collected.clear()
    logger = SyncLoggerFacade(
        name="t2",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()
    logger.enable_enricher(_SimpleEnricher())
    logger.disable_enricher("x_enricher")
    logger.info("m2")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert all("x" not in evt for evt in collected)


@pytest.mark.asyncio
async def test_enricher_exception_isolated_and_sink_still_writes() -> None:
    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()
    logger.enable_enricher(_ExplodingEnricher())  # type: ignore[arg-type]
    logger.info("m")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert len(collected) == 1


@pytest.mark.asyncio
async def test_redactor_stage_applies_when_configured() -> None:
    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    # Inject a redactor directly for unit coverage of stage
    logger._redactors = [
        _SimpleRedactor()  # type: ignore[list-item, assignment]
    ]  # type: ignore[attr-defined]
    logger.start()
    # Include a field that redactor will remove
    logger.enable_enricher(_SimpleEnricher())
    logger.info("m")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert len(collected) == 1
    evt = collected[0]
    assert "x" not in evt and evt.get("redacted") is True


@pytest.mark.asyncio
async def test_serialize_in_flush_fast_path_calls_write_serialized() -> None:
    calls: dict[str, Any] = {"serialized": 0, "bytes": b""}

    class TestSink:
        async def write(self, entry: dict[str, Any]) -> None:  # pragma: no cover
            pass

        async def write_serialized(self, view) -> None:  # type: ignore[no-untyped-def]
            calls["serialized"] += 1
            calls["bytes"] = bytes(view.data)

    sink = TestSink()

    async def _sink_write(entry: dict[str, Any]) -> None:
        await sink.write(entry)

    async def _sink_write_serialized(view) -> None:  # type: ignore[no-untyped-def]
        await sink.write_serialized(view)

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=_sink_write,
        sink_write_serialized=_sink_write_serialized,
        enrichers=[],
        metrics=None,
        serialize_in_flush=True,
    )
    logger.start()
    logger.info("m", i=1)
    await asyncio.sleep(0.1)
    await logger.stop_and_drain()

    assert calls["serialized"] >= 1


@pytest.mark.asyncio
async def test_start_is_idempotent_thread_mode() -> None:
    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.1,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()
    # Calling start twice should not raise or spawn another thread
    logger.start()
    res = await logger.stop_and_drain()
    assert isinstance(res.submitted, int)


@pytest.mark.asyncio
async def test_cross_thread_backpressure_behavior() -> None:
    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=1,
        batch_max_size=1024,
        batch_timeout_seconds=0.5,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    # Bind logger to current event loop
    logger.start()

    # Overrun queue from a different thread to exercise cross-thread path
    async def submit_from_thread() -> None:
        loop = asyncio.get_running_loop()

        def _send_many() -> None:
            for _ in range(200):
                logger.info("x")

        await loop.run_in_executor(None, _send_many)

    await submit_from_thread()

    res = await logger.stop_and_drain()
    assert res.submitted == 200
    assert res.dropped >= 1
    # Invariant: submitted equals processed + dropped
    assert res.submitted == (res.processed + res.dropped)
