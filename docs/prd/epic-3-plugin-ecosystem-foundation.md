# Epic 3: Plugin Ecosystem Foundation

**Epic Goal**: Create a universal plugin ecosystem that enables community-driven growth while maintaining architectural excellence and providing both developer-friendly and enterprise-ready plugins.

**Integration Requirements**: Plugin architecture must recreate all v2 extensibility patterns while adding ecosystem support and marketplace integration.

Distribution & Install Model (Non-negotiables)
Base package: fapilog installs core only (pip install fapilog).

Extras: optional feature sets and first-party plugins are installable via extras, e.g. pip install fapilog[fastapi,opentelemetry].

External plugins: community/enterprise plugins are separate PyPI packages using the fapilog-\* naming convention (e.g. fapilog-fastapi, fapilog-splunk), and are also exposed via fapilog extras where applicable.

Discovery: plugins are registered via Python entry points (group="fapilog.plugins"), resolved with importlib.metadata.entry_points.

Version gates: each plugin declares a Requires-Dist: fapilog>=X,<Y range; the core enforces compatibility at load time with a clear error message.

Namespacing: all public plugin APIs live under fapilog.plugins.\* (import path) and expose a minimal, stable interface contract.

Install examples (must be in README and marketplace):

Core only: pip install fapilog

Core + FastAPI integration (first-party extra): pip install fapilog[fastapi]

Community plugin (separate dist): pip install fapilog-splunk

## Story 3.1: Universal Plugin Architecture

As a developer,
I want a simple plugin interface for creating custom sinks, processors, and enrichers,
so that I can extend the library's functionality with my own custom logic.

**Acceptance Criteria:**

1. Async plugin interfaces for sinks, processors, enrichers, and future alerting
2. Simple plugin development with clear documentation and examples
3. Plugin discovery and loading system with version compatibility
4. Plugin validation and quality gates for marketplace inclusion
5. Plugin testing framework recreating test excellence
6. Plugin documentation standards recreating clarity
7. Plugin CI/CD pipeline recreating quality gates
8. Plugin marketplace infrastructure for ecosystem growth
9. Plugin packaging spec:
   1. First-party features exposed as extras via [project.optional-dependencies] in pyproject.toml.
   2. Third-party plugins published as separate fapilog-\* packages.
10. Entry point contract: plugins must register via entry_points={"fapilog.plugins": ["name=package.module:PluginClass"]}.
11. Semantic versioning & compatibility matrix: documented policy and automated check on load.
12. Fallback behavior: safe no-op when an extra isn’t installed; actionable error when a declared plugin can’t be loaded.

## Story 3.2: Plugin Marketplace Infrastructure

As a developer,
I want a plugin marketplace for discovering and installing plugins,
so that I can easily find and use community-developed plugins for common use cases.

**Acceptance Criteria:**

1. Plugin marketplace with search and discovery capabilities
2. Plugin installation and update mechanisms
3. Plugin ratings and reviews for quality assurance
4. Performance benchmarks for plugin comparison
5. Enterprise support for commercial plugins
6. Plugin monetization for community developers
7. Compliance validation for enterprise plugins
8. Security scanning for all plugins
9. Marketplace surfaces install commands for both models (extras and separate packages).
10. Automated compatibility badges (CI-generated) showing tested fapilog core versions per plugin.
11. “Health signals” (downloads, CI status, supported Python versions) and security scan badges.
12. One-click copy for pip and uv commands; guidance for constraints files/lockers.

## Story 3.3: Developer Plugin Experience

As a developer,
I want excellent tools and documentation for creating custom plugins,
so that I can contribute to the ecosystem and share my solutions with the community.

**Acceptance Criteria:**

1. Plugin development guidelines recreating code quality
2. Plugin scaffolding tools for rapid development
3. Plugin testing utilities recreating test coverage
4. Plugin documentation generation recreating clarity
5. Plugin examples and tutorials for common use cases
6. Plugin development environment with hot reloading
7. Plugin debugging tools and error reporting
8. Plugin performance profiling and optimization tools
9. fapilog plugin new <name> scaffolds:
   1. pyproject.toml with fapilog.plugins entry point
   2. tests, type hints, pre-commit, and example PluginClass
10. Template for first-party extras wiring (showing [project.optional-dependencies] and import guards).
11. Local dev docs for verifying extras: pip install -e .[dev,fastapi] and python -c "import fapilog; fapilog.debug_plugins()".

## Story 3.4: Enterprise Plugin Ecosystem

As an enterprise developer,
I want enterprise-ready plugins for compliance and platform integration,
so that I can meet regulatory requirements and integrate with enterprise observability platforms.

**Acceptance Criteria:**

1. Enterprise compliance plugins (PCI-DSS, HIPAA, SOX)
2. Enterprise platform integration plugins (SIEM, Splunk, ELK)
3. Enterprise plugin validation for compliance and security
4. Enterprise plugin testing framework recreating test excellence
5. Enterprise plugin documentation recreating clarity
6. Enterprise plugin support and consulting services
7. Enterprise plugin marketplace with compliance validation
8. Enterprise plugin performance benchmarks and guarantees
9. Supply-chain requirements: signed wheels (Sigstore or similar), SBOM generation, and vulnerability scans in release CI.
10. Enterprise distribution patterns: support for private indexes (Artifactory/Nexus) and constraints files; docs for mirroring extras into internal repos.
11. Long-term support policy indicating minimum overlap of supported core/plugin versions (e.g., N–2).

## Apendix

```python
# fapilog/plugin_api.py
from typing import Protocol, Mapping, Any

class Processor(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, record: Mapping[str, Any]) -> Mapping[str, Any]: ...

class Sink(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def write(self, record: Mapping[str, Any]) -> None: ...
```

```toml
# pyproject.toml (plugin package or core extras provider)
[project]
name = "fapilog-fastapi"
dependencies = ["fapilog>=3.0,<4.0", "fastapi>=0.115"]

[project.entry-points."fapilog.plugins"]
fastapi = "fapilog_fastapi:FastAPIPlugin"
```

```toml
# pyproject.toml (core package exposing extras)
[project.optional-dependencies]
fastapi = ["fapilog-fastapi>=1.0,<2.0", "fastapi>=0.115"]
```
