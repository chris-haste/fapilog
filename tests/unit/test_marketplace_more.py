from __future__ import annotations

import importlib
import importlib.metadata
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from fapilog.plugins.marketplace import (
    CIStatusProvider,
    ExtrasProvider,
    InstallCommands,
    MarketplaceIndex,
    MarketplaceIndexBuilder,
    MarketplacePluginIndexItem,
    SearchFilters,
    _compute_install_commands,
    _extract_declared_fapilog,
    deserialize_index_from_json_bytes,
    search_plugins,
    serialize_index_to_json_bytes,
)


def _mk_item(**kwargs: Any) -> MarketplacePluginIndexItem:
    base = {
        "id": "x",
        "name": "x",
        "summary": "sum",
        "type": "sink",
        "distribution_type": "package",
        "package_name": "fapilog-x",
        "capabilities": [],
        "tags": [],
        "license": None,
        "source_url": None,
        "homepage_url": None,
        "docs_url": None,
        "supported_python": None,
        "declared_fapilog": None,
        "verified_fapilog": [],
        "ci_status": None,
        "downloads": 0,
        "last_updated": None,
        "entry_points": {"present": False, "names": []},
        "install_commands": InstallCommands(
            pip="pip install fapilog-x", uv="uv add fapilog-x"
        ),
    }
    base.update(kwargs)
    return MarketplacePluginIndexItem(**base)


def test_extract_declared_fapilog_variants():
    assert _extract_declared_fapilog(["requests"]) is None
    assert _extract_declared_fapilog(["fapilog>=3,<4"]) == "fapilog>=3,<4"
    assert (
        _extract_declared_fapilog(["fapilog[fastapi]>=3,<4"])
        == "fapilog[fastapi]>=3,<4"
    )
    assert _extract_declared_fapilog(["Fapilog >=3, <4"]) == "Fapilog>=3,<4".replace(
        "Fapilog", "Fapilog"
    )


def test_install_commands_success_and_errors():
    # package success
    cmds = _compute_install_commands("package", package_name="fapilog-acme")
    assert cmds.pip.endswith("fapilog-acme") and cmds.uv.endswith("fapilog-acme")

    # package error
    with pytest.raises(ValueError):
        _compute_install_commands("package")

    # extras success (dedupe and sorted)
    cmds2 = _compute_install_commands("extra", extras=["fastapi", "fastapi", "otel"])
    assert cmds2.pip == 'pip install "fapilog[fastapi,otel]"'

    # extras error
    with pytest.raises(ValueError):
        _compute_install_commands("extra", extras=[])


def test_search_relevance_filters_and_sorting():
    # Build index with varied items
    t1 = _mk_item(id="a", name="splunk", tags=["sink"], downloads=10)
    t2 = _mk_item(
        id="b", name="acme-proc", type="processor", capabilities=["json"], downloads=5
    )
    t3 = _mk_item(
        id="c",
        name="alpha",
        summary="great processor",
        type="processor",
        license="MIT",
        supported_python=">=3.10",
        declared_fapilog=">=3,<4",
        downloads=1,
    )
    # last_updated for sorting
    now = datetime.now(UTC).replace(microsecond=0)
    t1.last_updated = (now - timedelta(days=2)).isoformat()
    t2.last_updated = (now - timedelta(days=1)).isoformat()
    t3.last_updated = now.isoformat()

    idx = MarketplaceIndex(
        version="1.0", generated_at=now.isoformat(), items=[t1, t2, t3]
    )

    # relevance query
    res = search_plugins(idx, query="processor")
    assert res.total >= 1

    # filters
    res2 = search_plugins(idx, filters=SearchFilters(type="processor"))
    assert all(i.type == "processor" for i in res2.items)

    res3 = search_plugins(idx, filters=SearchFilters(license="MIT"))
    assert any(i.license == "MIT" for i in res3.items)

    res4 = search_plugins(idx, filters=SearchFilters(supported_python=">=3.10"))
    assert any(
        i.supported_python and ">=3.10" in i.supported_python for i in res4.items
    )

    res5 = search_plugins(idx, filters=SearchFilters(supported_fapilog=">=3,"))
    assert any(i.declared_fapilog and ">=3," in i.declared_fapilog for i in res5.items)

    # date range
    start = (now - timedelta(days=1, hours=12)).isoformat()
    end = now.isoformat()
    res6 = search_plugins(
        idx, filters=SearchFilters(last_updated_from=start, last_updated_to=end)
    )
    assert all(i.last_updated is not None for i in res6.items)

    # sort last_updated
    res7 = search_plugins(idx, sort="last_updated")
    assert res7.items and res7.items[0].last_updated == t3.last_updated

    # pagination
    res8 = search_plugins(idx, page=2, per_page=1)
    assert res8.total == 3 and len(res8.items) == 1


def test_builder_extras_only_and_json_roundtrip(tmp_path: Path):
    class DummyExtras(ExtrasProvider):
        def list_extras(self):  # type: ignore[override]
            return {"fastapi": ["fastapi>=0.115.0"], "otel": ["opentelemetry"]}

    class DummyPackages:
        def iter_packages(self):  # type: ignore[override]
            return []

    builder = MarketplaceIndexBuilder(
        package_provider=DummyPackages(),
        extras_provider=DummyExtras(),
        ci_provider=CIStatusProvider(),
    )
    idx = builder.build_index()
    assert any(i.distribution_type == "extra" for i in idx.items)

    data = serialize_index_to_json_bytes(idx)
    restored = deserialize_index_from_json_bytes(data)
    assert restored.version == idx.version and len(restored.items) == len(idx.items)


def test_pyproject_extras_provider_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # create minimal pyproject
    content = """
[project]
name = "demo"

[project.optional-dependencies]
fastapi = ["fastapi>=0.115.0"]
obs = ["opentelemetry"]
"""
    p = tmp_path / "pyproject.toml"
    p.write_text(content)

    from fapilog.plugins.marketplace import PyProjectExtrasProvider

    prov = PyProjectExtrasProvider(pyproject_path=p)
    extras = prov.list_extras()
    assert set(extras.keys()) == {"fastapi", "obs"}


def test_installed_packages_provider_iter_packages(monkeypatch: pytest.MonkeyPatch):
    from fapilog.plugins.marketplace import InstalledPackagesProvider

    # Fake entry points mapping with ep.dist
    class EPDist:
        def __init__(self, name: str) -> None:
            self.name = name

    class EP:
        def __init__(self, dist_name: str, name: str) -> None:
            self.dist = EPDist(dist_name)
            self.name = name

    class Eps:
        def __init__(self):
            self._by_group = {"fapilog.sinks": [EP("fapilog-acme", "sink-ep")]}

        def select(self, *, group: str):
            return self._by_group.get(group, [])

        def get(self, group: str, default: list[Any] = None):  # python <3.10 path
            return self._by_group.get(group, default or [])

    monkeypatch.setattr(importlib.metadata, "entry_points", lambda: Eps())

    # Fake distributions iterable
    class Meta:
        def __init__(self, name: str):
            self._data = {
                "Name": name,
                "Requires-Python": ">=3.9",
                "License": "Apache-2.0",
                "Summary": "demo",
                "Home-page": "https://example.com",
                "Project-URL": "https://example.com/repo",
            }

        def get(self, key: str, default: Any = "") -> Any:
            return self._data.get(key, default)

        def get_all(self, key: str) -> list[str]:
            if key == "Requires-Dist":
                return ["fapilog>=3,<4", "requests>=2"]
            return []

    class Dist:
        def __init__(self, name: str) -> None:
            self.metadata = Meta(name)

    monkeypatch.setattr(
        importlib.metadata, "distributions", lambda: [Dist("fapilog-acme")]
    )

    prov = InstalledPackagesProvider()
    pkgs = list(prov.iter_packages())
    assert (
        pkgs
        and pkgs[0].name == "fapilog-acme"
        and pkgs[0].entry_point_names == ["sink-ep"]
    )
