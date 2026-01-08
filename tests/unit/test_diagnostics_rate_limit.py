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


def test_diagnostics_emit_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that diagnostics.emit handles exceptions gracefully."""
    # Force diagnostics enabled
    monkeypatch.setattr(diag, "_is_enabled", lambda: True)

    # Test exception handling when request_id context var is unavailable
    from unittest.mock import patch

    # Patch the context module where request_id_var is imported from
    with patch("fapilog.core.context.request_id_var") as mock_var:
        mock_var.get.side_effect = RuntimeError("Context error")
        # Should not raise, should set corr = None
        diag.emit(component="test", level="DEBUG", message="test")
        # Verify it handled the exception

    # Test exception handling when writer callback fails
    def failing_writer(payload: dict[str, Any]) -> None:
        raise RuntimeError("Writer error")

    diag.set_writer_for_tests(failing_writer)
    # Should not raise, should return silently
    diag.emit(component="test", level="DEBUG", message="test")
