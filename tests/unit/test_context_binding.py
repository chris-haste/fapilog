import asyncio
from typing import Any, List

import pytest

from fapilog import get_logger, runtime_async


@pytest.mark.asyncio
async def test_bind_and_precedence_and_unbind_and_clear() -> None:
    captured: List[dict[str, Any]] = []
    logger = get_logger(name="bind-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    # Swap sink to capture outputs
    logger._sink_write = capture  # type: ignore[attr-defined]

    # Bind some context - request_id and user_id are context fields (v1.1)
    logger.bind(request_id="abc", user_id="u1")
    logger.info("started")

    # Per-call kwargs override bound
    logger.info("override", user_id="u2")

    # Unbind a key
    logger.unbind("user_id")
    logger.info("anon")

    # Clear all
    logger.clear_context()
    logger.info("done")

    await asyncio.sleep(0)
    await logger.stop_and_drain()

    assert len(captured) >= 4
    # v1.1 schema: request_id and user_id are in context, not data
    ctx0 = captured[-4]["context"]
    assert ctx0["request_id"] == "abc" and ctx0["user_id"] == "u1"
    ctx1 = captured[-3]["context"]
    assert ctx1["user_id"] == "u2"  # per-call override wins
    ctx2 = captured[-2]["context"]
    assert "user_id" not in ctx2 and ctx2.get("request_id") == "abc"
    ctx3 = captured[-1]["context"]
    # cleared context still has correlation_id but no request_id/user_id
    assert "request_id" not in ctx3 and "user_id" not in ctx3


@pytest.mark.asyncio
async def test_unbind_returns_logger_sync_facade() -> None:
    logger = get_logger(name="unbind-return-sync")
    try:
        bound = logger.bind(request_id="123")
        assert bound is logger
        unbound = bound.unbind("request_id")
        assert unbound is logger
        assert hasattr(unbound, "info")
    finally:
        await logger.stop_and_drain()


@pytest.mark.asyncio
async def test_unbind_returns_logger_async_facade() -> None:
    async with runtime_async() as logger:
        bound = logger.bind(request_id="abc")
        assert bound is logger
        unbound = bound.unbind("request_id")
        assert unbound is logger
        assert hasattr(unbound, "info")


@pytest.mark.asyncio
async def test_isolation_across_tasks() -> None:
    captured: List[dict[str, Any]] = []
    logger = get_logger(name="iso-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]

    async def task_a() -> None:
        logger.bind(req="A")
        logger.info("a1")
        await asyncio.sleep(0)
        logger.info("a2")

    async def task_b() -> None:
        logger.bind(req="B")
        logger.info("b1")
        await asyncio.sleep(0)
        logger.info("b2")

    await asyncio.gather(task_a(), task_b())
    await logger.stop_and_drain()

    # Verify no cross-contamination
    # v1.1 schema: custom fields like "req" go to data, not metadata
    req_values = [
        e["data"].get("req")
        for e in captured
        if e.get("message") in {"a1", "a2", "b1", "b2"}
    ]
    assert "A" in req_values and "B" in req_values
    # Check that each message keeps its own bound value
    for e in captured:
        msg = e.get("message")
        if msg in ("a1", "a2"):
            assert e["data"].get("req") == "A"
        if msg in ("b1", "b2"):
            assert e["data"].get("req") == "B"
