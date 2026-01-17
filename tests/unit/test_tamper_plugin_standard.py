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


def test_tamper_config_models_expose_standard_fields() -> None:
    from fapilog_tamper.config import IntegrityEnricherConfig, SealedSinkConfig

    enricher_cfg = IntegrityEnricherConfig()
    assert enricher_cfg.algorithm == "sha256"
    assert enricher_cfg.key_provider == "env"
    assert enricher_cfg.chain_state_path is None

    sink_cfg = SealedSinkConfig()
    assert sink_cfg.inner_sink == "rotating_file"
    assert sink_cfg.inner_config == {}
    assert sink_cfg.manifest_path is None


@pytest.mark.asyncio
async def test_standard_tamper_configs_flow_into_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fapilog import Settings, get_logger

    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    class _DummySink:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.started = False
            self.writes: list[dict[str, Any]] = []

        async def start(self) -> None:
            self.started = True

        async def write(self, entry: dict[str, Any]) -> None:
            self.writes.append(entry)

    class _DummyEnricher:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

        async def enrich(self, entry: dict[str, Any]) -> dict[str, Any]:
            return entry

    def _fake_load(
        group: str,
        name: str,
        config: dict[str, Any] | None = None,
        *,
        validation_mode: Any = None,
        allow_external: bool | None = None,
        allowlist: list[str] | None = None,
    ) -> Any:
        calls.append((group, name, config))
        if group == "fapilog.sinks":
            return _DummySink(**(config or {}))
        if group == "fapilog.enrichers":
            return _DummyEnricher(**(config or {}))
        if group in ("fapilog.redactors", "fapilog.processors", "fapilog.filters"):
            # Return a minimal mock for these groups
            return None
        raise AssertionError(f"unexpected group {group}")

    monkeypatch.setattr("fapilog.plugins.loader.load_plugin", _fake_load)

    settings = Settings()
    settings.core.sinks = ["sealed"]
    settings.core.enrichers = ["integrity"]
    settings.core.enable_redactors = False
    settings.sink_config.sealed.inner_sink = "stdout_json"
    settings.sink_config.sealed.inner_config = {"directory": str(tmp_path)}
    settings.sink_config.sealed.manifest_path = str(tmp_path / "manifests")
    settings.enricher_config.integrity.algorithm = "sha256"
    settings.enricher_config.integrity.key_id = "kid-123"

    logger = get_logger(settings=settings)
    logger.info("hello tamper")
    await logger.stop_and_drain()

    sink_call = next(c for c in calls if c[0] == "fapilog.sinks")
    enricher_call = next(c for c in calls if c[0] == "fapilog.enrichers")

    assert sink_call[1] == "sealed"
    assert sink_call[2] is not None  # noqa: WA003
    assert sink_call[2]["inner_sink"] == "stdout_json"
    assert sink_call[2]["manifest_path"] == str(tmp_path / "manifests")
    assert sink_call[2]["inner_config"] == {"directory": str(tmp_path)}

    assert enricher_call[1] == "integrity"
    assert enricher_call[2] is not None  # noqa: WA003
    assert enricher_call[2]["algorithm"] == "sha256"
    assert enricher_call[2]["key_id"] == "kid-123"
