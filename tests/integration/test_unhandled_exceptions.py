from __future__ import annotations

import asyncio
from typing import Any

import pytest

import fapilog.core.errors as _errors_mod
from fapilog.core.errors import capture_unhandled_exceptions
from fapilog.core.logger import SyncLoggerFacade

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_unhandled_flag() -> None:
    """Reset the module-level guard so the hook installs fresh each test."""
    _errors_mod._unhandled_installed = False


@pytest.mark.asyncio
async def test_unhandled_async_exception_is_captured() -> None:
    captured: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger = SyncLoggerFacade(
        name="unhandled-test",
        queue_capacity=100,
        batch_max_size=10,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=5,
        drop_on_full=True,
        sink_write=capture,
        enrichers=[],
        metrics=None,
    )
    logger.start()

    # Install hooks
    capture_unhandled_exceptions(logger)

    async def boom() -> None:
        raise RuntimeError("boom")

    # Schedule a task that will raise without being awaited
    asyncio.create_task(boom())
    await asyncio.sleep(0.05)
    await logger.stop_and_drain()

    assert any(
        e.get("message") in {"unhandled_task_exception", "unhandled_exception"}
        for e in captured
    )
