"""
Marketplace index schema, static index builder, and search utilities.

This module provides:
- Pydantic v2 models for representing marketplace items and the index
- Deterministic, static-first index builder that can enumerate:
  - First-party extras from the current project's `pyproject.toml`
  - Third-party packages installed locally that match `fapilog-*`
  - Entry-point discovery signals for `fapilog.*` groups
- Client-side search, filtering, sorting, and pagination utilities

Design principles:
- Static-first: everything can be produced into a JSON index for static sites
- Deterministic/idempotent: builder accepts providers to mock external data
- No network I/O in this module; callers can inject providers for CI or PyPI
"""

from __future__ import annotations

import importlib.metadata
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, cast

import orjson
from pydantic import BaseModel, Field

# ----------------------
# Pydantic Models
# ----------------------


PluginType = Literal[
    "sink",
    "processor",
    "enricher",
    "alerting",
    "integration",
]
DistributionType = Literal["extra", "package"]


class EntryPointSignal(BaseModel):
    present: bool = Field(description="Whether entry points are present")
    names: list[str] = Field(
        default_factory=list,
        description="Registered names",
    )


class InstallCommands(BaseModel):
    pip: str
    uv: str


class MarketplacePluginIndexItem(BaseModel):
    id: str = Field(description="Unique slug identifier")
    name: str = Field(description="Human-readable name")
    summary: str | None = Field(default=None, description="Short summary")
    type: PluginType = Field(description="Plugin type")
    distribution_type: DistributionType = Field(description="extra|package")

    package_name: str | None = Field(default=None, description="PyPI package name")
    extras: list[str] | None = Field(
        default=None, description="Optional-dependency extra names when extra"
    )

    capabilities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    license: str | None = Field(default=None)

    source_url: str | None = Field(default=None)
    homepage_url: str | None = Field(default=None)
    docs_url: str | None = Field(default=None)

    supported_python: str | None = Field(
        default=None, description="Python requirement spec or versions"
    )
    declared_fapilog: str | None = Field(
        default=None, description="Declared compatibility range from metadata"
    )
    verified_fapilog: list[str] = Field(
        default_factory=list,
        description=("Verified versions from CI matrix"),
    )
    ci_status: str | None = Field(default=None, description="CI status string")

    downloads: int | None = Field(default=None)
    last_updated: str | None = Field(
        default=None, description="ISO8601 last release date"
    )

    # Quality signals
    class RatingSummary(BaseModel):
        average: float = Field(ge=0.0, le=5.0, description="Average rating 0-5")
        count: int = Field(ge=0, description="Number of ratings")

    rating: RatingSummary | None = Field(default=None, description="Rating data")
    benchmark: dict | None = Field(default=None, description="Benchmark summary blob")
    # Security & Compliance
    security: dict | None = Field(
        default=None, description="Security scan summary (e.g., vuln counts)"
    )
    compliance: dict | None = Field(
        default=None, description="Compliance validation summary (flags/status)"
    )

    entry_points: EntryPointSignal
    install_commands: InstallCommands


class MarketplaceIndex(BaseModel):
    version: str = Field(description="Index schema version")
    generated_at: str = Field(description="ISO8601 timestamp")
    items: list[MarketplacePluginIndexItem] = Field(default_factory=list)


# ----------------------
# Provider Protocols (duck-typed)
# ----------------------


@dataclass
class PackageInfo:
    name: str
    requires_python: str | None
    requires_dist: list[str]
    license: str | None
    summary: str | None
    homepage_url: str | None
    project_url: str | None
    download_count: int | None
    last_release_date: str | None
    entry_point_names: list[str]


class PackageProvider:
    def iter_packages(self) -> Iterable[PackageInfo]:  # pragma: no cover
        raise NotImplementedError


class InstalledPackagesProvider(PackageProvider):
    """Package provider using importlib.metadata only (local, offline)."""

    GROUPS = [
        "fapilog.sinks",
        "fapilog.processors",
        "fapilog.enrichers",
        "fapilog.alerting",
        "fapilog.plugins",  # legacy aggregate group if used
    ]

    def iter_packages(self) -> Iterable[PackageInfo]:  # pragma: no cover
        # Precompute entry points per distribution
        entry_points = importlib.metadata.entry_points()
        eps: list[importlib.metadata.EntryPoint] = []
        try:
            if hasattr(entry_points, "select"):
                for group in self.GROUPS:
                    eps.extend(entry_points.select(group=group))
            else:  # Python 3.8/3.9 compat path
                for group in self.GROUPS:
                    eps.extend(entry_points.get(group, []))
        except Exception:
            eps = []

        # Map distribution name to entry point names
        dist_to_ep_names: dict[str, list[str]] = {}
        for ep in eps:
            dist_name = getattr(getattr(ep, "dist", None), "name", None)
            if isinstance(dist_name, str):
                dist_to_ep_names.setdefault(dist_name, []).append(ep.name)

        for dist in importlib.metadata.distributions():
            meta = cast(Mapping[str, Any], dist.metadata)
            name = (meta.get("Name") or "").strip()
            if not name:
                continue
            # Only consider third-party plugin package naming pattern
            if name.lower().startswith("fapilog-") and name.lower() != "fapilog":
                requires_dist = list(
                    getattr(meta, "get_all", lambda *_: [])("Requires-Dist") or []
                )
                yield PackageInfo(
                    name=name,
                    requires_python=(meta.get("Requires-Python") or None),
                    requires_dist=requires_dist,
                    license=(meta.get("License") or None),
                    summary=(meta.get("Summary") or None),
                    homepage_url=(meta.get("Home-page") or None),
                    project_url=(meta.get("Project-URL") or None),
                    download_count=None,  # offline provider doesn't fetch
                    last_release_date=None,  # offline provider doesn't fetch
                    entry_point_names=dist_to_ep_names.get(name, []),
                )


class CIStatusProvider:
    def get_ci_verification(
        self,
        package_name: str,
    ) -> tuple[list[str], str | None]:  # pragma: no cover - interface
        """
        Return (verified_fapilog_versions, ci_status).

        The tuple contains the list of verified fapilog versions and an
        optional CI status string.
        """
        return ([], None)


class RatingsProvider:
    def get_rating(
        self, package_name: str
    ) -> dict | None:  # pragma: no cover - interface
        """Return rating summary dict: {"average": float, "count": int}."""
        return None


class BenchmarkProvider:
    def get_benchmark(
        self, package_name: str
    ) -> dict | None:  # pragma: no cover - interface
        """Return benchmark summary blob for display."""
        return None


class SecurityProvider:
    def get_security(
        self, package_name: str
    ) -> dict | None:  # pragma: no cover - interface
        """Return security summary dict (e.g., {"critical":0,"high":1,...})."""
        return None


class ComplianceProvider:
    def get_compliance(
        self, package_name: str
    ) -> dict | None:  # pragma: no cover - interface
        """Return compliance status dict (e.g., {"pci_dss":"pass","hipaa":"unknown"})."""
        return None


class ExtrasProvider:
    def list_extras(self) -> dict[str, list[str]]:  # pragma: no cover - interface
        """Return mapping of extra name to dependency list."""
        raise NotImplementedError


class PyProjectExtrasProvider(ExtrasProvider):
    def __init__(self, pyproject_path: Path | None = None) -> None:
        self.pyproject_path = pyproject_path or Path("pyproject.toml")

    def list_extras(self) -> dict[str, list[str]]:
        # Prefer stdlib tomllib; if unavailable, return empty (no extras)
        import importlib.util

        if importlib.util.find_spec("tomllib") is None:
            return {}

        import tomllib  # Python 3.11+

        if not self.pyproject_path.exists():
            return {}
        data = tomllib.loads(self.pyproject_path.read_text())
        section = data.get("project", {}).get("optional-dependencies", {})
        result: dict[str, list[str]] = {}
        for extra_name, deps in section.items():
            if isinstance(deps, list):
                result[extra_name] = [str(d) for d in deps]
        return result


# ----------------------
# Builder and Utilities
# ----------------------


def _slugify(value: str) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _extract_declared_fapilog(requirements: list[str]) -> str | None:
    # Look for requirements like: "fapilog>=X,<Y" possibly with extras
    for req in requirements:
        req_lower = req.lower()
        if req_lower.startswith("fapilog"):
            # Strip extras if present: fapilog[extra]>=x
            cleaned = req.split(";")[0].strip()
            return cleaned.replace(" ", "")
    return None


def _compute_install_commands(
    distribution_type: DistributionType,
    *,
    package_name: str | None = None,
    extras: list[str] | None = None,
) -> InstallCommands:
    if distribution_type == "package":
        if not package_name:
            raise ValueError("package_name is required for distribution_type=package")
        pip_cmd = f"pip install {package_name}"
        uv_cmd = f"uv add {package_name}"
        return InstallCommands(pip=pip_cmd, uv=uv_cmd)

    # extras
    extras = extras or []
    if not extras:
        raise ValueError("extras must be provided for distribution_type=extra")
    extras_part = ",".join(sorted(set(extras)))
    quoted = f'"fapilog[{extras_part}]"'
    return InstallCommands(
        pip=f"pip install {quoted}",
        uv=f"uv add {quoted}",
    )


class MarketplaceIndexBuilder:
    def __init__(
        self,
        *,
        package_provider: PackageProvider | None = None,
        extras_provider: ExtrasProvider | None = None,
        ci_provider: CIStatusProvider | None = None,
        ratings_provider: RatingsProvider | None = None,
        benchmark_provider: BenchmarkProvider | None = None,
        security_provider: SecurityProvider | None = None,
        compliance_provider: ComplianceProvider | None = None,
        schema_version: str = "1.0",
    ) -> None:
        self.package_provider = package_provider or InstalledPackagesProvider()
        self.extras_provider = extras_provider or PyProjectExtrasProvider()
        self.ci_provider = ci_provider or CIStatusProvider()
        self.ratings_provider = ratings_provider or RatingsProvider()
        self.benchmark_provider = benchmark_provider or BenchmarkProvider()
        # Late-defined protocols below
        self.security_provider = security_provider or SecurityProvider()
        self.compliance_provider = compliance_provider or ComplianceProvider()
        self.schema_version = schema_version

    def build_index(self) -> MarketplaceIndex:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        items: list[MarketplacePluginIndexItem] = []

        # First-party extras
        extras_map = self.extras_provider.list_extras()
        for extra_name in sorted(extras_map.keys()):
            # Synthetic item per extra. Type is "integration" unless specified by convention.
            item = MarketplacePluginIndexItem(
                id=_slugify(f"extra-{extra_name}"),
                name=f"fapilog[{extra_name}]",
                summary=f"First-party extra '{extra_name}'",
                type="integration",
                distribution_type="extra",
                package_name=None,
                extras=[extra_name],
                capabilities=[],
                tags=["extra", extra_name],
                license=None,
                source_url=None,
                homepage_url=None,
                docs_url=None,
                supported_python=None,
                declared_fapilog=None,
                verified_fapilog=[],
                ci_status=None,
                downloads=None,
                last_updated=None,
                entry_points=EntryPointSignal(present=False, names=[]),
                install_commands=_compute_install_commands(
                    "extra", extras=[extra_name]
                ),
            )
            items.append(item)

        # Third-party packages matching fapilog-*
        for pkg in self.package_provider.iter_packages():
            declared = _extract_declared_fapilog(pkg.requires_dist)
            verified, ci_status = self.ci_provider.get_ci_verification(pkg.name)
            entry_present = len(pkg.entry_point_names) > 0
            rating_dict = self.ratings_provider.get_rating(pkg.name)
            bench = self.benchmark_provider.get_benchmark(pkg.name)
            sec = self.security_provider.get_security(pkg.name)
            comp = self.compliance_provider.get_compliance(pkg.name)

            # Derive type from entry point names if possible; default to "sink"
            derived_type: PluginType = "sink"
            for ep_name in pkg.entry_point_names:
                # heuristic: names ending with -processor/-enricher etc.
                n = ep_name.lower()
                if "processor" in n:
                    derived_type = "processor"
                    break
                if "enrich" in n:
                    derived_type = "enricher"
                    break
                if "alert" in n:
                    derived_type = "alerting"
                    break

            item = MarketplacePluginIndexItem(
                id=_slugify(pkg.name),
                name=pkg.name,
                summary=pkg.summary,
                type=derived_type,
                distribution_type="package",
                package_name=pkg.name,
                extras=None,
                capabilities=[],
                tags=["package"],
                license=pkg.license,
                source_url=pkg.project_url,
                homepage_url=pkg.homepage_url,
                docs_url=None,
                supported_python=pkg.requires_python,
                declared_fapilog=declared,
                verified_fapilog=verified,
                ci_status=ci_status,
                downloads=pkg.download_count,
                last_updated=pkg.last_release_date,
                rating=(
                    MarketplacePluginIndexItem.RatingSummary(**rating_dict)
                    if isinstance(rating_dict, dict)
                    else None
                ),
                benchmark=bench,
                security=sec,
                compliance=comp,
                entry_points=EntryPointSignal(
                    present=entry_present,
                    names=pkg.entry_point_names,
                ),
                install_commands=_compute_install_commands(
                    "package",
                    package_name=pkg.name,
                ),
            )
            items.append(item)

        return MarketplaceIndex(
            version=self.schema_version,
            generated_at=now,
            items=items,
        )


# ----------------------
# Search & Sorting
# ----------------------


class SearchFilters(BaseModel):
    type: PluginType | None = None
    distribution_type: DistributionType | None = None
    license: str | None = None
    supported_python: str | None = None
    supported_fapilog: str | None = None
    last_updated_from: str | None = None  # ISO
    last_updated_to: str | None = None  # ISO


class SearchResult(BaseModel):
    total: int
    items: list[MarketplacePluginIndexItem]


def _matches_query(item: MarketplacePluginIndexItem, query: str | None) -> bool:
    if not query:
        return True
    q = query.strip().lower()
    hay = " ".join(
        [
            item.name or "",
            item.summary or "",
            " ".join(item.tags or []),
            " ".join(item.capabilities or []),
        ]
    ).lower()
    return q in hay


def _passes_filters(item: MarketplacePluginIndexItem, f: SearchFilters) -> bool:
    if f.type and item.type != f.type:
        return False
    if f.distribution_type and item.distribution_type != f.distribution_type:
        return False
    if f.license and (item.license or "").lower() != f.license.lower():
        return False
    if f.supported_python and item.supported_python:
        if f.supported_python not in item.supported_python:
            return False
    if f.supported_fapilog and item.declared_fapilog:
        if f.supported_fapilog not in item.declared_fapilog:
            return False

    # Date range filters if available
    def to_dt(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    last = to_dt(item.last_updated)
    from_dt = to_dt(f.last_updated_from)
    to_dt_ = to_dt(f.last_updated_to)
    if from_dt and (not last or last < from_dt):
        return False
    if to_dt_ and (not last or last > to_dt_):
        return False
    return True


def _relevance_score(item: MarketplacePluginIndexItem, query: str | None) -> int:
    if not query:
        return 0
    q = query.lower()
    score = 0
    if item.name and item.name.lower() == q:
        score += 100
    if item.name and q in item.name.lower():
        score += 20
    score += sum(5 for t in (item.tags or []) if q in t.lower())
    score += sum(5 for c in (item.capabilities or []) if q in c.lower())
    if item.summary and q in item.summary.lower():
        score += 3
    return score


def search_plugins(
    index: MarketplaceIndex,
    *,
    query: str | None = None,
    filters: SearchFilters | None = None,
    sort: Literal["relevance", "downloads", "last_updated"] = "relevance",
    page: int = 1,
    per_page: int = 20,
) -> SearchResult:
    filters = filters or SearchFilters()

    candidates = [
        i
        for i in index.items
        if _matches_query(i, query) and _passes_filters(i, filters)
    ]

    if sort == "relevance":
        candidates.sort(
            key=lambda i: _relevance_score(i, query),
            reverse=True,
        )
    elif sort == "downloads":
        candidates.sort(key=lambda i: (i.downloads or 0), reverse=True)
    elif sort == "last_updated":

        def dt(i: MarketplacePluginIndexItem) -> float:
            try:
                if i.last_updated:
                    return datetime.fromisoformat(
                        i.last_updated.replace("Z", "+00:00")
                    ).timestamp()
            except Exception:
                pass
            return 0.0

        candidates.sort(key=dt, reverse=True)

    total = len(candidates)
    start = max(0, (page - 1) * per_page)
    end = start + per_page
    return SearchResult(total=total, items=candidates[start:end])


# ----------------------
# JSON helpers
# ----------------------


def serialize_index_to_json_bytes(index: MarketplaceIndex) -> bytes:
    data: bytes = orjson.dumps(index.model_dump(mode="json"))
    return data


def deserialize_index_from_json_bytes(data: bytes) -> MarketplaceIndex:
    return MarketplaceIndex.model_validate(orjson.loads(data))
