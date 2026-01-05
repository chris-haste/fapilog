from __future__ import annotations

import pytest

from fapilog import Settings, _build_pipeline
from fapilog.plugins.processors import BaseProcessor


class _DelegatingProcessor(BaseProcessor):
    name = "delegating"

    def __init__(self) -> None:
        self.seen: list[memoryview] = []

    async def process(self, view: memoryview) -> memoryview:  # noqa: D401
        self.seen.append(view)
        return memoryview(view.tobytes() + b"!")


def test_build_pipeline_loads_processors_with_configs(monkeypatch):
    captured: dict[str, dict[str, object]] = {}

    def fake_load_plugins(group, names, settings, cfgs):
        captured[group] = {
            "names": list(names),
            "cfgs": cfgs,
        }
        if group == "fapilog.processors":
            return ["proc-instance"]
        return []

    monkeypatch.setattr("fapilog._load_plugins", fake_load_plugins)

    settings = Settings(
        core={"processors": ["zero-copy"]},
        plugins={"enabled": True},
    )

    sinks, enrichers, redactors, processors, filters, metrics = _build_pipeline(
        settings
    )

    assert processors == ["proc-instance"]
    assert "fapilog.processors" in captured
    proc_capture = captured["fapilog.processors"]
    assert proc_capture["names"] == ["zero-copy"]
    assert "zero_copy" in proc_capture["cfgs"]


@pytest.mark.asyncio
async def test_base_processor_process_many_returns_processed_views() -> None:
    proc = _DelegatingProcessor()
    views = [memoryview(b"a"), memoryview(b"b")]

    out = await proc.process_many(views)

    assert [bytes(v) for v in out] == [b"a!", b"b!"]
    # process_many should delegate to process for each view
    assert proc.seen and len(proc.seen) == 2
