from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fapilog import get_logger
from fapilog.core.diagnostics import set_writer_for_tests


@pytest.mark.asyncio
async def test_policy_warning_emitted_when_policy_present_but_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diags: list[dict[str, Any]] = []

    def _writer(payload: dict[str, Any]) -> None:
        diags.append(payload)

    set_writer_for_tests(_writer)

    # Simulate policy by enabling diagnostics and injecting a settings policy
    import fapilog.core.diagnostics as _diag_mod

    monkeypatch.setattr(_diag_mod, "_is_enabled", lambda: True)
    from fapilog.core.settings import Settings

    s = Settings()
    s.core.internal_logging_enabled = True
    s.core.sensitive_fields_policy = ["user.password"]
    logger = get_logger(name="policy-warning-test", settings=s)

    # Force an event through the pipeline
    logger.info("msg")
    await asyncio.sleep(0)
    await logger.stop_and_drain()

    # Ensure a redactor policy warning was emitted
    assert any(
        (d.get("component") == "redactor") and "policy" in d.get("message", "")
        for d in diags
    )
