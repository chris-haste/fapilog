# Changelog

All notable changes to this project will be documented in this file. This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Logger instance caching: `get_logger()` and `get_async_logger()` now cache instances by name (like stdlib `logging.getLogger()`), preventing resource exhaustion from unbounded logger creation (Story 10.29).
- `reuse` parameter for `get_logger()` and `get_async_logger()` to opt out of caching when needed (e.g., tests).
- `get_cached_loggers()` function to inspect cached logger names and types.
- `clear_logger_cache()` async function to drain and clear all cached loggers.
- `ResourceWarning` emitted when loggers are garbage collected without being drained.

## [0.4.0] - 2026-01-19

### Breaking Changes

- `fastapi` preset now enables redaction by default (`field_mask`, `regex_mask`, `url_credentials`), matching `production` preset security posture (Story 10.21). Use `dev` preset for debugging or explicitly set `redactors=[]` to disable.
- Log schema v1.1 with semantic field groupings (`context`, `diagnostics`, `data`); `metadata` renamed to `data`, `correlation_id` moved to `context.correlation_id`, timestamp now RFC3339 string (Story 1.26). See `docs/schema-migration-v1.0-to-v1.1.md`.
- Enrichers now return nested dicts targeting semantic groups (`{"diagnostics": {...}}`) instead of flat dicts; `enrich_parallel()` uses deep-merge; `LogEvent` model updated to v1.1 schema with `context`, `diagnostics`, `data` fields replacing `metadata`, `correlation_id`, `component` (Story 1.27).
- Production preset now includes `regex_mask` redactor for broader secret protection; users may see additional fields masked (Story 4.47).
- External plugins now blocked by default; use `plugins.allow_external=true` or `plugins.allowlist` for explicit opt-in (Story 3.5).

### Added

- Fluent builder API (`LoggerBuilder`, `AsyncLoggerBuilder`) for chainable logger configuration with IDE autocomplete support.
- Pretty console output (`stdout_pretty`) and `format` selection for stdout logging.
- One-liner FastAPI setup helpers (`setup_logging`, `get_request_logger`) with lifespan support.
- Default log-level selection based on TTY/CI when no preset or explicit log level is set.
- Stderr fallback for sink write failures with optional diagnostics warnings.
- `SinkWriteError` for sinks to signal write failures to the core pipeline; core now catches these errors (and `False` returns) to trigger fallback and circuit breaker behavior (Story 4.41).
- CI smoke test for benchmark script to catch future regressions.
- CI timeout multiplier (`CI_TIMEOUT_MULTIPLIER`) with `get_test_timeout()` helper for timing-sensitive tests on slow CI runners.
- `SECURITY.md` with vulnerability reporting guidance.
- `CODE_OF_CONDUCT.md` (Contributor Covenant).
- Production tip callout in README for `preset="production"` guidance.

### Changed

- Serialization path cleanup - `serialize_envelope()` now trusts upstream v1.1 schema compliance and only fails for non-JSON-serializable objects; exception-driven fallback is now truly exceptional, not the normal path; `strict_envelope_mode` now works correctly (Story 1.28).
- Internal diagnostics now write to stderr by default (Unix convention); add `core.diagnostics_output="stdout"` for backward compatibility (Story 6.11).
- Updated built-in sinks (`stdout_json`, `stdout_pretty`, `rotating_file`, `audit`) to raise `SinkWriteError` instead of swallowing errors, enabling proper fallback handling.
- Updated `BaseSink` protocol documentation to reflect the new error signaling contract.
- Aligned ruff, black, and mypy target versions with `requires-python = ">=3.10"`; added pre-commit hook to enforce Python 3.10+ (Story 10.16).
- Standardized Hypothesis property test settings: removed per-test `max_examples` overrides so all tests respect `HYPOTHESIS_MAX_EXAMPLES` env var.
- Split large test files into focused modules: `test_error_handling.py` → 4 files, `test_high_performance_lru_cache.py` → 3 files, `test_logger_pipeline.py` → 3 files, `test_rotating_file_sink.py` → 3 files (total test count preserved at 1704).

### Fixed

- Benchmark script key alignment in `derive_verdicts()` to match actual output keys from `benchmark()` (Story 10.11).
- Strict mode serialization drops now correctly increment the `dropped` counter and record metrics; previously these drops were silently unaccounted (Story 1.24).
- Extras documentation accuracy: removed non-existent extras (enterprise, loki, cloud, siem), documented all real extras with descriptions.
- Python version badge in README (3.8+ → 3.10+).
- Plugin group documentation in architecture docs.
- `CONTRIBUTING.md` with correct Python version, repo name, and governance file references.

### Security

- WebhookSink now supports HMAC-SHA256 signatures (`signature_mode="hmac"`) instead of sending secrets in headers; legacy header mode emits deprecation warning (Story 4.42).
- Bumped orjson minimum version to 3.9.15 (CVE-2024-27454 fix).
- Fallback minimal redaction now recurses into lists, preventing secrets in arrays from leaking to stderr during sink failures (Story 4.48).

### Performance

- Cache sampling rate, filter config, and error dedupe window at logger initialization to avoid `Settings()` instantiation on every log call (Story 1.23).

### Documentation

- Added performance benchmarks page with methodology, results, and reproduction instructions (Story 10.20).
- Added `redaction-guarantee.md` documenting exact redaction behavior per preset; fixed inaccurate claims in `reliability-defaults.md` (Story 4.47).
- Documented same-thread backpressure behavior where `drop_on_full=False` cannot be honored; enhanced diagnostic warning with `drop_on_full_setting` field (Story 1.19).
- Added automated changelog generation with git-cliff and conventional commit linting via pre-commit hooks; release workflow now validates changelog entries match tagged version (Story 10.12).
- Added CloudWatch sink size limit documentation comment.

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
