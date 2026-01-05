from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest

from fapilog.core.logger import SyncLoggerFacade


def _make_settings(rate: float, filters: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        observability=SimpleNamespace(
            logging=SimpleNamespace(sampling_rate=rate),
        ),
        core=SimpleNamespace(
            error_dedupe_window_seconds=0.0,
            filters=filters or [],
        ),
    )


def _make_logger(
    monkeypatch: pytest.MonkeyPatch,
    rate: float,
    *,
    random_value: float,
    filters: list[str] | None = None,
) -> SyncLoggerFacade:
    async def _sink_write(entry: dict) -> None:  # pragma: no cover - placeholder
        _ = entry

    settings = _make_settings(rate, filters=filters)
    monkeypatch.setattr("fapilog.core.logger.Settings", lambda: settings, raising=False)
    monkeypatch.setattr(
        "fapilog.core.settings.Settings", lambda: settings, raising=False
    )
    monkeypatch.setattr("random.random", lambda: random_value)

    logger = SyncLoggerFacade(
        name="legacy",
        queue_capacity=4,
        batch_max_size=1,
        batch_timeout_seconds=0.01,
        backpressure_wait_ms=1,
        drop_on_full=False,
        sink_write=_sink_write,
        sink_write_serialized=None,
        enrichers=[],
        processors=[],
        filters=[],
        metrics=None,
        exceptions_enabled=False,
        exceptions_max_frames=1,
        exceptions_max_stack_chars=10,
        serialize_in_flush=False,
        num_workers=1,
        level_gate=None,
    )
    monkeypatch.setattr(logger, "start", lambda: None)
    return logger


def test_legacy_sampling_emits_deprecation_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _make_logger(monkeypatch, rate=0.5, random_value=0.9)

    with pytest.warns(DeprecationWarning):
        logger._enqueue("INFO", "legacy")

    assert logger._submitted == 0


def test_filter_sampling_path_suppresses_deprecation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = _make_logger(
        monkeypatch,
        rate=0.5,
        random_value=0.0,
        filters=["sampling"],
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=DeprecationWarning)
        logger._enqueue("INFO", "use-filter")

    assert logger._submitted == 1
