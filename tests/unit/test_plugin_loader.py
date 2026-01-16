from __future__ import annotations

import types
from typing import Any

import pytest

from fapilog.plugins import loader


class _DummyPlugin:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _fake_entry_point(name: str, target: Any) -> Any:
    ep = types.SimpleNamespace()
    ep.name = name
    ep.load = lambda: target
    return ep


def test_normalize_plugin_name() -> None:
    assert loader._normalize_plugin_name("Field-Mask") == "field_mask"
    assert loader._normalize_plugin_name("url_credentials") == "url_credentials"
    assert loader._normalize_plugin_name("URL-Credentials") == "url_credentials"


def test_register_and_load_builtin_with_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure clean registries for test isolation
    monkeypatch.setattr(loader, "BUILTIN_ENRICHERS", {}, raising=False)
    monkeypatch.setattr(
        loader,
        "BUILTIN_ALIASES",
        {"fapilog.enrichers": {"runtime-info": "runtime_info"}},
        raising=False,
    )

    class DummyEnricher(_DummyPlugin):
        pass

    loader.register_builtin("fapilog.enrichers", "runtime_info", DummyEnricher)

    # Canonical name
    inst = loader.load_plugin("fapilog.enrichers", "runtime_info", {"key": "value"})
    assert isinstance(inst, DummyEnricher)
    assert inst.kwargs == {"key": "value"}

    # Alias name resolves to canonical
    inst_alias = loader.load_plugin("fapilog.enrichers", "runtime-info")
    assert isinstance(inst_alias, DummyEnricher)


def test_load_plugin_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {}, raising=False)
    with pytest.raises(loader.PluginNotFoundError):
        loader.load_plugin("fapilog.sinks", "missing")


def test_error_message_shows_normalized_name_when_different(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: Error message includes both original and normalized names."""
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {}, raising=False)

    with pytest.raises(loader.PluginNotFoundError) as exc_info:
        loader.load_plugin("fapilog.sinks", "HTTP-Sink")

    error_msg = str(exc_info.value)
    assert "HTTP-Sink" in error_msg
    assert "http_sink" in error_msg
    assert "normalized" in error_msg.lower()


def test_error_message_lists_available_plugins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: Error message lists available plugins."""
    monkeypatch.setattr(
        loader, "BUILTIN_SINKS", {"console": _DummyPlugin, "file": _DummyPlugin}
    )
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {}, raising=False)

    with pytest.raises(loader.PluginNotFoundError) as exc_info:
        loader.load_plugin("fapilog.sinks", "missing")

    error_msg = str(exc_info.value)
    assert "console" in error_msg
    assert "file" in error_msg


def test_error_message_unchanged_when_name_already_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: Error message does not show normalized form when name is already canonical."""
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {}, raising=False)

    with pytest.raises(loader.PluginNotFoundError) as exc_info:
        loader.load_plugin("fapilog.sinks", "missing_plugin")

    error_msg = str(exc_info.value)
    assert "missing_plugin" in error_msg
    assert "normalized" not in error_msg.lower()


def test_register_builtin_warns_for_non_canonical_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: Warn when registering plugins with non-normalized names."""
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}}, raising=False)

    warnings_emitted: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        warnings_emitted.append({"component": component, "message": message, **fields})

    monkeypatch.setattr(loader.diagnostics, "warn", capture_warn)

    loader.register_builtin("fapilog.sinks", "HTTP-Sink", _DummyPlugin)

    assert len(warnings_emitted) == 1
    warning = warnings_emitted[0]
    assert warning["component"] == "plugins"
    assert "non-canonical" in warning["message"]
    assert warning["registered"] == "HTTP-Sink"
    assert warning["canonical"] == "http_sink"


def test_register_builtin_no_warning_for_canonical_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: No warning when registering plugins with normalized names."""
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}}, raising=False)

    warnings_emitted: list[dict[str, Any]] = []

    def capture_warn(component: str, message: str, **fields: Any) -> None:
        warnings_emitted.append({"component": component, "message": message, **fields})

    monkeypatch.setattr(loader.diagnostics, "warn", capture_warn)

    loader.register_builtin("fapilog.sinks", "http_sink", _DummyPlugin)

    # No warnings should be emitted for canonical names
    assert len(warnings_emitted) == 0


def test_register_builtin_continues_when_diagnostics_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registration succeeds even when diagnostics.warn raises."""
    registry: dict[str, type] = {}
    monkeypatch.setattr(loader, "BUILTIN_SINKS", registry, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}}, raising=False)

    def failing_warn(component: str, message: str, **fields: Any) -> None:
        raise RuntimeError("diagnostics failed")

    monkeypatch.setattr(loader.diagnostics, "warn", failing_warn)

    # Should not raise despite diagnostics failure
    loader.register_builtin("fapilog.sinks", "HTTP-Sink", _DummyPlugin)

    # Plugin should still be registered under canonical name
    assert "http_sink" in registry
    assert registry["http_sink"] is _DummyPlugin


def test_entry_point_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader, "BUILTIN_SINKS", {}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {}, raising=False)

    fake_ep = _fake_entry_point("sample", _DummyPlugin)

    class _FakeEntryPoints:
        def select(self, group: str):  # pragma: no cover - py>=3.10 path
            return [fake_ep] if group == "fapilog.sinks" else []

        def get(self, group: str, default: Any = None):  # pragma: no cover - py3.8 path
            return [fake_ep] if group == "fapilog.sinks" else []

    monkeypatch.setattr(
        loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
    )

    inst = loader.load_plugin("fapilog.sinks", "sample", {"a": 1})
    assert isinstance(inst, _DummyPlugin)
    assert inst.kwargs == {"a": 1}


def test_list_available_includes_builtins_and_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        loader, "BUILTIN_REDACTORS", {"field_mask": _DummyPlugin}, raising=False
    )
    monkeypatch.setattr(
        loader,
        "BUILTIN_ALIASES",
        {"fapilog.redactors": {"field-mask": "field_mask"}},
        raising=False,
    )

    fake_ep = _fake_entry_point("ep_redactor", _DummyPlugin)

    class _FakeEntryPoints:
        def select(self, group: str):
            return [fake_ep] if group == "fapilog.redactors" else []

        def get(self, group: str, default: Any = None):
            return [fake_ep] if group == "fapilog.redactors" else []

    monkeypatch.setattr(
        loader.importlib.metadata, "entry_points", lambda: _FakeEntryPoints()
    )

    names = loader.list_available_plugins("fapilog.redactors")
    assert "field_mask" in names
    assert "field-mask" in names  # alias exposure for UX
    assert "ep_redactor" in names
