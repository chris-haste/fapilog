from __future__ import annotations

import pytest

from fapilog.core.logger import SyncLoggerFacade


@pytest.mark.asyncio
async def test_logger_self_test_success() -> None:
    async def _sink_write(entry: dict) -> None:  # type: ignore[no-redef]
        # accept dict and do nothing
        return None

    logger = SyncLoggerFacade(
        name="selftest",
        queue_capacity=8,
        batch_max_size=4,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=True,
        sink_write=_sink_write,
    )
    res = await logger.self_test()
    assert res.get("ok") is True
    assert res.get("sink") == "default"
