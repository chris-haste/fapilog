from __future__ import annotations

from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.errors import request_id_var


@pytest.mark.asyncio
async def test_correlation_id_uses_context_request_id() -> None:
    captured: list[dict[str, Any]] = []
    logger = get_logger(name="corr")

    async def capture(entry: dict[str, Any]) -> None:
        captured.append(entry)

    logger._sink_write = capture  # type: ignore[attr-defined]

    token = request_id_var.set("REQ-123")
    try:
        logger.info("message")
        await logger.stop_and_drain()
    finally:
        request_id_var.reset(token)

    assert captured
    assert captured[0].get("correlation_id") == "REQ-123"
