# Changelog

All notable changes to this project will be documented in this file. This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- **Fixed**: Strict mode serialization drops now correctly increment the `dropped` counter and record metrics; previously these drops were silently unaccounted (Story 1.24).
- Fixed extras documentation accuracy: removed non-existent extras (enterprise, loki, cloud, siem), documented all real extras with descriptions.
- **Security**: Bumped orjson minimum version to 3.9.15 (CVE-2024-27454 fix).
- Added `SECURITY.md` with vulnerability reporting guidance.
- Added `CODE_OF_CONDUCT.md` (Contributor Covenant).
- Fixed Python version badge in README (3.8+ → 3.10+).
- Added production tip callout in README for `preset="production"` guidance.
- Updated plugin group documentation in architecture docs.
- Added CloudWatch sink size limit documentation comment.
- Updated `CONTRIBUTING.md` with correct Python version, repo name, and governance file references.
- Added `SinkWriteError` for sinks to signal write failures to the core pipeline; core now catches these errors (and `False` returns) to trigger fallback and circuit breaker behavior (Story 4.41).
- Updated built-in sinks (`stdout_json`, `stdout_pretty`, `rotating_file`, `audit`) to raise `SinkWriteError` instead of swallowing errors, enabling proper fallback handling.
- Updated `BaseSink` protocol documentation to reflect the new error signaling contract.
- Split large test files into focused modules: `test_error_handling.py` → 4 files, `test_high_performance_lru_cache.py` → 3 files, `test_logger_pipeline.py` → 3 files, `test_rotating_file_sink.py` → 3 files (total test count preserved at 1704).
- Added CI timeout multiplier (`CI_TIMEOUT_MULTIPLIER`) with `get_test_timeout()` helper for timing-sensitive tests on slow CI runners.
- Standardized Hypothesis property test settings: removed per-test `max_examples` overrides so all tests respect `HYPOTHESIS_MAX_EXAMPLES` env var.
- Added fluent builder API (`LoggerBuilder`, `AsyncLoggerBuilder`) for chainable logger configuration with IDE autocomplete support.
- Added pretty console output (`stdout_pretty`) and `format` selection for stdout logging.
- Added one-liner FastAPI setup helpers (`setup_logging`, `get_request_logger`) with lifespan support.
- Added default log-level selection based on TTY/CI when no preset or explicit log level is set.
- Added stderr fallback for sink write failures with optional diagnostics warnings.

## [0.3.5] - 2026-01-01

### Added

- Hash-chain integrity for AuditTrail.

### Changed

- `unbind()` now returns self for method chaining.

### Fixed

- GitHub release workflow now handles existing releases.

## [0.3.4] - 2025-12-30

### Added

- Enterprise key management for tamper-evident plugin (Story 4.18).
- Verification API and CLI for tamper-evident plugin (Story 4.17).
- Enterprise tamper-evident plugin stories and package scaffold.
- Configurable worker count for logging pipeline.

### Fixed

- PYTHONPATH passing to subprocess in CLI test.
- fapilog-tamper tests now skip gracefully if package not available.
- Loop stall tolerance increased for CI runners.
- Prometheus fallback typing for mypy.

## [0.3.3] - 2025-12-22

- Project status upgraded from Alpha to Beta classification.
- Fixed plugin catalog generation to exclude failed plugin entries.
- Disabled PDF/ePub generation in ReadTheDocs due to LaTeX builder incompatibility.
- Added release notes page to documentation (includes CHANGELOG.md).
- Removed placeholder Discord and Plugin Marketplace links from PyPI metadata.

## [0.3.2] - 2025-12-22

- Backpressure configuration now honored: `drop_on_full` waits instead of dropping when set to false; sink/enricher/redactor failures emit diagnostics.
- FastAPI request/response logging middleware added (sampling, header redaction, skip paths) and exported alongside context middleware.
- Metrics dependency is optional via extras; Prometheus exporter disables gracefully when absent; docs updated for lean core + extras.
- New reliability defaults and quality signals docs; coverage badge added (~90%).
- Release workflow now extracts the latest changelog section for GitHub releases and guards builds if the changelog is missing a section.

## [0.3.1] - Documentation release

- Documentation updates and alignment.

## [0.3.0] - Initial release of fapilog

- First public release.
