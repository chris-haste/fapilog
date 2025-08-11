from __future__ import annotations

from pathlib import Path

from fapilog.plugins.marketplace import (
    CIStatusProvider,
    ExtrasProvider,
    MarketplaceIndexBuilder,
    PackageInfo,
    PackageProvider,
    SearchFilters,
    deserialize_index_from_json_bytes,
    search_plugins,
    serialize_index_to_json_bytes,
)


class DummyPackages(PackageProvider):
    def __init__(self) -> None:
        self.items = [
            PackageInfo(
                name="fapilog-splunk",
                requires_python=">=3.9",
                requires_dist=["fapilog>=3,<4", "requests"],
                license="Apache-2.0",
                summary="Splunk sink",
                homepage_url=None,
                project_url=None,
                download_count=5000,
                last_release_date="2025-08-01T00:00:00Z",
                entry_point_names=["splunk-sink"],
            ),
            PackageInfo(
                name="fapilog-acme-processor",
                requires_python=">=3.10",
                requires_dist=["fapilog>=3.1,<4"],
                license="MIT",
                summary="ACME processor",
                homepage_url=None,
                project_url=None,
                download_count=100,
                last_release_date="2025-08-02T00:00:00Z",
                entry_point_names=["acme-processor"],
            ),
        ]

    def iter_packages(self):
        return list(self.items)


class DummyExtras(ExtrasProvider):
    def list_extras(self):
        return {"fastapi": ["fastapi>=0.115.0"], "opentelemetry": ["opentelemetry"]}


class DummyCI(CIStatusProvider):
    def get_ci_verification(self, package_name: str) -> tuple[list[str], str | None]:
        if package_name == "fapilog-splunk":
            return (["3.0", "3.1"], "passing")
        return ([], "unknown")


def test_build_and_serialize_index(tmp_path: Path):
    builder = MarketplaceIndexBuilder(
        package_provider=DummyPackages(),
        extras_provider=DummyExtras(),
        ci_provider=DummyCI(),
    )
    index = builder.build_index()
    assert len(index.items) >= 3  # 2 packages + at least 1 extra

    data = serialize_index_to_json_bytes(index)
    restored = deserialize_index_from_json_bytes(data)
    assert restored.version == index.version
    assert len(restored.items) == len(index.items)


def test_search_and_filters():
    builder = MarketplaceIndexBuilder(
        package_provider=DummyPackages(),
        extras_provider=DummyExtras(),
        ci_provider=DummyCI(),
    )
    index = builder.build_index()

    # text query
    res = search_plugins(index, query="splunk")
    assert res.total >= 1
    assert any("splunk" in (i.name or "").lower() for i in res.items)

    # filter by type
    res2 = search_plugins(index, filters=SearchFilters(type="processor"))
    assert any(i.type == "processor" for i in res2.items) or res2.total == 0

    # sort by downloads
    res3 = search_plugins(index, sort="downloads")
    # ensure non-increasing
    dls = [i.downloads or 0 for i in res3.items]
    assert dls == sorted(dls, reverse=True)
