import asyncio
from typing import Any, List

import pytest

from fapilog import get_logger


@pytest.mark.asyncio
async def test_bind_and_precedence_and_unbind_and_clear() -> None:
    captured: List[dict[str, Any]] = []
    logger = get_logger(name="bind-test")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    # Swap sink to capture outputs
    logger._sink_write = capture  # type: ignore[attr-defined]

    # Bind some context
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
    m0 = captured[-4]["metadata"]
    assert m0["request_id"] == "abc" and m0["user_id"] == "u1"
    m1 = captured[-3]["metadata"]
    assert m1["user_id"] == "u2"  # per-call override wins
    m2 = captured[-2]["metadata"]
    assert "user_id" not in m2 and m2.get("request_id") == "abc"
    m3 = captured[-1]["metadata"]
    # cleared context shouldn't include previous keys
    assert "request_id" not in m3 and "user_id" not in m3


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
    req_values = [
        e["metadata"].get("req")
        for e in captured
        if e.get("message") in {"a1", "a2", "b1", "b2"}
    ]
    assert "A" in req_values and "B" in req_values
    # Check that each message keeps its own bound value
    for e in captured:
        msg = e.get("message")
        if msg in ("a1", "a2"):
            assert e["metadata"].get("req") == "A"
        if msg in ("b1", "b2"):
            assert e["metadata"].get("req") == "B"
