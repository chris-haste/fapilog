from __future__ import annotations

import pytest

from fapilog import get_logger
from fapilog.core.lifecycle import install_signal_handlers


@pytest.mark.asyncio
async def test_install_signal_handlers_noop() -> None:
    # Ensure it does not raise in normal test environment
    logger = get_logger(name="sig-test")
    install_signal_handlers(logger)
    # quick self-test path
    res = await logger.self_test()
    assert res["ok"] is True
    await logger.stop_and_drain()
