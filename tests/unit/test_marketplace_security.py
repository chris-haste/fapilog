from __future__ import annotations

from fapilog.plugins.marketplace import (
    CIStatusProvider,
    ComplianceProvider,
    MarketplaceIndexBuilder,
    RatingsProvider,
    SecurityProvider,
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
        return None


class DummySecurity(SecurityProvider):
    def get_security(self, package_name: str):  # type: ignore[override]
        return {"critical": 0, "high": 1}


class DummyCompliance(ComplianceProvider):
    def get_compliance(self, package_name: str):  # type: ignore[override]
        return {"pci_dss": "pass", "hipaa": "unknown"}


def test_index_includes_security_and_compliance():
    b = MarketplaceIndexBuilder(
        package_provider=DummyPackages(),
        ratings_provider=DummyRatings(),
        security_provider=DummySecurity(),
        compliance_provider=DummyCompliance(),
        ci_provider=DummyCI(),
    )
    idx = b.build_index()
    pkg = next(i for i in idx.items if i.distribution_type == "package")
    assert pkg.security == {"critical": 0, "high": 1}
    assert pkg.compliance == {"pci_dss": "pass", "hipaa": "unknown"}
