from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.errors import serialize_exception
from fapilog.core.settings import Settings


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


@pytest.mark.asyncio
async def test_log_exception_and_exc_info_true() -> None:
    captured: list[dict[str, Any]] = []
    s = Settings()
    s.core.exceptions_enabled = True
    logger = get_logger(name="exc-test", settings=s)

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]

    try:
        raise ZeroDivisionError("x")
    except ZeroDivisionError:
        logger.exception("fail", op="zdx")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert captured
    meta = captured[-1]["metadata"]
    assert meta.get("error.type") == "ZeroDivisionError"
    assert "error.stack" in meta


@pytest.mark.asyncio
async def test_exc_and_exc_info_precedence() -> None:
    captured: list[dict[str, Any]] = []
    s = Settings()
    s.core.exceptions_enabled = True
    logger = get_logger(name="prec-test", settings=s)

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]

    try:
        raise RuntimeError("primary")
    except RuntimeError as e1:
        try:
            raise ValueError("secondary")
        except ValueError:
            info = sys.exc_info()
        # exc takes precedence over exc_info when both provided
        logger.error("msg", exc=e1, exc_info=info)
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    meta = captured[-1]["metadata"]
    assert meta.get("error.type") == "RuntimeError"
