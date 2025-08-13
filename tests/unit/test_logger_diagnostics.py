from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.diagnostics import set_writer_for_tests
from fapilog.core.settings import Settings


@pytest.mark.asyncio
async def test_flush_error_emits_diagnostics_and_drops_batch(monkeypatch: Any) -> None:
    # Enable internal diagnostics via env so Settings picks it up
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")

    # Build settings with small batch to force immediate flush
    s = Settings()
    s.core.batch_max_size = 2
    s.core.batch_timeout_seconds = 0.1

    logger = get_logger(name="diag", settings=s)

    # Capture diagnostics
    captured: list[dict[str, Any]] = []

    def capture_writer(payload: dict[str, Any]) -> None:
        captured.append(payload)

    set_writer_for_tests(capture_writer)

    # Sink that always raises to trigger error path in _flush_batch
    async def failing_sink(entry: dict[str, Any]) -> None:  # noqa: ARG001
        raise RuntimeError("sink failure")

    # Replace sink_write on the logger (test-only)
    logger._sink_write = failing_sink  # type: ignore[attr-defined]

    # Submit two events to form a batch and trigger flush
    logger.info("a")
    logger.info("b")

    # Allow the worker to attempt flush
    await asyncio.sleep(0.2)
    res = await logger.stop_and_drain()

    assert res.submitted == 2
    assert res.processed == 0
    assert res.dropped == 2

    # Verify at least one diagnostic was emitted for sink flush error
    assert any(
        p.get("component") == "sink" and p.get("level") in {"WARN", "WARNING"}
        for p in captured
    )
