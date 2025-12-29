from typing import Any
from unittest.mock import MagicMock

import pytest

from fapilog import Settings, get_logger
from fapilog.plugins.enrichers import BaseEnricher
from fapilog.plugins.integrity import (
    IntegrityPluginLoadError,
    load_integrity_plugin,
)


class _DummyEnricher(BaseEnricher):
    name = "dummy-integrity"

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        event["integrity"] = True
        return event


class _DummyPlugin:
    def __init__(self, calls: list[tuple[str, Any]]) -> None:
        self._calls = calls

    def get_enricher(self, config: dict[str, Any] | None = None) -> BaseEnricher:
        self._calls.append(("enricher", config))
        return _DummyEnricher()

    def wrap_sink(self, sink: Any, config: dict[str, Any] | None = None) -> Any:
        self._calls.append(("wrap", config))
        sink._wrapped_by_dummy = True
        return sink


@pytest.mark.asyncio
async def test_integrity_plugin_skipped_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def _fake_loader(_name: str) -> Any:  # pragma: no cover - should not run
        nonlocal called
        called = True
        return None

    async def _noop_write(self, _entry: dict) -> None:
        return None

    async def _noop_write_serialized(self, _view: Any) -> None:
        return None

    # Avoid background threads and I/O during test
    monkeypatch.setattr("fapilog.core.logger.SyncLoggerFacade.start", lambda self: None)
    monkeypatch.setattr(
        "fapilog.plugins.sinks.stdout_json.StdoutJsonSink.write", _noop_write
    )
    monkeypatch.setattr(
        "fapilog.plugins.sinks.stdout_json.StdoutJsonSink.write_serialized",
        _noop_write_serialized,
    )
    monkeypatch.setattr("fapilog.plugins.integrity.load_integrity_plugin", _fake_loader)

    logger = get_logger(settings=Settings())
    # Ensure pipeline still usable
    logger.info("hello")
    assert called is False


@pytest.mark.asyncio
async def test_integrity_plugin_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Any]] = []
    plugin = _DummyPlugin(calls)

    def _fake_loader(_name: str) -> Any:
        return plugin

    async def _noop_write(self, _entry: dict) -> None:
        return None

    async def _noop_write_serialized(self, _view: Any) -> None:
        return None

    # Avoid background threads and I/O during test
    monkeypatch.setattr("fapilog.core.logger.SyncLoggerFacade.start", lambda self: None)
    monkeypatch.setattr(
        "fapilog.plugins.sinks.stdout_json.StdoutJsonSink.write", _noop_write
    )
    monkeypatch.setattr(
        "fapilog.plugins.sinks.stdout_json.StdoutJsonSink.write_serialized",
        _noop_write_serialized,
    )
    monkeypatch.setattr("fapilog.plugins.integrity.load_integrity_plugin", _fake_loader)

    cfg = Settings(
        core={
            "integrity_plugin": "dummy",
            "integrity_config": {"k": "v"},
        }
    )
    logger = get_logger(settings=cfg)

    # Plugin wrap/enricher hooks should have been invoked
    assert ("wrap", {"k": "v"}) in calls
    assert ("enricher", {"k": "v"}) in calls
    assert any(isinstance(e, _DummyEnricher) for e in logger._enrichers)


def test_load_integrity_plugin_success_with_select(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test loading plugin using the select() method (Python 3.10+)."""
    mock_plugin = _DummyPlugin([])
    mock_ep = MagicMock()
    mock_ep.name = "test-plugin"
    mock_ep.load.return_value = mock_plugin

    mock_eps = MagicMock()
    mock_eps.select.return_value = [mock_ep]
    monkeypatch.setattr(
        "fapilog.plugins.integrity.importlib.metadata.entry_points", lambda: mock_eps
    )

    result = load_integrity_plugin("test-plugin")
    assert result is mock_plugin
    mock_ep.load.assert_called_once()


def test_load_integrity_plugin_success_with_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test loading plugin using the get() method (Python 3.8 compat)."""
    mock_plugin = _DummyPlugin([])
    mock_ep = MagicMock()
    mock_ep.name = "test-plugin"
    mock_ep.load.return_value = mock_plugin

    # Create a mock that doesn't have 'select' attribute to simulate old API
    class OldEntryPoints:
        def get(self, group: str, default: list[Any] | None = None) -> list[Any]:
            if group == "fapilog.integrity":
                return [mock_ep]
            return default or []

    mock_eps = OldEntryPoints()
    monkeypatch.setattr(
        "fapilog.plugins.integrity.importlib.metadata.entry_points", lambda: mock_eps
    )

    result = load_integrity_plugin("test-plugin")
    assert result is mock_plugin
    mock_ep.load.assert_called_once()


def test_load_integrity_plugin_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error when plugin is not found."""
    mock_eps = MagicMock()
    mock_eps.select.return_value = []
    monkeypatch.setattr(
        "fapilog.plugins.integrity.importlib.metadata.entry_points", lambda: mock_eps
    )

    with pytest.raises(
        IntegrityPluginLoadError, match="Integrity plugin 'missing' not found"
    ):
        load_integrity_plugin("missing")


def test_load_integrity_plugin_enumeration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test error during entry point enumeration."""
    mock_eps = MagicMock()
    mock_eps.select.side_effect = ValueError("Enumeration failed")
    monkeypatch.setattr(
        "fapilog.plugins.integrity.importlib.metadata.entry_points", lambda: mock_eps
    )

    with pytest.raises(
        IntegrityPluginLoadError, match="Failed to enumerate integrity plugins"
    ):
        load_integrity_plugin("test-plugin")


def test_load_integrity_plugin_load_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test error during plugin loading."""
    mock_ep = MagicMock()
    mock_ep.name = "test-plugin"
    mock_ep.load.side_effect = ImportError("Cannot import plugin")

    mock_eps = MagicMock()
    mock_eps.select.return_value = [mock_ep]
    monkeypatch.setattr(
        "fapilog.plugins.integrity.importlib.metadata.entry_points", lambda: mock_eps
    )

    with pytest.raises(
        IntegrityPluginLoadError, match="Failed to load integrity plugin 'test-plugin'"
    ):
        load_integrity_plugin("test-plugin")
