from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from fapilog.core import Settings
from fapilog.core.advanced_validation import validate_advanced_settings
from fapilog.core.change_detection import (
    compute_file_signature,
    signatures_differ,
)
from fapilog.core.hot_reload import ConfigHotReloader
from fapilog.core.migration import migrate_to_latest, register_migration


@pytest.mark.asyncio
async def test_compute_signature_and_diff(tmp_path) -> None:
    p = tmp_path / "conf.json"
    p.write_text("{}")
    sig1 = await compute_file_signature(str(p))
    p.write_text("{\n}\n")
    sig2 = await compute_file_signature(str(p))
    assert signatures_differ(sig1, sig2)


@pytest.mark.asyncio
async def test_hot_reload_calls_callbacks(tmp_path, monkeypatch) -> None:
    p = tmp_path / "c.json"
    p.write_text("{}")

    async def loader() -> Settings:
        # Minimal load via env only
        from fapilog.core.config import load_settings

        return await load_settings(env={})

    applied = []
    errors = []

    async def on_applied(s: Settings) -> None:
        applied.append(s)

    async def on_error(e: Exception) -> None:
        errors.append(e)

    reloader = ConfigHotReloader(
        path=str(p),
        loader=loader,
        on_applied=on_applied,
        on_error=on_error,
    )
    await reloader.start()
    try:
        p.write_text("{\n}\n")
        await asyncio.sleep(1.0)
        assert len(applied) >= 1
        assert len(errors) == 0
    finally:
        await reloader.stop()


@pytest.mark.asyncio
async def test_advanced_validation_cross_field() -> None:
    s = Settings()
    # Core enables metrics, but observability.metrics is disabled by default
    s.core.enable_metrics = True
    result = await validate_advanced_settings(s)
    assert not result.ok
    assert any("observability.metrics.enabled" == i.field for i in result.issues)


def test_migration_default_and_custom() -> None:
    data = {"schema_version": "0.9", "core": {"app_name": "x"}}

    def bump_to_1_0(d: Mapping[str, Any]) -> Mapping[str, Any]:
        nd = dict(d)
        nd["schema_version"] = "1.0"
        return nd

    register_migration("0.9", bump_to_1_0)
    res = migrate_to_latest(data)
    assert res.did_migrate is True
    assert res.to_version == "1.0"
