from __future__ import annotations

import sys
from typing import Any

import pytest

from fapilog.core.errors import serialize_exception
from fapilog.core.logger import SyncLoggerFacade


def test_serialize_exception_bounds() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        info = sys.exc_info()
    data = serialize_exception(info, max_frames=2, max_stack_chars=200)
    assert data.get("error.type") == "ValueError"
    assert "error.stack" in data
    assert len(data["error.stack"]) <= 200
    frames = data.get("error.frames", [])
    assert isinstance(frames, list)
    assert len(frames) <= 2


def _make_logger(name: str, sink: Any) -> SyncLoggerFacade:
    """Create a SyncLoggerFacade with exceptions enabled and a capture sink."""
    logger = SyncLoggerFacade(
        name=name,
        queue_capacity=16,
        batch_max_size=8,
        batch_timeout_seconds=0.05,
        backpressure_wait_ms=10,
        drop_on_full=True,
        sink_write=sink,
        exceptions_enabled=True,
    )
    logger.start()
    return logger


@pytest.mark.asyncio
async def test_log_exception_and_exc_info_true() -> None:
    captured: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger = _make_logger("exc-test", capture)

    try:
        raise ZeroDivisionError("x")
    except ZeroDivisionError:
        logger.exception("fail", op="zdx")
    await logger.stop_and_drain()
    assert captured
    # v1.1 schema: exception data in diagnostics.exception
    exc_data = captured[-1].get("diagnostics", {}).get("exception", {})
    assert exc_data.get("error.type") == "ZeroDivisionError"
    assert "error.stack" in exc_data


@pytest.mark.asyncio
async def test_exc_and_exc_info_precedence() -> None:
    captured: list[dict[str, Any]] = []

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger = _make_logger("prec-test", capture)

    try:
        raise RuntimeError("primary")
    except RuntimeError as e1:
        try:
            raise ValueError("secondary")
        except ValueError:
            info = sys.exc_info()
        # exc takes precedence over exc_info when both provided
        logger.error("msg", exc=e1, exc_info=info)
    await logger.stop_and_drain()

    # v1.1 schema: exception data in diagnostics.exception
    exc_data = captured[-1].get("diagnostics", {}).get("exception", {})
    assert exc_data.get("error.type") == "RuntimeError"
