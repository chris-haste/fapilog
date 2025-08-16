from __future__ import annotations

import pytest

from fapilog import get_logger
from fapilog.core.settings import Settings


@pytest.mark.asyncio
async def test_get_logger_injects_redactors_and_unhandled_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = Settings()
    s.core.enable_redactors = True
    s.core.redactors_order = ["field-mask", "regex-mask", "url-credentials"]
    s.core.capture_unhandled_enabled = True

    logger = get_logger(name="init-test", settings=s)
    # Verify redactors injected
    assert getattr(logger, "_redactors", None)
    # Exercise unhandled handler indirectly by raising and catching
    # (hook exists)
    try:
        raise RuntimeError("dummy")
    except RuntimeError:
        logger.exception("caught")
    await logger.stop_and_drain()
