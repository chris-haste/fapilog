from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.stdlib_bridge import StdlibBridgeHandler, enable_stdlib_bridge


@pytest.mark.asyncio
async def test_forward_basic_and_extras() -> None:
    captured: list[dict[str, Any]] = []
    logger = get_logger(name="bridge-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]

    enable_stdlib_bridge(
        logger,
        level=logging.INFO,
        remove_existing_handlers=True,
    )
    std = logging.getLogger("thirdparty.module")
    std.info("hello %s", "world", extra={"user_id": "u1", "k": 2})

    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert captured
    ev = captured[-1]
    assert ev["message"].startswith("hello world")
    meta = ev["metadata"]
    assert meta.get("user_id") == "u1" and meta.get("k") == 2
    assert meta.get("stdlib_logger") == "thirdparty.module"


@pytest.mark.asyncio
async def test_forward_exception() -> None:
    captured: list[dict[str, Any]] = []
    logger = get_logger(name="bridge-exc-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]
    enable_stdlib_bridge(
        logger,
        level=logging.DEBUG,
        remove_existing_handlers=True,
    )
    std = logging.getLogger("thirdparty.exc")

    try:
        raise RuntimeError("boom")
    except RuntimeError:
        std.exception("failed")

    await asyncio.sleep(0)
    await logger.stop_and_drain()
    ev = captured[-1]
    assert ev["metadata"].get("error.type") == "RuntimeError"


@pytest.mark.asyncio
async def test_loop_prevention() -> None:
    captured: list[dict[str, Any]] = []
    logger = get_logger(name="bridge-loop-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]
    enable_stdlib_bridge(
        logger,
        level=logging.INFO,
        remove_existing_handlers=True,
    )
    std = logging.getLogger("fapilog.core")
    std.info("should-not-forward")
    await asyncio.sleep(0)
    await logger.stop_and_drain()
    assert not any(e.get("message") == "should-not-forward" for e in captured)


def test_custom_targets_and_warning_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}
    target = logging.getLogger("custom-target")
    target.handlers = [logging.NullHandler()]

    def _capture(flag: bool) -> None:
        calls["capture_warnings_flag"] = flag

    monkeypatch.setattr(logging, "captureWarnings", _capture)

    logger = get_logger(name="bridge-custom-target")
    enable_stdlib_bridge(
        logger,
        level=logging.WARNING,
        remove_existing_handlers=True,
        capture_warnings=True,
        target_loggers=[target],
    )

    assert calls.get("capture_warnings_flag") is True
    assert any(isinstance(h, StdlibBridgeHandler) for h in target.handlers)

    asyncio.run(logger.stop_and_drain())
