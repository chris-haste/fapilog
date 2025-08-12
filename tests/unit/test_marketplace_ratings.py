from __future__ import annotations

from fapilog.plugins.marketplace import (
    BenchmarkProvider,
    CIStatusProvider,
    MarketplaceIndexBuilder,
    RatingsProvider,
)


class DummyPackages:
    def iter_packages(self):  # type: ignore[override]
        class P:
            name = "fapilog-acme"
            requires_python = ">=3.10"
            requires_dist = ["fapilog>=3,<4"]
            license = "Apache-2.0"
            summary = "demo"
            homepage_url = None
            project_url = None
            download_count = 123
            last_release_date = None
            entry_point_names = ["sink-ep"]

        yield P()


class DummyCI(CIStatusProvider):
    def get_ci_verification(self, package_name: str):  # type: ignore[override]
        return (["3.0.0a1"], "passing")


class DummyRatings(RatingsProvider):
    def get_rating(self, package_name: str):  # type: ignore[override]
        return {"average": 4.5, "count": 10}


class DummyBench(BenchmarkProvider):
    def get_benchmark(self, package_name: str):  # type: ignore[override]
        return {"p50_ms": 1.2}


def test_index_includes_rating_and_benchmark():
    b = MarketplaceIndexBuilder(
        package_provider=DummyPackages(),
        ratings_provider=DummyRatings(),
        benchmark_provider=DummyBench(),
        ci_provider=DummyCI(),
    )
    idx = b.build_index()
    # Select the package item (extras come first)
    pkg = next(i for i in idx.items if i.distribution_type == "package")
    assert pkg.rating is not None
    assert pkg.rating.average == 4.5
    assert pkg.benchmark == {"p50_ms": 1.2}
