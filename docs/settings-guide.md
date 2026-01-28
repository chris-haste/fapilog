<!-- AUTO-GENERATED: do not edit by hand. Run scripts/generate_env_matrix.py -->
# Settings Reference

This guide documents Settings groups and fields.

## core

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `core.app_name` | str | fapilog | Logical application name |
| `core.log_level` | Literal | INFO | Default log level |
| `core.max_queue_size` | int | 10000 | Maximum in-memory queue size for async processing |
| `core.batch_max_size` | int | 256 | Maximum number of events per batch before a flush is triggered |
| `core.batch_timeout_seconds` | float | 0.25 | Maximum time to wait before flushing a partial batch |
| `core.backpressure_wait_ms` | int | 50 | Milliseconds to wait for queue space before dropping |
| `core.drop_on_full` | bool | True | If True, drop events after backpressure_wait_ms elapses when queue is full |
| `core.enable_metrics` | bool | False | Enable Prometheus-compatible metrics |
| `core.context_binding_enabled` | bool | True | Enable per-task bound context via logger.bind/unbind/clear |
| `core.default_bound_context` | dict | PydanticUndefined | Default bound context applied at logger creation when enabled |
| `core.internal_logging_enabled` | bool | False | Emit DEBUG/WARN diagnostics for internal errors |
| `core.diagnostics_output` | Literal | stderr | Output stream for internal diagnostics: stderr (default, Unix convention) or stdout (backward compat) |
| `core.error_dedupe_window_seconds` | float | 5.0 | Seconds to suppress duplicate ERROR logs with the same message; 0 disables deduplication |
| `core.shutdown_timeout_seconds` | float | 3.0 | Maximum time to flush on shutdown signals |
| `core.worker_count` | int | 1 | Number of worker tasks for flush processing |
| `core.sensitive_fields_policy` | list | PydanticUndefined | Optional list of dotted paths for sensitive fields policy; warning if no redactors configured |
| `core.enable_redactors` | bool | True | Enable redactors stage between enrichers and sink emission |
| `core.redactors_order` | list | PydanticUndefined | Ordered list of redactor plugin names to apply |
| `core.sinks` | list | PydanticUndefined | Sink plugins to use (by name); falls back to env-based default when empty |
| `core.enrichers` | list | PydanticUndefined | Enricher plugins to use (by name) |
| `core.redactors` | list | PydanticUndefined | Redactor plugins to use (by name); defaults to ['url_credentials'] for secure defaults; set to [] to disable all redaction |
| `core.processors` | list | PydanticUndefined | Processor plugins to use (by name) |
| `core.filters` | list | PydanticUndefined | Filter plugins to apply before enrichment (by name) |
| `core.redaction_max_depth` | int | None | 6 | Optional max depth guardrail for nested redaction |
| `core.redaction_max_keys_scanned` | int | None | 5000 | Optional max keys scanned guardrail for redaction |
| `core.exceptions_enabled` | bool | True | Enable structured exception serialization for log calls |
| `core.exceptions_max_frames` | int | 10 | Maximum number of stack frames to capture for exceptions |
| `core.exceptions_max_stack_chars` | int | 20000 | Maximum total characters for serialized stack string |
| `core.strict_envelope_mode` | bool | False | If True, drop emission when envelope cannot be produced; otherwise fallback to best-effort serialization with diagnostics |
| `core.capture_unhandled_enabled` | bool | False | Automatically install unhandled exception hooks (sys/asyncio) |
| `core.serialize_in_flush` | bool | False | If True, pre-serialize envelopes once during flush and pass SerializedView to sinks that support write_serialized |
| `core.resource_pool_max_size` | int | 8 | Default max size for resource pools |
| `core.resource_pool_acquire_timeout_seconds` | float | 2.0 | Default acquire timeout for pools |
| `core.sink_circuit_breaker_enabled` | bool | False | Enable circuit breaker for sink fault isolation |
| `core.sink_circuit_breaker_failure_threshold` | int | 5 | Number of consecutive failures before opening circuit |
| `core.sink_circuit_breaker_recovery_timeout_seconds` | float | 30.0 | Seconds to wait before probing a failed sink |
| `core.sink_parallel_writes` | bool | False | Write to multiple sinks in parallel instead of sequentially |
| `core.fallback_redact_mode` | Literal | minimal | Redaction mode for fallback stderr output: 'inherit' uses pipeline redactors, 'minimal' applies built-in sensitive field masking, 'none' writes unredacted (opt-in to legacy behavior) |
| `core.redaction_fail_mode` | Literal | warn | Behavior when _apply_redactors() catches an unexpected exception: 'open' passes original event, 'closed' drops the event, 'warn' (default) passes event but emits diagnostic warning |
| `core.atexit_drain_enabled` | bool | True | Register atexit handler to drain pending logs on normal process exit |
| `core.atexit_drain_timeout_seconds` | float | 2.0 | Maximum seconds to wait for log drain during atexit handler |
| `core.signal_handler_enabled` | bool | True | Install signal handlers for SIGTERM/SIGINT to enable graceful drain |
| `core.flush_on_critical` | bool | False | Immediately flush ERROR and CRITICAL logs (bypass batching) to reduce log loss on abrupt shutdown |
| `core.emit_drop_summary` | bool | False | Emit summary log events when events are dropped due to backpressure or deduplicated due to error dedupe window |
| `core.drop_summary_window_seconds` | float | 60.0 | Window in seconds for aggregating drop/dedupe summary events. Summaries are emitted at most once per window. |
| `core.fallback_scrub_raw` | bool | True | Apply keyword scrubbing to raw (non-JSON) fallback output; set to False for debugging when raw output is needed |
| `core.fallback_raw_max_bytes` | int | None | — | Optional limit for raw fallback output bytes; payloads exceeding this are truncated with '[truncated]' marker |
| `core.benchmark_file_path` | str | None | — | Optional path used by performance benchmarks |

## security

| Field | Type | Default | Description |
|-------|------|---------|-------------|

### security.encryption

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `security.encryption.enabled` | bool | True | Enable encryption features |
| `security.encryption.algorithm` | Literal | AES-256 | Primary encryption algorithm |
| `security.encryption.key_source` | Optional | — | Source for key material |
| `security.encryption.env_var_name` | str | None | — | Environment variable holding key material |
| `security.encryption.key_file_path` | str | None | — | Filesystem path to key material |
| `security.encryption.key_id` | str | None | — | Key identifier for KMS/Vault sources |
| `security.encryption.rotate_interval_days` | int | 90 | Recommended key rotation interval |
| `security.encryption.min_tls_version` | Literal | 1.2 | Minimum TLS version for transport |

### security.access_control

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `security.access_control.enabled` | bool | True | Enable access control checks across the system |
| `security.access_control.auth_mode` | Literal | token | Authentication mode used by integrations (library-agnostic) |
| `security.access_control.allowed_roles` | list | PydanticUndefined | List of roles granted access to protected operations |
| `security.access_control.require_admin_for_sensitive_ops` | bool | True | Require admin role for sensitive or destructive operations |
| `security.access_control.allow_anonymous_read` | bool | False | Permit read access without authentication (discouraged) |
| `security.access_control.allow_anonymous_write` | bool | False | Permit write access without authentication (never recommended) |

## observability

| Field | Type | Default | Description |
|-------|------|---------|-------------|

### observability.monitoring

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `observability.monitoring.enabled` | bool | False | Enable health/monitoring checks and endpoints |
| `observability.monitoring.endpoint` | str | None | — | Monitoring endpoint URL |

### observability.metrics

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `observability.metrics.enabled` | bool | False | Enable internal metrics collection/export |
| `observability.metrics.exporter` | Literal | prometheus | Metrics exporter to use ('prometheus' or 'none') |
| `observability.metrics.port` | int | 8000 | TCP port for metrics exporter |

### observability.tracing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `observability.tracing.enabled` | bool | False | Enable distributed tracing features |
| `observability.tracing.provider` | Literal | otel | Tracing backend provider ('otel' or 'none') |
| `observability.tracing.sampling_rate` | float | 0.1 | Trace sampling probability in range 0.0–1.0 |

### observability.logging

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `observability.logging.format` | Literal | json | Output format for logs (machine-friendly JSON or text) |
| `observability.logging.include_correlation` | bool | True | Include correlation IDs and trace/span metadata in logs |
| `observability.logging.sampling_rate` | float | 1.0 | DEPRECATED: Use core.filters=['sampling'] with filter_config.sampling instead. Log sampling probability in range 0.0–1.0. |

### observability.alerting

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `observability.alerting.enabled` | bool | False | Enable emitting alerts from the logging pipeline |
| `observability.alerting.min_severity` | Literal | ERROR | Minimum alert severity to emit (filter threshold) |

## plugins

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `plugins.enabled` | bool | True | Enable plugin loading |
| `plugins.allow_external` | bool | False | Allow loading plugins from entry points (security risk) |
| `plugins.allowlist` | list | PydanticUndefined | If non-empty, only these plugin names are allowed |
| `plugins.denylist` | list | PydanticUndefined | Plugin names to block from loading |
| `plugins.validation_mode` | str | disabled | Plugin validation mode: disabled, warn, or strict |
