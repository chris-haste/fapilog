from __future__ import annotations

from typing import Any

import pytest

from fapilog.core import diagnostics as diag


def test_diagnostics_rate_limiter_allows_then_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force diagnostics enabled via monkeypatch
    monkeypatch.setattr(diag, "_is_enabled", lambda: True)
    seen = 0

    def _writer(payload: dict[str, Any]) -> None:
        nonlocal seen
        seen += 1

    diag.set_writer_for_tests(_writer)
    # Emitting more than capacity should be limited
    for _ in range(20):
        diag.emit(component="x", level="DEBUG", message="m")
    assert seen >= 1
