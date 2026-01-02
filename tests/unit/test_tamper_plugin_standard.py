from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Add fapilog-tamper to path before importing
_tamper_src = (
    Path(__file__).resolve().parents[2] / "packages" / "fapilog-tamper" / "src"
)
if _tamper_src.exists():
    sys.path.insert(0, str(_tamper_src))

try:
    from fapilog_tamper.enricher import IntegrityEnricher
    from fapilog_tamper.sealed_sink import SealedSink
except Exception:  # pragma: no cover - missing optional dependency
    pytest.skip("fapilog-tamper not available", allow_module_level=True)


def _fake_entry_point(name: str, target: Any) -> Any:
    return SimpleNamespace(name=name, load=lambda: target)


def _fake_entry_points(ep: Any) -> Any:
    class _EPs:
        def select(self, *, group: str) -> list[Any]:
            return [ep] if group in ("fapilog.enrichers", "fapilog.sinks") else []

        def get(
            self, group: str, default: Any = None
        ) -> list[Any]:  # pragma: no cover - py3.8 path
            return [ep] if group in ("fapilog.enrichers", "fapilog.sinks") else []

    return _EPs()


def test_integrity_enricher_loads_via_standard_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fapilog.plugins import loader

    fake_ep = _fake_entry_point("integrity", IntegrityEnricher)
    monkeypatch.setattr(loader, "BUILTIN_ENRICHERS", {}, raising=False)
    monkeypatch.setattr(
        loader, "BUILTIN_ALIASES", {"fapilog.enrichers": {}}, raising=False
    )
    monkeypatch.setattr(
        loader.importlib.metadata, "entry_points", lambda: _fake_entry_points(fake_ep)
    )

    enricher = loader.load_plugin("fapilog.enrichers", "integrity", {"enabled": True})
    assert isinstance(enricher, IntegrityEnricher)


def test_sealed_sink_loads_and_resolves_inner(monkeypatch: pytest.MonkeyPatch) -> None:
    from fapilog.plugins import loader

    class _DummySink:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def start(self) -> None:
            return None

        async def write(self, entry: dict[str, Any]) -> None:
            return None

    monkeypatch.setattr(loader, "BUILTIN_SINKS", {"inner": _DummySink}, raising=False)
    monkeypatch.setattr(loader, "BUILTIN_ALIASES", {"fapilog.sinks": {}}, raising=False)
    monkeypatch.setattr(
        loader.importlib.metadata,
        "entry_points",
        lambda: _fake_entry_points(_fake_entry_point("sealed", SealedSink)),
    )

    sink = loader.load_plugin(
        "fapilog.sinks",
        "sealed",
        {"inner_sink": "inner", "inner_config": {"path": "/tmp/test"}},
    )
    assert isinstance(sink, SealedSink)
    assert isinstance(sink._inner, _DummySink)  # noqa: SLF001


def test_load_integrity_plugin_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    from fapilog.plugins import integrity

    fake_plugin = object()
    ep = _fake_entry_point("legacy", fake_plugin)

    class _EPs:
        def select(self, *, group: str) -> list[Any]:
            return [ep] if group == "fapilog.integrity" else []

        def get(
            self, group: str, default: Any = None
        ) -> list[Any]:  # pragma: no cover - py3.8 path
            return [ep] if group == "fapilog.integrity" else []

    monkeypatch.setattr(integrity.importlib.metadata, "entry_points", lambda: _EPs())

    with pytest.warns(DeprecationWarning):
        assert integrity.load_integrity_plugin("legacy") is fake_plugin
