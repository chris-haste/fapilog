# Changelog

All notable changes to this project will be documented in this file. This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking Changes

- **Removed deprecated `SignatureMode.HEADER` from webhook sink:** The insecure `header` signature mode that sent secrets in plain `X-Webhook-Secret` headers has been removed. All webhook authentication now uses HMAC-SHA256 signatures via `X-Fapilog-Signature-256`. This was flagged as a security risk in the v0.7.0 audit. If you were explicitly using `signature_mode="header"`, remove that parameter to use the secure default.

### Changed

- **Production preset disables Postgres auto-DDL:** The `production` preset now sets `create_table=False` for Postgres sink configuration, requiring explicit table provisioning via migrations. This prevents unexpected DDL execution in regulated environments (Story 10.32).
- **Worker event-based wakeup:** The background worker loop now uses `asyncio.Event` signaling instead of fixed 1ms polling when an enqueue event is provided, reducing CPU wakeups when the queue is empty (Story 10.32).
- **Doc accuracy CI now fails on missing critical files:** The `scripts/check_doc_accuracy.py` script now fails when required documentation files are missing, instead of silently skipping them. This prevents security-sensitive documentation from drifting without CI catching it.

### Fixed

- **Silent data loss in `write_serialized`:** Fixed correctness issue where HTTP, Webhook, Loki, CloudWatch, and PostgreSQL sinks silently replaced log data with placeholder values (e.g., `{"message": "fallback"}`) when deserialization failed. All sinks now raise `SinkWriteError` with diagnostics, enabling proper fallback and circuit breaker handling (Story 4.53).
- **Plugin metadata version default:** Changed `create_plugin_metadata()` default `min_fapilog_version` from `"3.0.0"` to `"0.1.0"`. The previous default was incorrect for a 0.x project and caused compatibility check failures for plugin authors (Story 10.32).

### Added

- **Known-good dependency constraints file:** Added `constraints.txt` with pinned versions for security-conscious production deployments. Install with `pip install fapilog -c constraints.txt` (Story 12.22).

### Documentation

- **Backpressure API documentation accuracy:** Fixed incorrect examples showing non-existent `policy="wait"` parameter and `discard_oldest` policy. Documentation now correctly shows actual `with_backpressure(wait_ms=..., drop_on_full=...)` API with behavior table explaining parameter combinations (Story 10.31).
- **Architecture documentation accuracy:** Removed stale references to non-existent components (`ComplianceEngine`, `UniversalSettings`, `EventCategory`) and deleted outdated monolithic `docs/architecture.md` (Story 12.15).
- **Production checklist documentation:** Added consolidated pre-deployment checklist covering preset selection, metrics, diagnostics, redaction validation, backpressure tuning, and graceful shutdown (Story 12.16).
- **stdlib bridge documentation:** Added user guide for `enable_stdlib_bridge()` with API reference, common use cases, Django/Celery integration examples, level mapping, and troubleshooting (Story 12.18).
- **Production installation guide:** Added documentation for using constraints file to pin dependencies to tested versions (Story 12.22).

## [0.7.0] - 2026-01-27

### Breaking Changes

- **Unified Redaction API:** The following methods have been removed and consolidated into `with_redaction()`:
  - `with_field_mask()` - use `with_redaction(fields=[...], mask="...")`
  - `with_regex_mask()` - use `with_redaction(patterns=[...], mask="...")`
  - `with_url_credential_redaction()` - use `with_redaction(url_credentials=True)`
  - `with_redaction_guardrails()` - use `with_redaction(max_depth=..., max_keys=...)`
  - `with_redaction_preset()` - use `with_redaction(preset="...")`

  **Migration guide:**
  ```python
  # Old                                    # New
  .with_field_mask(["password"])          .with_redaction(fields=["password"])
  .with_regex_mask([".*secret.*"])        .with_redaction(patterns=[".*secret.*"])
  .with_url_credential_redaction()        .with_redaction(url_credentials=True)
  .with_redaction_guardrails(max_depth=10).with_redaction(max_depth=10)
  .with_redaction_preset("GDPR_PII")      .with_redaction(preset="GDPR_PII")
  ```

- **Auto-prefix for field names:** `with_redaction(fields=["password"])` now automatically adds the `data.` prefix for simple field names (no dots). Use `auto_prefix=False` to disable. This ensures fields are correctly matched in the log envelope structure.

- **Production/FastAPI/Serverless presets now apply CREDENTIALS preset:** Security-focused presets (`production`, `fastapi`, `serverless`) automatically apply the `CREDENTIALS` redaction preset for comprehensive secret protection. Custom credential fields are no longer hardcoded in these presets.

### Added

- **Unified `with_redaction()` API:** Single method for all redaction configuration with preset support, URL credentials, guardrails, and custom fields/patterns (Story 3.8).
- **Preset discovery methods:** `LoggerBuilder.list_redaction_presets()` and `LoggerBuilder.get_redaction_preset_info(name)` for discovering available redaction presets.
- **Multiple preset support:** `with_redaction(preset=["GDPR_PII", "PCI_DSS"])` applies multiple presets in one call.
- **Composable redaction presets:** One-liner compliance protection via `with_redaction(preset="GDPR_PII")`. Includes presets for GDPR, CCPA, HIPAA, PCI-DSS, and CREDENTIALS with inheritance support and metadata filtering (Story 3.8).

### Changed

- **`with_redaction()` is now additive by default:** Calling `with_redaction()` multiple times merges fields/patterns instead of replacing. Use `replace=True` to restore the previous overwrite behavior (Story 3.8).

### Documentation

- New dedicated `/redaction/` documentation section with presets reference, configuration guide, behavior documentation, and testing guide.
- Added compliance redaction cookbook explaining what field-name matching covers and its limitations.
- Updated enterprise documentation with compliance preset examples and cross-references.
- Improved documentation navigation structure and fixed toctree cross-references.
- Added configuration approach decision guide with comparison matrix (preset vs builder vs settings).

## [0.6.0] - 2026-01-26

### Added

- **Graceful log drain on shutdown:** Loggers now automatically flush pending logs during application shutdown via `atexit` handlers (Story 6.13). This ensures logs are not lost when processes terminate.
- **Regex ReDoS protection:** `RegexMaskRedactor` now validates patterns at config time to prevent catastrophic backtracking. Patterns with nested quantifiers, overlapping alternation, or wildcards in bounded repetition are rejected. Use `allow_unsafe_patterns=True` to bypass validation if needed (Story 4.50).

### Changed

- **Secure header redaction by default:** `LoggingMiddleware` now redacts sensitive headers (Authorization, Cookie, X-API-Key, etc.) by default when `include_headers=True` (Story 4.51). This prevents accidental credential leakage in logs.
  - Use `additional_redact_headers` to add custom headers to the default list
  - Use `allow_headers` for allowlist mode (only log specified headers)
  - Use `disable_default_redactions=True` to opt out (emits warning)

### Documentation

- Added Django structured logging cookbook entry.
- Added library comparison pages (why-fapilog, alternative library comparisons).
- Added security audit findings as stories for tracking.

## [0.5.1] - 2026-01-21

### Added

- **FastAPI `log_errors_on_skip` parameter:** `LoggingMiddleware` and `setup_logging()` now accept `log_errors_on_skip` (default: True) to log unhandled exceptions on skipped paths (Story 1.32). This ensures visibility into crashes on health endpoints while still skipping routine success logs.

### Documentation

- Added 10 cookbook recipes for common FastAPI logging patterns:
  - FastAPI request_id logging
  - FastAPI JSON logging
  - Non-blocking async logging
  - Development and production logging configuration
  - Redacting secrets and PII
  - Safe request/response logging
  - Skip noisy endpoints
  - Log sampling and rate limiting
  - Graceful shutdown and log flushing
  - Exception logging with request context
- SEO improvements with sitemap generation and canonical URL tags.
- Fixed documentation accuracy and cross-reference issues.

### Changed

- Updated PyPI description to be more concrete.
- Organized audit assessment files into versioned directories.

## [0.5.0] - 2026-01-21

### Breaking Changes

- **Logger instance caching enabled by default:** `get_logger()` and `get_async_logger()` now cache instances by name, matching stdlib `logging.getLogger()` behavior (Story 10.29). This prevents resource exhaustion from unbounded logger creation.

  **Migration:** Code that relied on fresh instances per call should add `reuse=False`:

  ```python
  # v0.4.0: each call created a new instance
  # v0.5.0: same name returns cached instance (add reuse=False for old behavior)
  logger = get_logger("my-service", reuse=False)
  ```

- **ResourceWarning on undrained loggers:** Loggers created with `reuse=False` that are garbage collected without `drain()` being called now emit a `ResourceWarning`.

  **Migration:** Use context managers or explicit cleanup:

  ```python
  # Option 1: Context manager (recommended)
  async with runtime_async() as logger:
      logger.info("message")

  # Option 2: Explicit drain
  logger = get_logger("test", reuse=False)
  # ... use logger ...
  await logger.drain()

  # Option 3: Clear cache in test teardown
  await clear_logger_cache()
  ```

### Added

- Logger instance caching: `get_logger()` and `get_async_logger()` now cache instances by name (like stdlib `logging.getLogger()`), preventing resource exhaustion from unbounded logger creation (Story 10.29).
- `reuse` parameter for `get_logger()` and `get_async_logger()` to opt out of caching when needed (e.g., tests).
- `get_cached_loggers()` function to inspect cached logger names and types.
- `clear_logger_cache()` async function to drain and clear all cached loggers.
- `ResourceWarning` emitted when loggers are garbage collected without being drained.
- `serverless` preset for AWS Lambda, Google Cloud Run, and Azure Functions: stdout-only output, `drop_on_full=True`, smaller batch size (25), production-grade redaction (Story 10.30).
- **Builder API parity with Settings** (Stories 10.22-10.27):
  - Core settings: `with_level()`, `with_name()`, `with_queue_size()`, `with_workers()`, `with_drop_on_full()`, `with_strict_mode()`, `with_diagnostics()`
  - Cloud sinks: `with_cloudwatch()`, `with_loki()`, `with_postgres()`, `with_webhook()`
  - Filters: `with_level_filter()`, `with_sampling()`, `with_adaptive_sampling()`, `with_trace_sampling()`, `with_rate_limit()`, `with_error_deduplication()`
  - Processors: `with_size_guard()`
  - Advanced: `with_context()`, `with_enricher()`, `with_redactor()`, `with_field_mask()`, `with_regex_mask()`, `with_url_credentials_redactor()`, `with_debug()`
- Builder API parity enforcement via CI to prevent configuration drift (Story 10.27).

### Documentation

- Comprehensive builder API documentation with examples for all methods (Story 10.28).
- Logger caching documentation explaining lifecycle and cache management.

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
