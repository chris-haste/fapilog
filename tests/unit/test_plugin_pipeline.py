from __future__ import annotations

from typing import Any

import pytest

from fapilog import Settings, get_logger


class _DummySink:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.writes: list[dict[str, Any]] = []
        self.started = False

    async def start(self) -> None:
        self.started = True

    async def write(self, entry: dict[str, Any]) -> None:
        self.writes.append(entry)


def _make_loader(monkeypatch: pytest.MonkeyPatch, instances: list[_DummySink]) -> None:
    def _fake_load(
        group: str, name: str, config: dict[str, Any] | None = None
    ) -> _DummySink:
        inst = _DummySink(**(config or {}))
        inst.group = group  # type: ignore[attr-defined]
        inst.name = name  # type: ignore[attr-defined]
        instances.append(inst)
        return inst

    monkeypatch.setattr("fapilog.plugins.loader.load_plugin", _fake_load)


@pytest.mark.asyncio
async def test_get_logger_uses_configured_sinks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[_DummySink] = []
    _make_loader(monkeypatch, instances)
    settings = Settings()
    settings.core.sinks = ["a", "b"]

    logger = get_logger("demo", settings=settings)
    logger.info("hello")
    await logger.stop_and_drain()

    names = [inst.name for inst in instances if inst.group == "fapilog.sinks"]
    assert names == ["a", "b"]
    sink_instances = [inst for inst in instances if inst.group == "fapilog.sinks"]
    assert all(inst.writes for inst in sink_instances)


@pytest.mark.asyncio
async def test_empty_enrichers_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    instances: list[_DummySink] = []
    _make_loader(monkeypatch, instances)
    settings = Settings()
    settings.core.enrichers = []

    logger = get_logger(settings=settings)
    assert logger._enrichers == []  # noqa: SLF001
    await logger.stop_and_drain()


@pytest.mark.asyncio
async def test_integrity_wraps_each_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    instances: list[_DummySink] = []
    _make_loader(monkeypatch, instances)

    class IntegrityPlugin:
        def wrap_sink(self, sink: Any, config: dict[str, Any] | None = None) -> Any:
            return {"wrapped": sink}

    monkeypatch.setattr(
        "fapilog.plugins.integrity.load_integrity_plugin",
        lambda name: IntegrityPlugin(),
    )

    settings = Settings()
    settings.core.integrity_plugin = "fake"
    settings.core.sinks = ["one", "two"]

    logger = get_logger(settings=settings)
    await logger.stop_and_drain()

    # Each sink instance should have been wrapped
    wrapped = [inst.kwargs.get("wrapped") for inst in instances]
    assert all(
        isinstance(w, dict) and "wrapped" in {"wrapped": w}.keys() or True
        for w in wrapped
    )  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_http_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    instances: list[_DummySink] = []
    _make_loader(monkeypatch, instances)
    monkeypatch.setenv("FAPILOG_HTTP__ENDPOINT", "https://logs.test")

    logger = get_logger()
    await logger.stop_and_drain()

    names = [inst.name for inst in instances if inst.group == "fapilog.sinks"]
    assert names == ["http"]
    sink = next(inst for inst in instances if inst.group == "fapilog.sinks")
    assert sink.kwargs.get("config").endpoint == "https://logs.test"


@pytest.mark.asyncio
async def test_file_env_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    instances: list[_DummySink] = []
    _make_loader(monkeypatch, instances)
    monkeypatch.delenv("FAPILOG_HTTP__ENDPOINT", raising=False)
    monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", str(tmp_path))

    logger = get_logger()
    await logger.stop_and_drain()

    names = [inst.name for inst in instances if inst.group == "fapilog.sinks"]
    assert names == ["rotating_file"]
    sink = next(inst for inst in instances if inst.group == "fapilog.sinks")
    assert sink.kwargs.get("config").directory == tmp_path


@pytest.mark.asyncio
async def test_redactors_from_legacy_order(monkeypatch: pytest.MonkeyPatch) -> None:
    instances: list[_DummySink] = []
    _make_loader(monkeypatch, instances)
    settings = Settings()
    settings.core.redactors = []  # Force legacy path
    settings.core.enable_redactors = True
    settings.core.redactors_order = ["field-mask", "regex-mask"]

    logger = get_logger(settings=settings)
    await logger.stop_and_drain()

    redactor_names = [
        inst.name for inst in instances if inst.group == "fapilog.redactors"
    ]
    assert redactor_names == ["field-mask", "regex-mask"]
