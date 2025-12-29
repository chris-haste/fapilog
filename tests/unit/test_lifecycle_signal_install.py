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


@pytest.mark.asyncio
async def test_install_signal_handlers_no_event_loop() -> None:
    """Test install_signal_handlers when no event loop exists."""
    from unittest.mock import patch

    logger = get_logger(name="sig-test-no-loop")

    # Mock get_event_loop to raise RuntimeError (simulating no event loop)
    with patch("fapilog.core.lifecycle.asyncio.get_event_loop") as mock_get_loop:
        mock_get_loop.side_effect = RuntimeError("No event loop")
        # Should not raise
        install_signal_handlers(logger)
        await logger.stop_and_drain()
