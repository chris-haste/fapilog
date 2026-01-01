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
