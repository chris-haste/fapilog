# Builder API Gap Audit

This document catalogs all Settings fields and their coverage by the LoggerBuilder API.

**Legend:**
- ✅ = Covered by builder method
- ❌ = No builder coverage (gap)
- ⚠️ = Partial coverage

## Summary

| Category | Total Fields | Covered | Gaps |
|----------|-------------|---------|------|
| CoreSettings | 37 | 9 | 28 |
| SinkConfig | 8 sink types | 4 | 4 |
| FilterConfig | 6 filter types | 0 | 6 |
| RedactorConfig | 3 redactor types | 2 | 1 |
| ProcessorConfig | 3 fields | 0 | 3 |
| PluginsSettings | 5 fields | 0 | 5 |
| SinkRoutingSettings | 4 fields | 0 | 4 |
| SecuritySettings | 2 sub-groups | 0 | 2 |
| ObservabilitySettings | 5 sub-groups | 0 | 5 |

---

## CoreSettings Fields

| Field | Type | Builder Coverage | Priority |
|-------|------|-----------------|----------|
| `app_name` | str | ❌ | P1 |
| `log_level` | Literal | ✅ `with_level()` | - |
| `max_queue_size` | int | ✅ `with_queue_size()` | - |
| `batch_max_size` | int | ✅ `with_batch_size()` | - |
| `batch_timeout_seconds` | float | ✅ `with_batch_timeout()` | - |
| `backpressure_wait_ms` | int | ❌ | P1 |
| `drop_on_full` | bool | ❌ | P1 |
| `enable_metrics` | bool | ❌ | P2 |
| `context_binding_enabled` | bool | ❌ | P2 |
| `default_bound_context` | dict | ✅ `with_context()` | - |
| `internal_logging_enabled` | bool | ❌ | P2 |
| `diagnostics_output` | Literal | ❌ | P2 |
| `error_dedupe_window_seconds` | float | ❌ | P2 |
| `shutdown_timeout_seconds` | float | ❌ | P1 |
| `worker_count` | int | ❌ | P1 |
| `sensitive_fields_policy` | list[str] | ❌ | P2 |
| `enable_redactors` | bool | ❌ | P2 |
| `redactors_order` | list[str] | ❌ | P2 |
| `sinks` | list[str] | ✅ via `add_*()` methods | - |
| `enrichers` | list[str] | ✅ `with_enrichers()` | - |
| `redactors` | list[str] | ⚠️ `with_redaction()` (partial) | - |
| `processors` | list[str] | ❌ | P1 |
| `filters` | list[str] | ✅ `with_filters()` | - |
| `redaction_max_depth` | int | ❌ | P2 |
| `redaction_max_keys_scanned` | int | ❌ | P2 |
| `exceptions_enabled` | bool | ❌ | P2 |
| `exceptions_max_frames` | int | ❌ | P2 |
| `exceptions_max_stack_chars` | int | ❌ | P2 |
| `strict_envelope_mode` | bool | ❌ | P2 |
| `capture_unhandled_enabled` | bool | ❌ | P2 |
| `serialize_in_flush` | bool | ❌ | P2 |
| `resource_pool_max_size` | int | ❌ | P2 |
| `resource_pool_acquire_timeout_seconds` | float | ❌ | P2 |
| `sink_circuit_breaker_enabled` | bool | ❌ | P1 |
| `sink_circuit_breaker_failure_threshold` | int | ❌ | P1 |
| `sink_circuit_breaker_recovery_timeout_seconds` | float | ❌ | P1 |
| `sink_parallel_writes` | bool | ❌ | P1 |
| `fallback_redact_mode` | Literal | ❌ | P2 |
| `benchmark_file_path` | str | ❌ (excluded - internal) | - |

---

## SinkConfig Coverage

### Covered Sinks

| Sink | Builder Method | Coverage |
|------|---------------|----------|
| `rotating_file` | `add_file()` | ⚠️ Partial (6/8 fields) |
| `stdout_json` | `add_stdout()` | ✅ Full |
| `stdout_pretty` | `add_stdout(format="pretty")` | ✅ Full |
| `http` | `add_http()` | ⚠️ Partial (3/12 fields) |
| `webhook` | `add_webhook()` | ⚠️ Partial (4/10 fields) |

### Uncovered Sinks (P0 - High Priority)

| Sink | Settings Class | Priority |
|------|---------------|----------|
| `cloudwatch` | CloudWatchSinkSettings | P0 |
| `loki` | LokiSinkSettings | P0 |
| `postgres` | PostgresSinkSettings | P0 |
| `sealed` | SealedSinkSettings | P1 |

### RotatingFileSettings - Partial Coverage

| Field | Covered | Builder Param |
|-------|---------|---------------|
| `directory` | ✅ | `directory` |
| `filename_prefix` | ❌ | - |
| `mode` | ❌ | - |
| `max_bytes` | ✅ | `max_bytes` |
| `interval_seconds` | ✅ | `interval` |
| `max_files` | ✅ | `max_files` |
| `max_total_bytes` | ❌ | - |
| `compress_rotated` | ✅ | `compress` |

### HttpSinkSettings - Partial Coverage

| Field | Covered | Builder Param |
|-------|---------|---------------|
| `endpoint` | ✅ | `endpoint` |
| `headers` | ✅ | `headers` |
| `headers_json` | ❌ | - |
| `retry_max_attempts` | ❌ | - |
| `retry_backoff_seconds` | ❌ | - |
| `timeout_seconds` | ✅ | `timeout` |
| `batch_size` | ❌ | - |
| `batch_timeout_seconds` | ❌ | - |
| `batch_format` | ❌ | - |
| `batch_wrapper_key` | ❌ | - |

### WebhookSettings - Partial Coverage

| Field | Covered | Builder Param |
|-------|---------|---------------|
| `endpoint` | ✅ | `endpoint` |
| `secret` | ✅ | `secret` |
| `headers` | ✅ | `headers` |
| `retry_max_attempts` | ❌ | - |
| `retry_backoff_seconds` | ❌ | - |
| `timeout_seconds` | ✅ | `timeout` |
| `batch_size` | ❌ | - |
| `batch_timeout_seconds` | ❌ | - |

### CloudWatchSinkSettings - No Coverage (P0)

| Field | Type | Notes |
|-------|------|-------|
| `log_group_name` | str | Required |
| `log_stream_name` | str | Optional |
| `region` | str | Required for non-default |
| `create_log_group` | bool | |
| `create_log_stream` | bool | |
| `batch_size` | int | |
| `batch_timeout_seconds` | float | |
| `endpoint_url` | str | LocalStack support |
| `max_retries` | int | |
| `retry_base_delay` | float | |
| `circuit_breaker_enabled` | bool | |
| `circuit_breaker_threshold` | int | |

### LokiSinkSettings - No Coverage (P0)

| Field | Type | Notes |
|-------|------|-------|
| `url` | str | Required |
| `tenant_id` | str | Multi-tenant |
| `labels` | dict | Static labels |
| `label_keys` | list[str] | Dynamic labels |
| `batch_size` | int | |
| `batch_timeout_seconds` | float | |
| `timeout_seconds` | float | |
| `max_retries` | int | |
| `retry_base_delay` | float | |
| `auth_username` | str | Basic auth |
| `auth_password` | str | Basic auth |
| `auth_token` | str | Bearer token |
| `circuit_breaker_enabled` | bool | |
| `circuit_breaker_threshold` | int | |

### PostgresSinkSettings - No Coverage (P0)

| Field | Type | Notes |
|-------|------|-------|
| `dsn` | str | Full connection string |
| `host` | str | |
| `port` | int | |
| `database` | str | |
| `user` | str | |
| `password` | str | |
| `table_name` | str | |
| `schema_name` | str | |
| `create_table` | bool | |
| `min_pool_size` | int | |
| `max_pool_size` | int | |
| `pool_acquire_timeout` | float | |
| `batch_size` | int | |
| `batch_timeout_seconds` | float | |
| `max_retries` | int | |
| `retry_base_delay` | float | |
| `circuit_breaker_enabled` | bool | |
| `circuit_breaker_threshold` | int | |
| `use_jsonb` | bool | |
| `include_raw_json` | bool | |
| `extract_fields` | list[str] | |

---

## FilterConfig Coverage (P1)

All filters currently have no builder coverage.

| Filter | Settings Type | Priority |
|--------|--------------|----------|
| `level` | dict | P1 |
| `sampling` | dict | P1 |
| `rate_limit` | dict | P1 |
| `adaptive_sampling` | dict | P2 |
| `trace_sampling` | dict | P2 |
| `first_occurrence` | dict | P2 |

---

## RedactorConfig Coverage

| Redactor | Builder Coverage | Notes |
|----------|-----------------|-------|
| `field_mask` | ✅ `with_redaction(fields=...)` | |
| `regex_mask` | ✅ `with_redaction(patterns=...)` | |
| `url_credentials` | ❌ | P2 - enabled by default |

### RedactorFieldMaskSettings - Partial Coverage

| Field | Covered |
|-------|---------|
| `fields_to_mask` | ✅ |
| `mask_string` | ❌ |
| `block_on_unredactable` | ❌ |
| `max_depth` | ❌ |
| `max_keys_scanned` | ❌ |

### RedactorRegexMaskSettings - Partial Coverage

| Field | Covered |
|-------|---------|
| `patterns` | ✅ |
| `mask_string` | ❌ |
| `block_on_unredactable` | ❌ |
| `max_depth` | ❌ |
| `max_keys_scanned` | ❌ |

---

## ProcessorConfig Coverage (P1)

| Processor | Builder Coverage |
|-----------|-----------------|
| `zero_copy` | ❌ |
| `size_guard` | ❌ |
| `extra` | ❌ |

### SizeGuardSettings - No Coverage

| Field | Type |
|-------|------|
| `max_bytes` | int |
| `action` | Literal["truncate", "drop", "warn"] |
| `preserve_fields` | list[str] |

---

## SinkRoutingSettings - No Coverage (P1)

| Field | Type | Priority |
|-------|------|----------|
| `enabled` | bool | P1 |
| `rules` | list[RoutingRule] | P1 |
| `overlap` | bool | P2 |
| `fallback_sinks` | list[str] | P1 |

---

## PluginsSettings - No Coverage (P2)

| Field | Type |
|-------|------|
| `enabled` | bool |
| `allow_external` | bool |
| `allowlist` | list[str] |
| `denylist` | list[str] |
| `validation_mode` | str |

---

## SecuritySettings - No Coverage (P2)

### EncryptionSettings

| Field | Type |
|-------|------|
| `enabled` | bool |
| `algorithm` | Literal |
| `key_source` | Literal |
| `env_var_name` | str |
| `key_file_path` | str |
| `key_id` | str |
| `rotate_interval_days` | int |
| `min_tls_version` | Literal |

### AccessControlSettings

| Field | Type |
|-------|------|
| `enabled` | bool |
| `auth_mode` | Literal |
| `allowed_roles` | list[str] |
| `require_admin_for_sensitive_ops` | bool |
| `allow_anonymous_read` | bool |
| `allow_anonymous_write` | bool |

---

## ObservabilitySettings - No Coverage (P2)

### MonitoringSettings

| Field | Type |
|-------|------|
| `enabled` | bool |
| `endpoint` | str |

### MetricsSettings

| Field | Type |
|-------|------|
| `enabled` | bool |
| `exporter` | Literal |
| `port` | int |

### TracingSettings

| Field | Type |
|-------|------|
| `enabled` | bool |
| `provider` | Literal |
| `sampling_rate` | float |

### LoggingSettings

| Field | Type |
|-------|------|
| `format` | Literal |
| `include_correlation` | bool |
| `sampling_rate` | float |

### AlertingSettings

| Field | Type |
|-------|------|
| `enabled` | bool |
| `min_severity` | Literal |

---

## Priority Ranking

### P0 - Critical (Block adoption)
- Cloud sink methods: `add_cloudwatch()`, `add_loki()`, `add_postgres()`

### P1 - High (Common use cases)
- Core performance: `with_backpressure()`, `with_workers()`, `with_shutdown_timeout()`
- Circuit breaker: `with_circuit_breaker()`
- Sink routing: `with_sink_routing()`
- Processors: `with_size_guard()`
- Filter config: `configure_filter()`

### P2 - Medium (Advanced users)
- Observability: `with_metrics()`, `with_tracing()`
- Security: `with_encryption()`, `with_access_control()`
- Redaction tuning: mask strings, depth limits
- Exception handling config
- Plugin management

---

## Excluded Fields (Intentional)

These fields intentionally have no builder methods:

| Field | Reason |
|-------|--------|
| `schema_version` | Internal versioning |
| `benchmark_file_path` | Testing/benchmarking only |
