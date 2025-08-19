from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from fapilog.core import diagnostics as _diag_mod
from fapilog.core.diagnostics import set_writer_for_tests
from fapilog.core.logger import SyncLoggerFacade
from fapilog.metrics.metrics import MetricsCollector


@pytest.mark.asyncio
async def test_self_test_returns_ok() -> None:
    wrote: list[dict[str, Any]] = []

    async def sink(entry: dict[str, Any]) -> None:
        wrote.append(entry)

    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=sink,
    )
    res = await logger.self_test()
    assert res.get("ok") is True
    assert wrote and wrote[0]["message"] == "self_test"


@pytest.mark.asyncio
async def test_disable_enricher_removes_by_name() -> None:
    class _E:
        name = "abc"

        async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
            return {"abc": True}

    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()
    logger.enable_enricher(_E())  # type: ignore[arg-type]
    logger.disable_enricher("abc")
    logger.info("m")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert collected and all("abc" not in e for e in collected)


@pytest.mark.asyncio
async def test_error_dedupe_rollover_emits_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diag: list[dict[str, Any]] = []

    def _writer(payload: dict[str, Any]) -> None:
        diag.append(payload)

    set_writer_for_tests(_writer)
    monkeypatch.setattr(_diag_mod, "_is_enabled", lambda: True)

    outs: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=128,
        batch_max_size=64,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=lambda e: outs.append(e),
    )
    # Very short window
    monkeypatch.setenv("FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS", "0.1")
    # First error allowed
    logger.error("same")
    # Burst of duplicates suppressed
    for _ in range(50):
        logger.error("same")
    # Wait for window to roll
    time.sleep(0.12)
    # Trigger rollover summary emission
    logger.error("same")
    await logger.stop_and_drain()
    assert any(d.get("component") == "error-dedupe" for d in diag)


@pytest.mark.asyncio
async def test_sampling_applies_only_to_info_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Low sampling rate
    monkeypatch.setenv("FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE", "0.01")
    collected: list[dict[str, Any]] = []
    logger = SyncLoggerFacade(
        name="t",
        queue_capacity=4096,
        batch_max_size=1024,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=0,
        drop_on_full=True,
        sink_write=lambda e: collected.append(e),
    )
    logger.start()
    # WARNING should bypass sampling and always arrive
    logger.warning("w1")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert any(e.get("message") == "w1" for e in collected)


@pytest.mark.asyncio
async def test_exception_serialization_enabled() -> None:
    captured: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger = SyncLoggerFacade(
        name="exc",
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=capture,
        exceptions_enabled=True,
        exceptions_max_frames=5,
        exceptions_max_stack_chars=2000,
    )
    logger.start()
    try:
        raise ValueError("bad")
    except ValueError:
        logger.exception("oops")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert any("error.stack" in e.get("metadata", {}) for e in captured)


@pytest.mark.asyncio
async def test_metrics_submission_paths() -> None:
    metrics = MetricsCollector(enabled=True)
    captured: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger = SyncLoggerFacade(
        name="m",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=capture,
        metrics=metrics,
    )
    # Submit and drain within the running loop
    logger.info("m1")
    res = await logger.stop_and_drain()
    assert res.submitted >= 1
