from __future__ import annotations

import pytest

from fapilog.core.settings import Settings


def test_env_mapping_for_logging_sampling_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE", "0.42")
    s = Settings()
    assert abs(s.observability.logging.sampling_rate - 0.42) < 1e-9


def test_env_mapping_for_error_dedupe_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS", "1.5")
    s = Settings()
    assert abs(s.core.error_dedupe_window_seconds - 1.5) < 1e-9
