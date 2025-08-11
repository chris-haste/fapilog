# Technical Assumptions

## Repository Structure: Monorepo

The project will use a monorepo structure to maintain all related components (core library, plugins, documentation, tools) in a single repository for easier development and versioning.

## Service Architecture: Monolith

The core library will be a monolithic architecture with clear separation of concerns through the plugin system. This provides the best balance of simplicity, performance, and maintainability.

## Testing Requirements: Full Testing Pyramid

The project will implement a comprehensive testing pyramid including unit tests, integration tests, performance tests, and enterprise compliance tests. All tests will be async-first to match the library architecture.

## Additional Technical Assumptions and Requests

- **Async-first throughout**: All components must be designed for async operation from the ground up
- **Zero-copy operations**: Memory efficiency through zero-copy serialization and processing
- **Plugin architecture**: Extensible plugin system for sinks, processors, enrichers, and future alerting
- **Enterprise compliance**: Built-in support for PCI-DSS, HIPAA, SOX compliance
- **Performance optimization**: Parallel processing, connection pooling, and adaptive systems
- **Container isolation**: Perfect isolation between logging instances with zero global state
- **Type safety**: Comprehensive async type annotations throughout the codebase
- **Documentation excellence**: Comprehensive async examples and enterprise deployment guides

## Packaging & Distribution

- **Core package**: The base library MUST be installable as `pip install fapilog` and include only core functionality with no framework/web dependencies.
- **First‑party integrations via extras**: Optional integrations (e.g., FastAPI) MUST be enabled via extras, e.g., `pip install fapilog[fastapi]`. These integrations MUST:
  - Declare dependencies under `[project.optional-dependencies]` in `pyproject.toml`.
  - Use import guards so the core operates when the extra is not installed.
  - Emit a clear diagnostic that suggests the correct install command when referenced but unavailable.
- **Third‑party/community plugins as separate wheels**: External plugins MUST be published as independent PyPI distributions named `fapilog-<name>` (e.g., `fapilog-splunk`). They MUST NOT be bundled into the core extras.
- **Plugin discovery**: All plugins (first‑party or third‑party) MUST register via Python entry points using the group **`fapilog.plugins`** and be discoverable via `importlib.metadata.entry_points`.
- **Version compatibility (load‑time gating)**: Plugins MUST declare `Requires-Dist: fapilog>=X,<Y` and the core MUST enforce these constraints at load time. Incompatible plugins MUST be skipped with a structured, actionable diagnostic.
- **Stable public contracts**: Public plugin interfaces (Sink/Processor/Enricher) MUST remain stable within a major version. Breaking changes MUST be versioned appropriately and communicated in release notes.
- **Enterprise readiness**: Release CI SHOULD generate SBOMs, perform vulnerability scans, and support signed wheels. Documentation MUST describe use with private indexes and constraints files.
- **Security & supply chain**: Recommended practices include Sigstore signing, SBOM generation, and vulnerability scanning in release workflows. Enterprises MAY mirror distributions to private indexes; documentation SHOULD include examples for constraints/locks.
