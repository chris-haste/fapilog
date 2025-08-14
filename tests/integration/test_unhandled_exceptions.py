from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.errors import capture_unhandled_exceptions


@pytest.mark.asyncio
async def test_unhandled_async_exception_is_captured() -> None:
    captured: list[dict[str, Any]] = []
    logger = get_logger(name="unhandled-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]

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
