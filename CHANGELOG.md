# Changelog

All notable changes to this project will be documented in this file. This changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.16.0] - 2026-02-17

### Added

- **Core - Unify logging pipeline to always use dedicated thread:** Eliminate bound mode — `start()` always spawns a dedicated background thread with its own event loop, preventing logging from competing with the caller's HTTP event loop.
- **Core - Add per-actuator adaptive toggles:** Add `filter_tightening`, `worker_scaling`, `queue_growth` fields to `AdaptiveSettings`. Gate filter ladder, WorkerPool, and capacity growth on respective toggles. Expose new params in `with_adaptive()` builder API.
- **Core - Add DualQueue for isolated protected-event handling:** Replace `PriorityAwareQueue` with `DualQueue` in logger construction. Dedicated bounded queue for protected-level events (ERROR, CRITICAL, etc.). Workers drain protected queue first on each iteration and shutdown.

### Changed

- **Core - Consolidate presets from 9 to 6 with benchmark-corrected defaults:** Remove `fastapi`, `production-latency`, `high-volume` presets. Update adaptive preset with benchmark-corrected values (`batch_max_size=256`, `max_workers=4`, `max_queue_growth=3.0`, `protected_levels=[ERROR, CRITICAL]`). Update production preset (`batch_max_size=256`, `shutdown_timeout_seconds=25.0`).

### Fixed

- **Core - Wire DualQueue drop metrics and depth gauges:** Wire protected/unprotected drop counters to MetricsCollector on enqueue failure. Add `depth_gauge_setter` callback to PressureMonitor for per-tick queue depth sampling.
- **Core - Address code review P1/P2 issues:** Strengthen test assertions, remove dead code (`_backpressure_wait_ms`, write-only `_loop_thread_ident`), lock-protect `PriorityAwareQueue.capacity` for thread safety.
- **Core - Scale queue growth table from max_queue_growth setting:** Compute growth multipliers proportionally instead of hardcoding. CRITICAL now reaches full `max_queue_growth` (4.0x default, was 2.0x).

### Documentation

- **Align documentation with unified dedicated-thread architecture:** Rewrite async-sync-boundary.md, update reliability-defaults.md, backpressure docs, and non-blocking-async-logging cookbook.
- **Add per-actuator toggle guidance to cookbook, config map, and builder guide.**
- **Replace audit callout with benchmarks link in README.**

## [0.15.0] - 2026-02-13

### Added

- **Core - Add priority-aware queue with protected levels:** Add PriorityAwareQueue with O(1) tombstone-based eviction. Protected levels (ERROR, CRITICAL, FATAL) survive queue pressure. Add with_protected_levels() builder method and priority eviction metrics.
- **Core - Add AUDIT and SECURITY log levels:** Add AUDIT (60) and SECURITY (70) as standard levels above CRITICAL. Add logger.audit() and logger.security() methods to both facades. Include in default protected_levels.
- **Core - Add sensitive container with auto-redaction at envelope time:** Handle sensitive= and pii= kwargs in build_envelope(), merging into data.sensitive with all values recursively masked before enqueue.
- **Core - Add unsafe_debug escape hatch for raw diagnostic logging:** Add unsafe_debug() to SyncLoggerFacade and AsyncLoggerFacade. Use _UNSAFE_SENTINEL to prevent user kwargs from bypassing redaction. Skip redaction pipeline for tagged events.
- **Core - Always emit correlation_id in envelope for stable schema:** Include correlation_id: null when no correlation context is active. Update JSON schema type from "string" to ["string", "null"].
- **Core - Add Literal type hints for preset name parameters:** Define PresetName and RedactionPresetName type aliases for IDE autocomplete. Add sync-check tests to prevent Literal/registry drift.
- **Core - Add pressure monitor and escalation state machine:** Implement PressureLevel enum and EscalationStateMachine with hysteresis. Add PressureMonitor asyncio task with callbacks, diagnostics, and metrics. Wire monitor lifecycle into logger start/drain with fail-open design.
- **Core - Add adaptive filter tightening on pressure escalation:** Pre-build filter tuples per pressure level at logger startup. Swap filter snapshot via lock-free callback on pressure change.
- **Core - Add dynamic worker scaling on pressure escalation:** Implement WorkerPool with scale_to() and per-worker stop flags. Register scaling callback with PressureMonitor.
- **Core - Wire adaptive batch sizing into worker loop:** Accept AdaptiveController in LoggerWorker. Record per-item flush latency and adjust batch size after each flush.
- **Core - Wire adaptive queue capacity growth on pressure escalation:** Add grow_capacity() to PriorityAwareQueue with grow-only semantics. Emit diagnostic on capacity growth events.
- **Core - Add circuit breaker fallback sink routing:** Route events to configured fallback sink when circuit breaker opens. Add fallback_sink to SinkCircuitBreakerConfig, Prometheus metric, and builder API.
- **Core - Add circuit breaker state as adaptive pressure signal:** Feed circuit breaker open/close events into PressureMonitor. Each open circuit boosts effective fill ratio by configurable amount.
- **Core - Add adaptive preset and builder API:** Add "adaptive" preset with production base, adaptive features, circuit breaker, and rotating file fallback. Add LoggerBuilder.with_adaptive() for fine-grained configuration.
- **Core - Add AdaptiveDrainSummary to DrainResult:** Surface adaptive pipeline metrics via DrainResult.adaptive field. Track escalation/de-escalation counts, time-at-level, peak pressure, and actuator counters.
- **Core - Add concurrent sink writes within batch flush:** Split _flush_batch into prepare phase and concurrent write phase bounded by asyncio.Semaphore. Add sink_concurrency setting and with_sink_concurrency() builder method.
- **Core - Cache component getter snapshots for worker access:** Add tuple snapshots for filters, enrichers, redactors, processors. Invalidate caches on enable/disable enricher and cleanup.
- **Redactors - Add field_blocker redactor for high-risk field names:** Strip dangerous field names (body, payload, raw, etc.) anywhere in event tree. Emit policy_violation diagnostic when blocked fields are encountered.
- **Redactors - Add redaction operational metrics counters:** Add fapilog_redacted_fields_total, fapilog_policy_violations_total, fapilog_sensitive_fields_total counters to MetricsCollector.
- **Redactors - Honor core guardrails in UrlCredentialsRedactor:** Add core_max_depth and core_max_keys_scanned params with "more restrictive wins" logic.
- **Redactors - Add per-field string truncation redactor:** Truncate string values exceeding configurable max_string_length with [truncated] marker. Wire into builder via with_redaction(max_string_length=4096).

### Changed

- **Redactors - Reduce allocations in field blocker traversal:** Replace per-key list path building with lazy string paths. Cache instance attributes as locals for tight loop.
- **Core - Inline sensitive masking to reduce hot-path overhead:** Inline the dict comprehension directly in build_envelope() to eliminate function-call overhead.
- **Redactors - Skip urlsplit for non-URL strings:** Add URL scheme prefix check to avoid parsing plain text.
- **Sinks - Replace hardcoded field extraction with schema-aware resolution:** Add _FIELD_LOCATIONS map for v1.1 envelope field lookup paths. Fix event_payload missing nested fields when include_raw_json=False.

### Fixed

- **Core - Skip error dedup for protected-level events:** Protected_levels promises events MUST NOT be dropped, but error dedup silently suppresses duplicates. Skip the dedup check when the event's level is in protected_levels.
- **Core - Disable batch_sizing by default in adaptive preset:** Adaptive batch sizing only benefits batch-aware sinks — not stdout or file sinks. Change adaptive preset default to batch_sizing=False.
- **Sinks - Extract correlation_id from context in Postgres sink:** Read correlation_id from entry["context"] per v1.1 schema. Add contract test using build_envelope() to prevent schema drift.
- **Core - Wire record_sensitive_fields() into envelope builder:** Call MetricsCollector.record_sensitive_fields() after build_envelope() when sensitive=/pii= containers produce masked fields.
- **Redactors - Deep-copy events in redact_in_order for snapshot integrity:** Replace shallow dict() copy with orjson roundtrip deep copy. Prevent failing redactors from corrupting last good snapshot.
- **Redactors - Align block_on_unredactable default across config layers:** Change RedactorFieldMaskSettings default from False to True to match FieldMaskConfig.
- **Redactors - Align FieldMaskRedactor.redact() return type with protocol:** Return original event dict instead of None when drop guardrail fires.
- **Core - Wrap metrics calls in try/except for resilience:** Ensure metrics failures don't affect enqueue success.

### Documentation

- **Docs - Add AdaptiveDrainSummary to API reference and guides:** Document AdaptiveDrainSummary fields in lifecycle-results.md. Add adaptive summary example to graceful-shutdown-flush.md.
- **Docs - Add adaptive pipeline and circuit breaker documentation:** Add adaptive preset to presets guide. Create user guides for adaptive-pipeline.md and circuit-breaker.md. Add glossary terms and performance tuning sections.
- **Redactors - Document field_blocker, string_truncate, unsafe_debug, and redaction metrics:** Add all 5 built-in redactors with config tables, examples, and builder shortcuts. Document redaction operational metrics with PromQL examples.
- **Docs - Update documentation for AUDIT and SECURITY levels:** Update custom-log-levels cookbook. Change custom level examples from AUDIT to VERBOSE/NOTICE.
- **Docs - Add priority queue metrics and tuning documentation:** Add Prometheus metrics reference table. Document priority queue metrics with alerting rules.
- **Docs - Improve configuration and FastAPI documentation:** Add configuration hierarchy section. Update FastAPI preset example to use FastAPIBuilder pattern.

## [0.14.0] - 2026-02-02

### Added

- **FastAPI - Add FastAPIBuilder for unified integration:** Extend AsyncLoggerBuilder with FastAPI-specific methods. Add skip_paths, include_headers, sample_rate, log_errors_on_skip. Support env var overrides with warning emission. Deprecate setup_logging() in favor of FastAPIBuilder.

### Documentation

- **FastAPI - Update documentation for FastAPIBuilder:** Update user guide with FastAPIBuilder as recommended approach. Create migration guide from setup_logging() to FastAPIBuilder. Update cookbook entries to use FastAPIBuilder pattern. Mark deprecated sections in documentation.
- **FastAPI - Update all documentation to use FastAPIBuilder:** Update all cookbook entries to use FastAPIBuilder instead of setup_logging(). Update user guide pages (configuration, execution-modes, presets). Update integrations/fastapi.md and examples/fastapi-logging.md. Update why-fapilog.md, features.md, context-binding.md.
- **Docs - Move migration guide to guides directory:** Move fastapi-builder.md to guides/fastapi-builder-migration.md. Add orphan directive to suppress toctree warning. Update links in user-guide/fastapi.md and user-guide/index.md.

## [0.13.0] - 2026-02-01

### Added

- **FastAPI - Expose header options in setup_logging:** Add include_headers, additional_redact_headers, allow_headers params. Pass header options through to _configure_middleware and LoggingMiddleware.
- **Core - Add high-volume preset with adaptive sampling:** Enable cost-effective logging for high-traffic services via preset="high-volume". Configure adaptive sampling to target ~100 events/sec with 1-100% dynamic range. Ensure ERROR/CRITICAL/FATAL always pass through (never sampled out).
- **Core - Add log origin tracking:** Add LogOrigin type and origin field to LogDiagnostics TypedDict. Set origin="native" by default in build_envelope(). Stdlib bridge sets origin="stdlib" via _origin parameter.
- **Core - Add async context propagation helpers:** Add create_task_with_context() for context-preserving task creation. Add run_in_executor_with_context() for executor context preservation. Fix preserve_context decorator bug.
- **Core - Add custom log level registration API:** Add register_level() to register custom levels with priority 0-99. Integrate custom levels with level filter and routing. Generate dynamic logger methods for levels with add_method=True.
- **Core - Add custom sink names to builder API:** Add optional name parameter to all add_* sink methods. Enable multiple sinks of same type with unique names for routing.

### Fixed

- **FastAPI - Preserve default header redactions in setup_logging:** Pass redact_headers=None instead of [] to LoggingMiddleware. Allows DEFAULT_REDACT_HEADERS to apply when include_headers=True.

### Documentation

- **Cookbook - Add FastAPI microservice production guide:** Cover preset selection for different traffic patterns. Include Kubernetes probe skip paths. Document serverless containers (Cloud Run, Fargate, Lambda).
- **Features - Add features page with comprehensive feature list:** Add features.md with categorized feature tables and benefits.
- **Cookbook - Add custom log levels recipe:** Cover TRACE, AUDIT, NOTICE level patterns for Python logging.
- **Guides - Add async context propagation guide:** Document create_task_with_context, run_in_executor_with_context, and preserve_context decorator usage.
- **Core - Add register_level API documentation:** Add comprehensive register_level() docs to top-level-functions.md with integration tests.

## [0.12.0] - 2026-01-30

### Added

- **Core - Add message_id field:** message_id uniquely identifies each log entry (always present). correlation_id now only appears when set via context variable, clarifying semantics: message_id per-entry vs correlation_id per-request.
- **Core - Add critical() log level method:** Add critical() method to SyncLoggerFacade and AsyncLoggerFacade. Update stdlib bridge to call critical() directly instead of error() with extras.

### Fixed

- **Core - Resolve race condition in cross-thread dropped counter:** Move dropped counting into _async_enqueue so it executes even when caller times out. Remove duplicate counting from sync and async callers. Ensures accurate accounting when fut.result() times out but coroutine completes.
- **Docs - Add presets.md to toctree:** Add presets.md to docs/user-guide/index.md toctree. Update test_all_presets_documented to include production-latency.

### Documentation

- **Security - Update supported versions:** Remove marketing tagline (not appropriate for security policy). Update version table to reflect current releases.
- **Security - Add tagline for brand consistency.**
- **Readme - Remove redundant title heading:** Logo already provides branding, no need for duplicate heading.
- **Readme - Align messaging with fapilog.dev website:** Update tagline to "Your sinks can be slow. Your app shouldn't be." Align "Why fapilog?" section with website value propositions. Replace ASCII architecture diagram with website image.
- **Stdlib-bridge - Fix CRITICAL level mapping:** Level mapping table incorrectly stated CRITICAL uses error() with critical=True. Implementation actually uses critical() method directly.
- **Redactors - Add prominent PII f-string warning:** Add warning callout to main redaction guide explaining message strings bypass redaction. Add same warning to API reference. Expand troubleshooting guide with comprehensive unsafe/safe code examples.

## [0.11.0] - 2026-01-30

### Added

- **Core - Add configuration validation:** Validate configuration with hard limits (reject invalid) and soft limits (warn on high values) for queue_capacity, batch_max_size, batch_timeout_seconds, and num_workers.

### Documentation

- **Core - Add execution modes guide:** Document execution modes (async, bound loop, thread) with throughput expectations and usage patterns in README and new user guide. Update troubleshooting docs with worker_count tuning guidance.
- **Docs - Fix broken cross-reference links:** Remove link to async-sync-boundary.md and replace anchor link with plain text reference for validation limits.

## [0.10.2] - 2026-01-30

### Fixed

- **Core - Wait for all workers to complete during drain:** Fix race condition where drain returned before all workers finished. Workers sharing single drained_event caused first-to-finish to win. Use asyncio.gather() to wait for all worker tasks instead.

## [0.10.1] - 2026-01-29

### Fixed

- **Core - Merge builder sinks with preset sinks instead of replacing:** Fix bug where `with_preset('production').add_file()` caused messages to be submitted but never processed (processed=0). Merge sink names preserving preset sinks (e.g., stdout_json). Deep-merge sink configs to preserve preset defaults.
- **Tests - Use CI timeout multiplier for backpressure timing test:** Apply `get_test_timeout()` to scale timing threshold for CI environments. Prevents flaky failures from 1% timing variance.

## [0.10.0] - 2026-01-29

### Added

- **Core - Default production presets to worker_count=2:** Add worker_count: 2 to production, fastapi, serverless, hardened presets. Provides ~30x throughput improvement (3,500 → 105,000 events/sec). Keep dev/minimal presets at 1 worker for simpler debugging.

### Fixed

- **Core - Align filter builder config keys with plugin fields:** Fix with_adaptive_sampling() to use min_sample_rate, max_sample_rate, target_eps. Fix with_trace_sampling() to use sample_rate, remove honor_upstream. Add contract tests verifying builder configs load via _build_pipeline.
- **Core - Rename max_entries to max_keys in with_first_occurrence():** Fix parameter name mismatch causing silent filter loading failure. Add max_entries as deprecated alias with DeprecationWarning.
- **Core - Enable serialize_in_flush for size_guard processor:** with_size_guard() now sets serialize_in_flush=True automatically. Respects explicit user setting if already configured.

### Documentation

- **Docs - Use correct logo green and make logo clickable:** Update badge color from #84CC16 to #9FE17B to match logo. Wrap logo image in link to fapilog.dev.

## [0.9.0] - 2026-01-29

### Added

- **Core - Add reuse() method to LoggerBuilder:** Expose reuse parameter for controlling logger caching behavior. Pass reuse through build() and build_async() to underlying functions. Enable test isolation by allowing non-cached logger instances.

### Changed

- **Core - Use Self return type for LoggerBuilder methods:** Change 44 builder methods from -> LoggerBuilder to -> Self. Enable correct type inference for AsyncLoggerBuilder chaining.

### Fixed

- **Core - Flatten data={} kwarg in envelope building:** When logging with `data={...}` (e.g., `logger.info("msg", data={"password": "secret"})`), the dict contents are now flattened into the envelope's `data` section instead of being nested under `data.data`. This fixes a security footgun where redaction rules for fields like `password` would fail silently because the actual path was `data.data.password`. Explicit kwargs override `data` dict values on collision. Non-dict `data` values are preserved as nested.
- **Core - Fix flaky thread mode drain counter test:** Track batch counters locally to prevent race condition. Accumulate processed/dropped counts within batch before updating shared counters. Only count unprocessed events as dropped when sink fails mid-batch.

### Documentation

- **Fapilog - Document field routing in with_context() docstring:** The `with_context()` builder method docstring now explains that known context fields (`request_id`, `user_id`, `tenant_id`, `trace_id`, `span_id`) are routed to `log.context` while custom fields go to `log.data`.

## [0.8.1] - 2026-01-29

### Added

- **Stdout sink capture mode for testing:** `StdoutJsonSink` now accepts a `capture_mode=True` parameter that disables `os.writev()` optimization, allowing output to be captured via `sys.stdout` replacement in tests. The builder API also supports this: `add_stdout(capture_mode=True)`. See `docs/guides/testing.md` for usage patterns.
- **Duration parser supports milliseconds and decimals:** The duration string parser now accepts `ms` suffix for milliseconds (e.g., `"100ms"`) and decimal values with any unit (e.g., `"0.5s"`, `"1.5h"`). Error messages now list all valid formats. Builder methods like `with_circuit_breaker(recovery_timeout="500ms")` benefit automatically.
- **Doc-accuracy CI check for redaction_fail_mode:** The `scripts/check_doc_accuracy.py` script now validates that `docs/redaction/behavior.md` accurately documents the `redaction_fail_mode` default value from `CoreSettings`. This prevents documentation drift for security-sensitive settings.

### Fixed

- **Logger resource cleanup on drain:** Internal data structures (`_error_dedupe`, `_plugin_stats`, `_worker_tasks`, plugin lists) are now cleared after `stop_and_drain()` completes. This prevents memory leaks in long-running applications that create and destroy loggers.

## [0.8.0] - 2026-01-28

### Breaking Changes

- **Redaction defaults changed to fail-closed:** All redaction settings now default to fail-closed behavior to prevent PII leakage:
  - `on_guardrail_exceeded`: `"warn"` → `"replace_subtree"` (masks unscanned subtrees instead of passing through)
  - `block_on_unredactable`: `False` → `True` (drops events when configured fields can't be redacted)
  - `redaction_fail_mode`: `"open"` → `"warn"` (emits diagnostic on redaction exceptions)

  **Migration guide:** To restore previous fail-open behavior for debugging:
  ```python
  from fapilog import Settings
  from fapilog.core.settings import CoreSettings
  from fapilog.core.config import RedactorConfig
  from fapilog.plugins.redactors.field_mask import FieldMaskConfig

  Settings(
      core=CoreSettings(redaction_fail_mode="open"),
      redactor_config=RedactorConfig(
          field_mask=FieldMaskConfig(
              block_on_unredactable=False,
              on_guardrail_exceeded="warn",
          )
      )
  )
  ```

### Changed

- **Production preset disables Postgres auto-DDL:** The `production` preset now sets `create_table=False` for Postgres sink configuration, requiring explicit table provisioning via migrations. This prevents unexpected DDL execution in regulated environments.
- **Worker event-based wakeup:** The background worker loop now uses `asyncio.Event` signaling instead of fixed 1ms polling when an enqueue event is provided, reducing CPU wakeups when the queue is empty.
- **Backpressure event-based signaling:** `NonBlockingRingQueue.await_enqueue()` and `await_dequeue()` now use `asyncio.Event` signaling instead of spin-wait loops, reducing CPU usage under sustained backpressure. The `yield_every` parameter has been removed.
- **Doc accuracy CI now fails on missing critical files:** The `scripts/check_doc_accuracy.py` script now fails when required documentation files are missing, instead of silently skipping them. This prevents security-sensitive documentation from drifting without CI catching it.

### Added

- **FastAPI middleware `require_logger` parameter:** `LoggingMiddleware` now accepts `require_logger=True` to fail fast with a clear error if no logger is in `app.state`. This avoids latency spikes from lazy logger creation on cold-start requests. Default is `False` for backward compatibility.
- **Fallback sink raw output hardening:** When JSON parsing fails for serialized payloads on the fallback path, fapilog now applies keyword scrubbing to mask common secret patterns (`password=`, `token=`, `api_key=`, `authorization:`) before writing to stderr. Optional truncation via `core.fallback_raw_max_bytes` limits output size. Scrubbing is enabled by default; set `FAPILOG_CORE__FALLBACK_SCRUB_RAW=false` to disable for debugging.

### Fixed

- **Core redaction guardrails now functional:** The `redaction_max_depth` and `redaction_max_keys_scanned` settings in `CoreSettings` were previously defined but never applied (dead code). They are now passed to `FieldMaskRedactor` and `RegexMaskRedactor` during initialization and act as outer limits that override per-redactor settings when more restrictive.
- **Silent data loss in `write_serialized`:** Fixed correctness issue where HTTP, Webhook, Loki, CloudWatch, and PostgreSQL sinks silently replaced log data with placeholder values (e.g., `{"message": "fallback"}`) when deserialization failed. All sinks now raise `SinkWriteError` with diagnostics, enabling proper fallback and circuit breaker handling.
- **Plugin metadata version default:** Changed `create_plugin_metadata()` default `min_fapilog_version` from `"3.0.0"` to `"0.1.0"`. The previous default was incorrect for a 0.x project and caused compatibility check failures for plugin authors.

### Documentation

- **Backpressure API documentation accuracy:** Fixed incorrect examples showing non-existent `policy="wait"` parameter and `discard_oldest` policy. Documentation now correctly shows actual `with_backpressure(wait_ms=..., drop_on_full=...)` API with behavior table explaining parameter combinations.
- **Architecture documentation accuracy:** Removed stale references to non-existent components (`ComplianceEngine`, `UniversalSettings`, `EventCategory`) and deleted outdated monolithic `docs/architecture.md`.
- **Production checklist documentation:** Added consolidated pre-deployment checklist covering preset selection, metrics, diagnostics, redaction validation, backpressure tuning, and graceful shutdown.
- **stdlib bridge documentation:** Added user guide for `enable_stdlib_bridge()` with API reference, common use cases, Django/Celery integration examples, level mapping, and troubleshooting.
- **Redaction guardrails documentation:** Documented two-level guardrail system (core pipeline vs per-redactor), precedence rules ("more restrictive wins"), and added CI validation for per-redactor defaults.
- **Unified sampling documentation:** Restructured sampling docs to emphasize filter-based approach as recommended, added deprecation section for `observability.logging.sampling_rate`, migration guide, strategy comparison table, and environment variable configuration.

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

- **Unified `with_redaction()` API:** Single method for all redaction configuration with preset support, URL credentials, guardrails, and custom fields/patterns.
- **Preset discovery methods:** `LoggerBuilder.list_redaction_presets()` and `LoggerBuilder.get_redaction_preset_info(name)` for discovering available redaction presets.
- **Multiple preset support:** `with_redaction(preset=["GDPR_PII", "PCI_DSS"])` applies multiple presets in one call.
- **Composable redaction presets:** One-liner compliance protection via `with_redaction(preset="GDPR_PII")`. Includes presets for GDPR, CCPA, HIPAA, PCI-DSS, and CREDENTIALS with inheritance support and metadata filtering.

### Changed

- **`with_redaction()` is now additive by default:** Calling `with_redaction()` multiple times merges fields/patterns instead of replacing. Use `replace=True` to restore the previous overwrite behavior.

### Documentation

- New dedicated `/redaction/` documentation section with presets reference, configuration guide, behavior documentation, and testing guide.
- Added compliance redaction cookbook explaining what field-name matching covers and its limitations.
- Updated enterprise documentation with compliance preset examples and cross-references.
- Improved documentation navigation structure and fixed toctree cross-references.
- Added configuration approach decision guide with comparison matrix (preset vs builder vs settings).

## [0.6.0] - 2026-01-26

### Added

- **Graceful log drain on shutdown:** Loggers now automatically flush pending logs during application shutdown via `atexit` handlers. This ensures logs are not lost when processes terminate.
- **Regex ReDoS protection:** `RegexMaskRedactor` now validates patterns at config time to prevent catastrophic backtracking. Patterns with nested quantifiers, overlapping alternation, or wildcards in bounded repetition are rejected. Use `allow_unsafe_patterns=True` to bypass validation if needed.

### Changed

- **Secure header redaction by default:** `LoggingMiddleware` now redacts sensitive headers (Authorization, Cookie, X-API-Key, etc.) by default when `include_headers=True`. This prevents accidental credential leakage in logs.
  - Use `additional_redact_headers` to add custom headers to the default list
  - Use `allow_headers` for allowlist mode (only log specified headers)
  - Use `disable_default_redactions=True` to opt out (emits warning)

### Documentation

- Added Django structured logging cookbook entry.
- Added library comparison pages (why-fapilog, alternative library comparisons).
- Added security audit findings as stories for tracking.

## [0.5.1] - 2026-01-21

### Added

- **FastAPI `log_errors_on_skip` parameter:** `LoggingMiddleware` and `setup_logging()` now accept `log_errors_on_skip` (default: True) to log unhandled exceptions on skipped paths. This ensures visibility into crashes on health endpoints while still skipping routine success logs.

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

- **Logger instance caching enabled by default:** `get_logger()` and `get_async_logger()` now cache instances by name, matching stdlib `logging.getLogger()` behavior. This prevents resource exhaustion from unbounded logger creation.

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

- Logger instance caching: `get_logger()` and `get_async_logger()` now cache instances by name (like stdlib `logging.getLogger()`), preventing resource exhaustion from unbounded logger creation.
- `reuse` parameter for `get_logger()` and `get_async_logger()` to opt out of caching when needed (e.g., tests).
- `get_cached_loggers()` function to inspect cached logger names and types.
- `clear_logger_cache()` async function to drain and clear all cached loggers.
- `ResourceWarning` emitted when loggers are garbage collected without being drained.
- `serverless` preset for AWS Lambda, Google Cloud Run, and Azure Functions: stdout-only output, `drop_on_full=True`, smaller batch size (25), production-grade redaction.
- **Builder API parity with Settings:**
  - Core settings: `with_level()`, `with_name()`, `with_queue_size()`, `with_workers()`, `with_drop_on_full()`, `with_strict_mode()`, `with_diagnostics()`
  - Cloud sinks: `with_cloudwatch()`, `with_loki()`, `with_postgres()`, `with_webhook()`
  - Filters: `with_level_filter()`, `with_sampling()`, `with_adaptive_sampling()`, `with_trace_sampling()`, `with_rate_limit()`, `with_error_deduplication()`
  - Processors: `with_size_guard()`
  - Advanced: `with_context()`, `with_enricher()`, `with_redactor()`, `with_field_mask()`, `with_regex_mask()`, `with_url_credentials_redactor()`, `with_debug()`
- Builder API parity enforcement via CI to prevent configuration drift.

### Documentation

- Comprehensive builder API documentation with examples for all methods.
- Logger caching documentation explaining lifecycle and cache management.

## [0.4.0] - 2026-01-19

### Breaking Changes

- `fastapi` preset now enables redaction by default (`field_mask`, `regex_mask`, `url_credentials`), matching `production` preset security posture. Use `dev` preset for debugging or explicitly set `redactors=[]` to disable.
- Log schema v1.1 with semantic field groupings (`context`, `diagnostics`, `data`); `metadata` renamed to `data`, `correlation_id` moved to `context.correlation_id`, timestamp now RFC3339 string. See `docs/schema-migration-v1.0-to-v1.1.md`.
- Enrichers now return nested dicts targeting semantic groups (`{"diagnostics": {...}}`) instead of flat dicts; `enrich_parallel()` uses deep-merge; `LogEvent` model updated to v1.1 schema with `context`, `diagnostics`, `data` fields replacing `metadata`, `correlation_id`, `component`.
- Production preset now includes `regex_mask` redactor for broader secret protection; users may see additional fields masked.
- External plugins now blocked by default; use `plugins.allow_external=true` or `plugins.allowlist` for explicit opt-in.

### Added

- Fluent builder API (`LoggerBuilder`, `AsyncLoggerBuilder`) for chainable logger configuration with IDE autocomplete support.
- Pretty console output (`stdout_pretty`) and `format` selection for stdout logging.
- One-liner FastAPI setup helpers (`setup_logging`, `get_request_logger`) with lifespan support.
- Default log-level selection based on TTY/CI when no preset or explicit log level is set.
- Stderr fallback for sink write failures with optional diagnostics warnings.
- `SinkWriteError` for sinks to signal write failures to the core pipeline; core now catches these errors (and `False` returns) to trigger fallback and circuit breaker behavior.
- CI smoke test for benchmark script to catch future regressions.
- CI timeout multiplier (`CI_TIMEOUT_MULTIPLIER`) with `get_test_timeout()` helper for timing-sensitive tests on slow CI runners.
- `SECURITY.md` with vulnerability reporting guidance.
- `CODE_OF_CONDUCT.md` (Contributor Covenant).
- Production tip callout in README for `preset="production"` guidance.

### Changed

- Serialization path cleanup - `serialize_envelope()` now trusts upstream v1.1 schema compliance and only fails for non-JSON-serializable objects; exception-driven fallback is now truly exceptional, not the normal path; `strict_envelope_mode` now works correctly.
- Internal diagnostics now write to stderr by default (Unix convention); add `core.diagnostics_output="stdout"` for backward compatibility.
- Updated built-in sinks (`stdout_json`, `stdout_pretty`, `rotating_file`, `audit`) to raise `SinkWriteError` instead of swallowing errors, enabling proper fallback handling.
- Updated `BaseSink` protocol documentation to reflect the new error signaling contract.
- Aligned ruff, black, and mypy target versions with `requires-python = ">=3.10"`; added pre-commit hook to enforce Python 3.10+.
- Standardized Hypothesis property test settings: removed per-test `max_examples` overrides so all tests respect `HYPOTHESIS_MAX_EXAMPLES` env var.
- Split large test files into focused modules: `test_error_handling.py` → 4 files, `test_high_performance_lru_cache.py` → 3 files, `test_logger_pipeline.py` → 3 files, `test_rotating_file_sink.py` → 3 files (total test count preserved at 1704).

### Fixed

- Benchmark script key alignment in `derive_verdicts()` to match actual output keys from `benchmark()`.
- Strict mode serialization drops now correctly increment the `dropped` counter and record metrics; previously these drops were silently unaccounted.
- Extras documentation accuracy: removed non-existent extras (enterprise, loki, cloud, siem), documented all real extras with descriptions.
- Python version badge in README (3.8+ → 3.10+).
- Plugin group documentation in architecture docs.
- `CONTRIBUTING.md` with correct Python version, repo name, and governance file references.

### Security

- WebhookSink now supports HMAC-SHA256 signatures (`signature_mode="hmac"`) instead of sending secrets in headers; legacy header mode emits deprecation warning.
- Bumped orjson minimum version to 3.9.15 (CVE-2024-27454 fix).
- Fallback minimal redaction now recurses into lists, preventing secrets in arrays from leaking to stderr during sink failures.

### Performance

- Cache sampling rate, filter config, and error dedupe window at logger initialization to avoid `Settings()` instantiation on every log call.

### Documentation

- Added performance benchmarks page with methodology, results, and reproduction instructions.
- Added `redaction-guarantee.md` documenting exact redaction behavior per preset; fixed inaccurate claims in `reliability-defaults.md`.
- Documented same-thread backpressure behavior where `drop_on_full=False` cannot be honored; enhanced diagnostic warning with `drop_on_full_setting` field.
- Added automated changelog generation with git-cliff and conventional commit linting via pre-commit hooks; release workflow now validates changelog entries match tagged version.
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

- Enterprise key management for tamper-evident plugin.
- Verification API and CLI for tamper-evident plugin.
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
