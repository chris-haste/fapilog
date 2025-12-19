# tests/unit/test_core_logger_cov_additions.py
from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from fapilog.core.logger import AsyncLoggerFacade, SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector


def _collect(collected: list[dict[str, Any]], e: dict[str, Any]) -> None:
    collected.append(dict(e))


def test_metrics_submission_outside_loop_thread_mode() -> None:
    metrics = MetricsCollector(enabled=True)
    out: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="out",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=lambda e: _collect(out, e),
        metrics=metrics,
    )
    logger.start()
    logger.info("outside-loop")
    res = asyncio.run(logger.stop_and_drain())
    assert res.submitted >= 1
    assert any(evt.get("message") == "outside-loop" for evt in out)


@pytest.mark.asyncio
async def test_context_binding_precedence_and_unbind_clear() -> None:
    out: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="ctx",
        queue_capacity=8,
        batch_max_size=1,  # Force immediate flush
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=lambda e: _collect(out, e),
    )
    logger.start()
    logger.bind(user="A", trace="t1")
    logger.info("m1", user="B")  # per-call overrides bound
    await asyncio.sleep(0.01)  # Let first message flush
    logger.unbind("trace")
    logger.info("m2")
    await asyncio.sleep(0.01)  # Let second message flush
    logger.clear_context()
    logger.info("m3", user="C")
    await asyncio.sleep(0.01)  # Let third message flush

    await logger.stop_and_drain()

    assert len(out) >= 3, f"Expected at least 3 messages, got {len(out)}"
    m1, m2, m3 = out[0], out[1], out[2]
    assert m1["metadata"].get("user") == "B"
    assert "trace" not in m2["metadata"]
    assert m3["metadata"].get("user") == "C"


@pytest.mark.asyncio
async def test_exception_serialization_with_exc_and_tuple() -> None:
    cap: list[dict[str, Any]] = []

    async def sink(e: dict[str, Any]) -> None:
        cap.append(e)

    logger = SyncLoggerFacade(
        name="exc",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=sink,
        exceptions_enabled=True,
        exceptions_max_frames=5,
        exceptions_max_stack_chars=2000,
    )
    logger.start()

    try:
        raise KeyError("boom")
    except KeyError as err:
        logger.error("with-exc", exc=err)

    try:
        _ = 1 / 0
    except ZeroDivisionError:
        info = sys.exc_info()
        logger.error("with-tuple", exc_info=info)

    await asyncio.sleep(0)
    await logger.stop_and_drain()
    metas = [e.get("metadata", {}) for e in cap]
    assert any("error.stack" in m or "error.frames" in m for m in metas)


@pytest.mark.asyncio
async def test_flush_batch_sink_error_counts_drop_and_metrics() -> None:
    calls = {"writes": 0}

    async def bad_sink(_e: dict[str, Any]) -> None:
        calls["writes"] += 1
        raise RuntimeError("sink-fail")

    metrics = MetricsCollector(enabled=True)
    logger = SyncLoggerFacade(
        name="fail",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=bad_sink,
        metrics=metrics,
    )
    logger.start()
    for i in range(5):
        logger.info("x", i=i)
    await asyncio.sleep(0.05)
    res = await logger.stop_and_drain()
    assert res.submitted == 5
    assert res.dropped >= 1


@pytest.mark.asyncio
async def test_enricher_without_name_attribute() -> None:
    """Test enable_enricher with object lacking name attribute (no-op path)."""
    cap: list[dict[str, Any]] = []

    class NamelessEnricher:
        # No name attribute
        async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
            return {"enriched": True}

    logger = SyncLoggerFacade(
        name="nameless",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=lambda e: cap.append(e),
    )
    logger.start()

    # This should be a no-op since enricher has no name
    logger.enable_enricher(NamelessEnricher())  # type: ignore[arg-type]
    logger.info("test")
    await asyncio.sleep(0.01)
    res = await logger.stop_and_drain()
    assert res.submitted >= 1
    # Enricher should not have been added since it has no name
    assert len(logger._enrichers) == 0  # type: ignore[attr-defined]


# Async-specific backpressure and metrics paths


@pytest.mark.asyncio
async def test_async_backpressure_drop_warn_path() -> None:
    cap: list[dict[str, Any]] = []
    logger = AsyncLoggerFacade(
        name="a",
        queue_capacity=1,
        batch_max_size=1024,
        batch_timeout_seconds=0.2,
        backpressure_wait_ms=0,  # force immediate drop
        drop_on_full=True,
        sink_write=lambda e: cap.append(e),
    )
    logger.start()
    # Fill queue and force additional drops
    await logger.info("seed")  # fills the single slot
    # Submit many more that will drop immediately
    for _ in range(10):
        await logger.info("x")
    res = await logger.stop_and_drain()
    assert res.dropped >= 1


@pytest.mark.asyncio
async def test_disable_nonexistent_enricher() -> None:
    """Test disable_enricher with non-existent name (no-op path)."""
    cap: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="test_disable",
        queue_capacity=8,
        batch_max_size=1,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=lambda e: cap.append(e),
    )
    logger.start()

    # Try to disable non-existent enricher (should be no-op)
    logger.disable_enricher("nonexistent")
    logger.info("test")
    await asyncio.sleep(0.01)

    res = await logger.stop_and_drain()
    assert res.submitted >= 1
    assert len(logger._enrichers) == 0  # type: ignore[attr-defined]
