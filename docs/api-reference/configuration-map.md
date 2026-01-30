# Configuration Reference

Quick reference for all fapilog settings with their environment variable names and builder API equivalents.

**Looking for a specific setting?** Use `Ctrl+F` / `Cmd+F` to search by name.

## Environment Variable Naming

Pattern: `FAPILOG_<SECTION>__<SETTING>`

- Use double underscore (`__`) to separate nested levels
- All uppercase
- Examples:
  - `core.log_level` → `FAPILOG_CORE__LOG_LEVEL`
  - `sink_config.rotating_file.max_bytes` → `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES`
  - `filter_config.sampling.sample_rate` → `FAPILOG_FILTER_CONFIG__SAMPLING__SAMPLE_RATE`

**Type conversion:** Environment variables are strings. Fapilog automatically converts:

- Booleans: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off`
- Integers: `100`, `10000`
- Floats: `0.5`, `1.0`
- Durations: `5s`, `1m`, `30s`, `daily`, `hourly`
- Sizes: `10 MB`, `1 GB`, `256 KB`
- Lists: `["a", "b"]` (JSON) or `a,b,c` (CSV)
- Dicts: `{"key": "value"}` (JSON only)

---

## Core Settings

Settings path: `core.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.app_name` | `FAPILOG_CORE__APP_NAME` | `.with_app_name("name")` | `"fapilog"` | Logical application name |
| `core.log_level` | `FAPILOG_CORE__LOG_LEVEL` | `.with_level("INFO")` | `"INFO"` | Default log level (DEBUG, INFO, WARNING, ERROR) |
| `core.max_queue_size` | `FAPILOG_CORE__MAX_QUEUE_SIZE` | `.with_queue_size(10000)` | `10000` | Maximum in-memory queue size |
| `core.batch_max_size` | `FAPILOG_CORE__BATCH_MAX_SIZE` | `.with_batch_size(256)` | `256` | Maximum events per batch |
| `core.batch_timeout_seconds` | `FAPILOG_CORE__BATCH_TIMEOUT_SECONDS` | `.with_batch_timeout("0.25s")` | `0.25` | Max time before flushing partial batch |
| `core.backpressure_wait_ms` | `FAPILOG_CORE__BACKPRESSURE_WAIT_MS` | `.with_backpressure(wait_ms=50)` | `50` | Milliseconds to wait for queue space |
| `core.drop_on_full` | `FAPILOG_CORE__DROP_ON_FULL` | `.with_backpressure(drop_on_full=True)` | `True` | Drop events when queue is full after wait |
| `core.enable_metrics` | `FAPILOG_CORE__ENABLE_METRICS` | `.with_metrics(enabled=True)` | `False` | Enable Prometheus-compatible metrics |
| `core.worker_count` | `FAPILOG_CORE__WORKER_COUNT` | `.with_workers(count=1)` | `1` | Number of worker tasks for flush processing (see Validation Limits below) |
| `core.shutdown_timeout_seconds` | `FAPILOG_CORE__SHUTDOWN_TIMEOUT_SECONDS` | `.with_shutdown_timeout("3s")` | `3.0` | Maximum time to flush on shutdown |
| `core.error_dedupe_window_seconds` | `FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS` | `.with_error_deduplication(5.0)` | `5.0` | Seconds to suppress duplicate ERROR logs |

### Context and Diagnostics

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.context_binding_enabled` | `FAPILOG_CORE__CONTEXT_BINDING_ENABLED` | Settings only | `True` | Enable per-task bound context |
| `core.default_bound_context` | `FAPILOG_CORE__DEFAULT_BOUND_CONTEXT` | `.with_context(**kwargs)` | `{}` | Default bound context at logger creation |
| `core.internal_logging_enabled` | `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED` | `.with_diagnostics(enabled=True)` | `False` | Emit DEBUG/WARN diagnostics for internal errors |
| `core.diagnostics_output` | `FAPILOG_CORE__DIAGNOSTICS_OUTPUT` | `.with_diagnostics(output="stderr")` | `"stderr"` | Output stream: stderr or stdout |

### Exception Handling

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.exceptions_enabled` | `FAPILOG_CORE__EXCEPTIONS_ENABLED` | `.with_exceptions(enabled=True)` | `True` | Enable structured exception serialization |
| `core.exceptions_max_frames` | `FAPILOG_CORE__EXCEPTIONS_MAX_FRAMES` | `.with_exceptions(max_frames=10)` | `10` | Maximum stack frames to capture |
| `core.exceptions_max_stack_chars` | `FAPILOG_CORE__EXCEPTIONS_MAX_STACK_CHARS` | `.with_exceptions(max_stack_chars=20000)` | `20000` | Maximum total characters for stack string |
| `core.capture_unhandled_enabled` | `FAPILOG_CORE__CAPTURE_UNHANDLED_ENABLED` | `.with_unhandled_exception_capture(True)` | `False` | Install unhandled exception hooks |

### Graceful Shutdown

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.atexit_drain_enabled` | `FAPILOG_CORE__ATEXIT_DRAIN_ENABLED` | `.with_atexit_drain(enabled=True)` | `True` | Register atexit handler for log drain |
| `core.atexit_drain_timeout_seconds` | `FAPILOG_CORE__ATEXIT_DRAIN_TIMEOUT_SECONDS` | `.with_atexit_drain(timeout="2s")` | `2.0` | Maximum seconds for atexit drain |
| `core.signal_handler_enabled` | `FAPILOG_CORE__SIGNAL_HANDLER_ENABLED` | `.with_signal_handlers(enabled=True)` | `True` | Install SIGTERM/SIGINT handlers |
| `core.flush_on_critical` | `FAPILOG_CORE__FLUSH_ON_CRITICAL` | `.with_flush_on_critical(enabled=True)` | `False` | Immediately flush ERROR/CRITICAL logs |

### Circuit Breaker

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.sink_circuit_breaker_enabled` | `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED` | `.with_circuit_breaker(enabled=True)` | `False` | Enable circuit breaker for sinks |
| `core.sink_circuit_breaker_failure_threshold` | `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `.with_circuit_breaker(failure_threshold=5)` | `5` | Consecutive failures before opening |
| `core.sink_circuit_breaker_recovery_timeout_seconds` | `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS` | `.with_circuit_breaker(recovery_timeout="30s")` | `30.0` | Seconds before probing failed sink |
| `core.sink_parallel_writes` | `FAPILOG_CORE__SINK_PARALLEL_WRITES` | `.with_parallel_sink_writes(True)` | `False` | Write to sinks in parallel |

### Redaction Settings

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.enable_redactors` | `FAPILOG_CORE__ENABLE_REDACTORS` | Settings only | `True` | Enable redactors stage |
| `core.redactors` | `FAPILOG_CORE__REDACTORS` | `.with_redaction(...)` | `["url_credentials"]` | Redactor plugins to use |
| `core.redactors_order` | `FAPILOG_CORE__REDACTORS_ORDER` | Settings only | `["field-mask", "regex-mask", "url-credentials"]` | Order of redactor application |
| `core.redaction_max_depth` | `FAPILOG_CORE__REDACTION_MAX_DEPTH` | `.with_redaction(max_depth=6)` | `6` | Max nested depth for redaction |
| `core.redaction_max_keys_scanned` | `FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED` | `.with_redaction(max_keys=5000)` | `5000` | Max keys scanned during redaction |
| `core.fallback_redact_mode` | `FAPILOG_CORE__FALLBACK_REDACT_MODE` | `.with_fallback_redaction(fallback_mode="minimal")` | `"minimal"` | Redaction mode for fallback: inherit, minimal, none |
| `core.redaction_fail_mode` | `FAPILOG_CORE__REDACTION_FAIL_MODE` | `.with_fallback_redaction(fail_mode="warn")` | `"warn"` | Behavior on redaction failure: open, closed, warn |
| `core.fallback_scrub_raw` | `FAPILOG_CORE__FALLBACK_SCRUB_RAW` | `.with_fallback_redaction(scrub_raw=True)` | `True` | Apply keyword scrubbing to raw fallback |
| `core.fallback_raw_max_bytes` | `FAPILOG_CORE__FALLBACK_RAW_MAX_BYTES` | `.with_fallback_redaction(raw_max_bytes=1000)` | `None` | Optional byte limit for raw fallback |

### Drop/Dedupe Visibility

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.emit_drop_summary` | `FAPILOG_CORE__EMIT_DROP_SUMMARY` | `.with_drop_summary(enabled=True)` | `False` | Emit summary when events dropped |
| `core.drop_summary_window_seconds` | `FAPILOG_CORE__DROP_SUMMARY_WINDOW_SECONDS` | `.with_drop_summary(window_seconds=60)` | `60.0` | Window for aggregating summaries |

### Plugin Selection

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.sinks` | `FAPILOG_CORE__SINKS` | `.add_file()`, `.add_stdout()`, etc. | `[]` | Sink plugins to use |
| `core.enrichers` | `FAPILOG_CORE__ENRICHERS` | `.with_enrichers(...)` | `["runtime_info", "context_vars"]` | Enricher plugins to use |
| `core.filters` | `FAPILOG_CORE__FILTERS` | `.with_filters(...)` | `[]` | Filter plugins to apply |
| `core.processors` | `FAPILOG_CORE__PROCESSORS` | Settings only | `[]` | Processor plugins to use |

### Advanced

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `core.strict_envelope_mode` | `FAPILOG_CORE__STRICT_ENVELOPE_MODE` | `.with_strict_mode(True)` | `False` | Drop on envelope serialization failure |
| `core.serialize_in_flush` | `FAPILOG_CORE__SERIALIZE_IN_FLUSH` | Settings only | `False` | Pre-serialize envelopes in flush |
| `core.resource_pool_max_size` | `FAPILOG_CORE__RESOURCE_POOL_MAX_SIZE` | Settings only | `8` | Default max size for resource pools |
| `core.resource_pool_acquire_timeout_seconds` | `FAPILOG_CORE__RESOURCE_POOL_ACQUIRE_TIMEOUT_SECONDS` | Settings only | `2.0` | Default acquire timeout for pools |
| `core.sensitive_fields_policy` | `FAPILOG_CORE__SENSITIVE_FIELDS_POLICY` | Settings only | `[]` | Optional list for sensitive fields warning |

### Validation Limits

Configuration values are validated at logger creation. Invalid values raise `ValueError`.

**Hard limits (rejected if violated):**

| Setting | Minimum | Error |
|---------|---------|-------|
| `max_queue_size` | 1 | `queue_capacity must be at least 1` |
| `batch_max_size` | 1 | `batch_max_size must be at least 1` |
| `batch_timeout_seconds` | >0 | `batch_timeout_seconds must be positive` |
| `worker_count` | 1 | `num_workers must be at least 1` |

**Soft limits (warning emitted via diagnostics):**

| Setting | Warning Threshold | Recommendation |
|---------|-------------------|----------------|
| `worker_count` | >32 | More workers increase memory and context-switching overhead |
| `max_queue_size` | >1,000,000 | Large queues consume significant memory |
| `batch_max_size` | >10,000 | Very large batches may cause latency spikes |

**Relationship warning:**

If `batch_max_size` > `max_queue_size`, a warning is emitted because batches can never reach their maximum size.

---

## Sink Settings

### Rotating File Sink

Settings path: `sink_config.rotating_file.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_config.rotating_file.directory` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__DIRECTORY` | `.add_file(directory="...")` | `None` | Log directory |
| `sink_config.rotating_file.filename_prefix` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__FILENAME_PREFIX` | Settings only | `"fapilog"` | Filename prefix |
| `sink_config.rotating_file.mode` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__MODE` | Settings only | `"json"` | Output format: json or text |
| `sink_config.rotating_file.max_bytes` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES` | `.add_file(max_bytes="10 MB")` | `10485760` | Max bytes before rotation |
| `sink_config.rotating_file.interval_seconds` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__INTERVAL_SECONDS` | `.add_file(interval="daily")` | `None` | Rotation interval (hourly, daily, etc.) |
| `sink_config.rotating_file.max_files` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_FILES` | `.add_file(max_files=10)` | `None` | Max rotated files to keep |
| `sink_config.rotating_file.max_total_bytes` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_TOTAL_BYTES` | Settings only | `None` | Max total bytes across all files |
| `sink_config.rotating_file.compress_rotated` | `FAPILOG_SINK_CONFIG__ROTATING_FILE__COMPRESS_ROTATED` | `.add_file(compress=True)` | `False` | Compress rotated files with gzip |

### HTTP Sink

Settings path: `sink_config.http.*` or `http.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `http.endpoint` | `FAPILOG_HTTP__ENDPOINT` | `.add_http(endpoint="...")` | `None` | HTTP endpoint URL |
| `http.headers` | `FAPILOG_HTTP__HEADERS` | `.add_http(headers={...})` | `{}` | Default headers |
| `http.headers_json` | `FAPILOG_HTTP__HEADERS_JSON` | Settings only | `None` | JSON-encoded headers map |
| `http.timeout_seconds` | `FAPILOG_HTTP__TIMEOUT_SECONDS` | `.add_http(timeout="30s")` | `5.0` | Request timeout |
| `http.retry_max_attempts` | `FAPILOG_HTTP__RETRY_MAX_ATTEMPTS` | Settings only | `None` | Max retry attempts |
| `http.retry_backoff_seconds` | `FAPILOG_HTTP__RETRY_BACKOFF_SECONDS` | Settings only | `None` | Base backoff between retries |
| `http.batch_size` | `FAPILOG_HTTP__BATCH_SIZE` | Settings only | `1` | Events per HTTP request |
| `http.batch_timeout_seconds` | `FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS` | Settings only | `5.0` | Max seconds before flush |
| `http.batch_format` | `FAPILOG_HTTP__BATCH_FORMAT` | Settings only | `"array"` | Format: array, ndjson, wrapped |
| `http.batch_wrapper_key` | `FAPILOG_HTTP__BATCH_WRAPPER_KEY` | Settings only | `"logs"` | Wrapper key when format=wrapped |

### Webhook Sink

Settings path: `sink_config.webhook.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_config.webhook.endpoint` | `FAPILOG_SINK_CONFIG__WEBHOOK__ENDPOINT` | `.add_webhook(endpoint="...")` | `None` | Webhook destination URL |
| `sink_config.webhook.secret` | `FAPILOG_SINK_CONFIG__WEBHOOK__SECRET` | `.add_webhook(secret="...")` | `None` | Shared secret for signing |
| `sink_config.webhook.headers` | `FAPILOG_SINK_CONFIG__WEBHOOK__HEADERS` | `.add_webhook(headers={...})` | `{}` | Additional HTTP headers |
| `sink_config.webhook.timeout_seconds` | `FAPILOG_SINK_CONFIG__WEBHOOK__TIMEOUT_SECONDS` | `.add_webhook(timeout="5s")` | `5.0` | Request timeout |
| `sink_config.webhook.retry_max_attempts` | `FAPILOG_SINK_CONFIG__WEBHOOK__RETRY_MAX_ATTEMPTS` | Settings only | `None` | Max retry attempts |
| `sink_config.webhook.retry_backoff_seconds` | `FAPILOG_SINK_CONFIG__WEBHOOK__RETRY_BACKOFF_SECONDS` | Settings only | `None` | Backoff between retries |
| `sink_config.webhook.batch_size` | `FAPILOG_SINK_CONFIG__WEBHOOK__BATCH_SIZE` | Settings only | `1` | Events per request |
| `sink_config.webhook.batch_timeout_seconds` | `FAPILOG_SINK_CONFIG__WEBHOOK__BATCH_TIMEOUT_SECONDS` | Settings only | `5.0` | Max seconds before flush |

### CloudWatch Sink

Settings path: `sink_config.cloudwatch.*`

Short env var aliases are available (e.g., `FAPILOG_CLOUDWATCH__REGION`).

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_config.cloudwatch.log_group_name` | `FAPILOG_CLOUDWATCH__LOG_GROUP_NAME` | `.add_cloudwatch(log_group="...")` | `"/fapilog/default"` | CloudWatch log group name |
| `sink_config.cloudwatch.log_stream_name` | `FAPILOG_CLOUDWATCH__LOG_STREAM_NAME` | `.add_cloudwatch(stream="...")` | `None` | Log stream name |
| `sink_config.cloudwatch.region` | `FAPILOG_CLOUDWATCH__REGION` | `.add_cloudwatch(region="...")` | `None` | AWS region |
| `sink_config.cloudwatch.endpoint_url` | `FAPILOG_CLOUDWATCH__ENDPOINT_URL` | `.add_cloudwatch(endpoint_url="...")` | `None` | Custom endpoint (LocalStack) |
| `sink_config.cloudwatch.create_log_group` | `FAPILOG_CLOUDWATCH__CREATE_LOG_GROUP` | `.add_cloudwatch(create_group=True)` | `True` | Create log group if missing |
| `sink_config.cloudwatch.create_log_stream` | `FAPILOG_CLOUDWATCH__CREATE_LOG_STREAM` | `.add_cloudwatch(create_stream=True)` | `True` | Create log stream if missing |
| `sink_config.cloudwatch.batch_size` | `FAPILOG_CLOUDWATCH__BATCH_SIZE` | `.add_cloudwatch(batch_size=100)` | `100` | Events per batch |
| `sink_config.cloudwatch.batch_timeout_seconds` | `FAPILOG_CLOUDWATCH__BATCH_TIMEOUT_SECONDS` | `.add_cloudwatch(batch_timeout="5s")` | `5.0` | Max seconds before flush |
| `sink_config.cloudwatch.max_retries` | `FAPILOG_CLOUDWATCH__MAX_RETRIES` | `.add_cloudwatch(max_retries=3)` | `3` | Max retries for PutLogEvents |
| `sink_config.cloudwatch.retry_base_delay` | `FAPILOG_CLOUDWATCH__RETRY_BASE_DELAY` | `.add_cloudwatch(retry_delay=0.5)` | `0.5` | Base delay for backoff |
| `sink_config.cloudwatch.circuit_breaker_enabled` | `FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_ENABLED` | `.add_cloudwatch(circuit_breaker=True)` | `True` | Enable circuit breaker |
| `sink_config.cloudwatch.circuit_breaker_threshold` | `FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD` | `.add_cloudwatch(circuit_breaker_threshold=5)` | `5` | Failures before opening |

### Loki Sink

Settings path: `sink_config.loki.*`

Short env var aliases are available (e.g., `FAPILOG_LOKI__URL`).

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_config.loki.url` | `FAPILOG_LOKI__URL` | `.add_loki(url="...")` | `"http://localhost:3100"` | Loki push endpoint |
| `sink_config.loki.tenant_id` | `FAPILOG_LOKI__TENANT_ID` | `.add_loki(tenant_id="...")` | `None` | Multi-tenant identifier |
| `sink_config.loki.labels` | `FAPILOG_LOKI__LABELS` | `.add_loki(labels={...})` | `{"service": "fapilog"}` | Static labels for streams |
| `sink_config.loki.label_keys` | `FAPILOG_LOKI__LABEL_KEYS` | `.add_loki(label_keys=[...])` | `["level"]` | Event keys to promote to labels |
| `sink_config.loki.batch_size` | `FAPILOG_LOKI__BATCH_SIZE` | `.add_loki(batch_size=100)` | `100` | Events per batch |
| `sink_config.loki.batch_timeout_seconds` | `FAPILOG_LOKI__BATCH_TIMEOUT_SECONDS` | `.add_loki(batch_timeout="5s")` | `5.0` | Max seconds before flush |
| `sink_config.loki.timeout_seconds` | `FAPILOG_LOKI__TIMEOUT_SECONDS` | `.add_loki(timeout="10s")` | `10.0` | HTTP timeout |
| `sink_config.loki.max_retries` | `FAPILOG_LOKI__MAX_RETRIES` | `.add_loki(max_retries=3)` | `3` | Max retries on failure |
| `sink_config.loki.retry_base_delay` | `FAPILOG_LOKI__RETRY_BASE_DELAY` | `.add_loki(retry_delay=0.5)` | `0.5` | Base delay for backoff |
| `sink_config.loki.auth_username` | `FAPILOG_LOKI__AUTH_USERNAME` | `.add_loki(auth_username="...")` | `None` | Basic auth username |
| `sink_config.loki.auth_password` | `FAPILOG_LOKI__AUTH_PASSWORD` | `.add_loki(auth_password="...")` | `None` | Basic auth password |
| `sink_config.loki.auth_token` | `FAPILOG_LOKI__AUTH_TOKEN` | `.add_loki(auth_token="...")` | `None` | Bearer token |
| `sink_config.loki.circuit_breaker_enabled` | `FAPILOG_LOKI__CIRCUIT_BREAKER_ENABLED` | `.add_loki(circuit_breaker=True)` | `True` | Enable circuit breaker |
| `sink_config.loki.circuit_breaker_threshold` | `FAPILOG_LOKI__CIRCUIT_BREAKER_THRESHOLD` | `.add_loki(circuit_breaker_threshold=5)` | `5` | Failures before opening |

### PostgreSQL Sink

Settings path: `sink_config.postgres.*`

Short env var aliases are available (e.g., `FAPILOG_POSTGRES__HOST`).

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_config.postgres.dsn` | `FAPILOG_POSTGRES__DSN` | `.add_postgres(dsn="...")` | `None` | Full connection string |
| `sink_config.postgres.host` | `FAPILOG_POSTGRES__HOST` | `.add_postgres(host="...")` | `"localhost"` | Database host |
| `sink_config.postgres.port` | `FAPILOG_POSTGRES__PORT` | `.add_postgres(port=5432)` | `5432` | Database port |
| `sink_config.postgres.database` | `FAPILOG_POSTGRES__DATABASE` | `.add_postgres(database="...")` | `"fapilog"` | Database name |
| `sink_config.postgres.user` | `FAPILOG_POSTGRES__USER` | `.add_postgres(user="...")` | `"fapilog"` | Username |
| `sink_config.postgres.password` | `FAPILOG_POSTGRES__PASSWORD` | `.add_postgres(password="...")` | `None` | Password |
| `sink_config.postgres.table_name` | `FAPILOG_POSTGRES__TABLE_NAME` | `.add_postgres(table="...")` | `"logs"` | Target table |
| `sink_config.postgres.schema_name` | `FAPILOG_POSTGRES__SCHEMA_NAME` | `.add_postgres(schema="...")` | `"public"` | Database schema |
| `sink_config.postgres.create_table` | `FAPILOG_POSTGRES__CREATE_TABLE` | `.add_postgres(create_table=True)` | `True` | Auto-create table |
| `sink_config.postgres.min_pool_size` | `FAPILOG_POSTGRES__MIN_POOL_SIZE` | `.add_postgres(min_pool=2)` | `2` | Minimum pool connections |
| `sink_config.postgres.max_pool_size` | `FAPILOG_POSTGRES__MAX_POOL_SIZE` | `.add_postgres(max_pool=10)` | `10` | Maximum pool connections |
| `sink_config.postgres.pool_acquire_timeout` | `FAPILOG_POSTGRES__POOL_ACQUIRE_TIMEOUT` | `.add_postgres(pool_acquire_timeout="10s")` | `10.0` | Pool acquire timeout |
| `sink_config.postgres.batch_size` | `FAPILOG_POSTGRES__BATCH_SIZE` | `.add_postgres(batch_size=100)` | `100` | Events per batch |
| `sink_config.postgres.batch_timeout_seconds` | `FAPILOG_POSTGRES__BATCH_TIMEOUT_SECONDS` | `.add_postgres(batch_timeout="5s")` | `5.0` | Max seconds before flush |
| `sink_config.postgres.max_retries` | `FAPILOG_POSTGRES__MAX_RETRIES` | `.add_postgres(max_retries=3)` | `3` | Max retries |
| `sink_config.postgres.retry_base_delay` | `FAPILOG_POSTGRES__RETRY_BASE_DELAY` | `.add_postgres(retry_delay=0.5)` | `0.5` | Base delay for backoff |
| `sink_config.postgres.circuit_breaker_enabled` | `FAPILOG_POSTGRES__CIRCUIT_BREAKER_ENABLED` | `.add_postgres(circuit_breaker=True)` | `True` | Enable circuit breaker |
| `sink_config.postgres.circuit_breaker_threshold` | `FAPILOG_POSTGRES__CIRCUIT_BREAKER_THRESHOLD` | `.add_postgres(circuit_breaker_threshold=5)` | `5` | Failures before opening |
| `sink_config.postgres.use_jsonb` | `FAPILOG_POSTGRES__USE_JSONB` | `.add_postgres(use_jsonb=True)` | `True` | Use JSONB column type |
| `sink_config.postgres.include_raw_json` | `FAPILOG_POSTGRES__INCLUDE_RAW_JSON` | `.add_postgres(include_raw_json=True)` | `True` | Store full event JSON |
| `sink_config.postgres.extract_fields` | `FAPILOG_POSTGRES__EXTRACT_FIELDS` | `.add_postgres(extract_fields=[...])` | `["timestamp", "level", ...]` | Fields to promote to columns |

### Sealed Sink (Tamper-Evident)

Settings path: `sink_config.sealed.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_config.sealed.inner_sink` | `FAPILOG_SINK_CONFIG__SEALED__INNER_SINK` | Settings only | `"rotating_file"` | Inner sink to wrap |
| `sink_config.sealed.inner_config` | `FAPILOG_SINK_CONFIG__SEALED__INNER_CONFIG` | Settings only | `{}` | Inner sink configuration |
| `sink_config.sealed.manifest_path` | `FAPILOG_SINK_CONFIG__SEALED__MANIFEST_PATH` | Settings only | `None` | Manifest directory |
| `sink_config.sealed.sign_manifests` | `FAPILOG_SINK_CONFIG__SEALED__SIGN_MANIFESTS` | Settings only | `True` | Sign manifests when keys available |
| `sink_config.sealed.key_id` | `FAPILOG_SINK_CONFIG__SEALED__KEY_ID` | Settings only | `None` | Signing key identifier |
| `sink_config.sealed.key_provider` | `FAPILOG_SINK_CONFIG__SEALED__KEY_PROVIDER` | Settings only | `"env"` | Key provider for signing |
| `sink_config.sealed.chain_state_path` | `FAPILOG_SINK_CONFIG__SEALED__CHAIN_STATE_PATH` | Settings only | `None` | Chain state directory |
| `sink_config.sealed.rotate_chain` | `FAPILOG_SINK_CONFIG__SEALED__ROTATE_CHAIN` | Settings only | `False` | Reset chain on rotation |
| `sink_config.sealed.fsync_on_write` | `FAPILOG_SINK_CONFIG__SEALED__FSYNC_ON_WRITE` | Settings only | `False` | Fsync on every write |
| `sink_config.sealed.fsync_on_rotate` | `FAPILOG_SINK_CONFIG__SEALED__FSYNC_ON_ROTATE` | Settings only | `True` | Fsync after rotation |
| `sink_config.sealed.compress_rotated` | `FAPILOG_SINK_CONFIG__SEALED__COMPRESS_ROTATED` | Settings only | `False` | Compress rotated files |
| `sink_config.sealed.use_kms_signing` | `FAPILOG_SINK_CONFIG__SEALED__USE_KMS_SIGNING` | Settings only | `False` | Sign via external KMS |

---

## Sink Routing

Settings path: `sink_routing.*`

Short env var aliases are available (e.g., `FAPILOG_SINK_ROUTING__ENABLED`).

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `sink_routing.enabled` | `FAPILOG_SINK_ROUTING__ENABLED` | `.with_routing(rules=[...])` | `False` | Enable level-based routing |
| `sink_routing.rules` | `FAPILOG_SINK_ROUTING__RULES` | `.with_routing(rules=[...])` | `[]` | Routing rules in priority order |
| `sink_routing.overlap` | `FAPILOG_SINK_ROUTING__OVERLAP` | `.with_routing(overlap=True)` | `True` | Allow multiple rule matches |
| `sink_routing.fallback_sinks` | `FAPILOG_SINK_ROUTING__FALLBACK_SINKS` | `.with_routing(fallback=[...])` | `[]` | Sinks when no rules match |

**Routing rules format:**

```json
[
  {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
  {"levels": ["INFO", "DEBUG"], "sinks": ["file"]}
]
```

---

## Redaction Settings

### Field Mask Redactor

Settings path: `redactor_config.field_mask.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `redactor_config.field_mask.fields_to_mask` | `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__FIELDS_TO_MASK` | `.with_redaction(fields=[...])` | `[]` | Field names to mask |
| `redactor_config.field_mask.mask_string` | `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MASK_STRING` | `.with_redaction(mask="***")` | `"***"` | Replacement string |
| `redactor_config.field_mask.block_on_unredactable` | `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__BLOCK_ON_UNREDACTABLE` | `.with_redaction(block_on_failure=True)` | `False` | Block if redaction fails |
| `redactor_config.field_mask.max_depth` | `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MAX_DEPTH` | Settings only | `16` | Max nested depth |
| `redactor_config.field_mask.max_keys_scanned` | `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MAX_KEYS_SCANNED` | Settings only | `1000` | Max keys to scan |

### Regex Mask Redactor

Settings path: `redactor_config.regex_mask.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `redactor_config.regex_mask.patterns` | `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__PATTERNS` | `.with_redaction(patterns=[...])` | `[]` | Regex patterns to mask |
| `redactor_config.regex_mask.mask_string` | `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__MASK_STRING` | `.with_redaction(mask="***")` | `"***"` | Replacement string |
| `redactor_config.regex_mask.block_on_unredactable` | `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__BLOCK_ON_UNREDACTABLE` | `.with_redaction(block_on_failure=True)` | `False` | Block if redaction fails |
| `redactor_config.regex_mask.max_depth` | `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__MAX_DEPTH` | Settings only | `16` | Max nested depth |
| `redactor_config.regex_mask.max_keys_scanned` | `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__MAX_KEYS_SCANNED` | Settings only | `1000` | Max keys to scan |

### URL Credentials Redactor

Settings path: `redactor_config.url_credentials.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `redactor_config.url_credentials.max_string_length` | `FAPILOG_REDACTOR_CONFIG__URL_CREDENTIALS__MAX_STRING_LENGTH` | `.with_redaction(url_max_length=4096)` | `4096` | Max string length to parse |

**Redaction presets:** For compliance-ready redaction, see the [Redaction Presets](../redaction/presets.md) documentation covering GDPR_PII, HIPAA_PHI, PCI_DSS, CREDENTIALS, and more.

---

## Filter Settings

### Sampling Filter

Settings path: `filter_config.sampling.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `filter_config.sampling.sample_rate` | `FAPILOG_FILTER_CONFIG__SAMPLING__SAMPLE_RATE` | `.with_sampling(rate=0.1)` | `1.0` | Sample rate 0.0-1.0 |
| `filter_config.sampling.seed` | `FAPILOG_FILTER_CONFIG__SAMPLING__SEED` | `.with_sampling(seed=42)` | `None` | Random seed for reproducibility |

### Adaptive Sampling Filter

Settings path: `filter_config.adaptive_sampling.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `filter_config.adaptive_sampling.min_rate` | `FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__MIN_RATE` | `.with_adaptive_sampling(min_rate=0.01)` | `0.01` | Minimum sample rate |
| `filter_config.adaptive_sampling.max_rate` | `FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__MAX_RATE` | `.with_adaptive_sampling(max_rate=1.0)` | `1.0` | Maximum sample rate |
| `filter_config.adaptive_sampling.target_events_per_sec` | `FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__TARGET_EVENTS_PER_SEC` | `.with_adaptive_sampling(target_events_per_sec=1000)` | `1000.0` | Target throughput |
| `filter_config.adaptive_sampling.window_seconds` | `FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__WINDOW_SECONDS` | `.with_adaptive_sampling(window_seconds=60)` | `60.0` | Measurement window |

### Trace Sampling Filter

Settings path: `filter_config.trace_sampling.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `filter_config.trace_sampling.default_rate` | `FAPILOG_FILTER_CONFIG__TRACE_SAMPLING__DEFAULT_RATE` | `.with_trace_sampling(default_rate=0.1)` | `1.0` | Default rate when no trace context |
| `filter_config.trace_sampling.honor_upstream` | `FAPILOG_FILTER_CONFIG__TRACE_SAMPLING__HONOR_UPSTREAM` | `.with_trace_sampling(honor_upstream=True)` | `True` | Honor upstream decisions |

### Rate Limit Filter

Settings path: `filter_config.rate_limit.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `filter_config.rate_limit.capacity` | `FAPILOG_FILTER_CONFIG__RATE_LIMIT__CAPACITY` | `.with_rate_limit(capacity=10)` | `10` | Token bucket capacity |
| `filter_config.rate_limit.refill_rate_per_sec` | `FAPILOG_FILTER_CONFIG__RATE_LIMIT__REFILL_RATE_PER_SEC` | `.with_rate_limit(refill_rate=5.0)` | `5.0` | Tokens per second |
| `filter_config.rate_limit.key_field` | `FAPILOG_FILTER_CONFIG__RATE_LIMIT__KEY_FIELD` | `.with_rate_limit(key_field="...")` | `None` | Field for partitioning |
| `filter_config.rate_limit.max_keys` | `FAPILOG_FILTER_CONFIG__RATE_LIMIT__MAX_KEYS` | `.with_rate_limit(max_keys=10000)` | `10000` | Max buckets |
| `filter_config.rate_limit.overflow_action` | `FAPILOG_FILTER_CONFIG__RATE_LIMIT__OVERFLOW_ACTION` | `.with_rate_limit(overflow_action="drop")` | `"drop"` | Action: drop or mark |

### First Occurrence Filter

Settings path: `filter_config.first_occurrence.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `filter_config.first_occurrence.window_seconds` | `FAPILOG_FILTER_CONFIG__FIRST_OCCURRENCE__WINDOW_SECONDS` | `.with_first_occurrence(window_seconds=300)` | `300.0` | Dedup window |
| `filter_config.first_occurrence.max_entries` | `FAPILOG_FILTER_CONFIG__FIRST_OCCURRENCE__MAX_ENTRIES` | `.with_first_occurrence(max_entries=10000)` | `10000` | Max tracked messages |
| `filter_config.first_occurrence.key_fields` | `FAPILOG_FILTER_CONFIG__FIRST_OCCURRENCE__KEY_FIELDS` | `.with_first_occurrence(key_fields=[...])` | `None` | Fields for dedup key |

---

## Processor Settings

### Size Guard Processor

Settings path: `processor_config.size_guard.*`

Short env var aliases are available (e.g., `FAPILOG_SIZE_GUARD__MAX_BYTES`).

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `processor_config.size_guard.max_bytes` | `FAPILOG_SIZE_GUARD__MAX_BYTES` | `.with_size_guard(max_bytes="256 KB")` | `256000` | Maximum payload size |
| `processor_config.size_guard.action` | `FAPILOG_SIZE_GUARD__ACTION` | `.with_size_guard(action="truncate")` | `"truncate"` | Action: truncate, drop, warn |
| `processor_config.size_guard.preserve_fields` | `FAPILOG_SIZE_GUARD__PRESERVE_FIELDS` | `.with_size_guard(preserve_fields=[...])` | `["level", "timestamp", ...]` | Fields to never remove |

---

## Observability Settings

Settings path: `observability.*`

### Monitoring

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `observability.monitoring.enabled` | `FAPILOG_OBSERVABILITY__MONITORING__ENABLED` | Settings only | `False` | Enable health/monitoring |
| `observability.monitoring.endpoint` | `FAPILOG_OBSERVABILITY__MONITORING__ENDPOINT` | Settings only | `None` | Monitoring endpoint URL |

### Metrics

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `observability.metrics.enabled` | `FAPILOG_OBSERVABILITY__METRICS__ENABLED` | Settings only | `False` | Enable metrics collection |
| `observability.metrics.exporter` | `FAPILOG_OBSERVABILITY__METRICS__EXPORTER` | Settings only | `"prometheus"` | Exporter: prometheus or none |
| `observability.metrics.port` | `FAPILOG_OBSERVABILITY__METRICS__PORT` | Settings only | `8000` | Metrics exporter port |

### Tracing

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `observability.tracing.enabled` | `FAPILOG_OBSERVABILITY__TRACING__ENABLED` | Settings only | `False` | Enable distributed tracing |
| `observability.tracing.provider` | `FAPILOG_OBSERVABILITY__TRACING__PROVIDER` | Settings only | `"otel"` | Provider: otel or none |
| `observability.tracing.sampling_rate` | `FAPILOG_OBSERVABILITY__TRACING__SAMPLING_RATE` | Settings only | `0.1` | Trace sampling rate 0.0-1.0 |

### Logging

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `observability.logging.format` | `FAPILOG_OBSERVABILITY__LOGGING__FORMAT` | Settings only | `"json"` | Output format: json or text |
| `observability.logging.include_correlation` | `FAPILOG_OBSERVABILITY__LOGGING__INCLUDE_CORRELATION` | Settings only | `True` | Include correlation IDs |
| `observability.logging.sampling_rate` | `FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE` | Settings only | `1.0` | Log sampling rate (deprecated) |

### Alerting

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `observability.alerting.enabled` | `FAPILOG_OBSERVABILITY__ALERTING__ENABLED` | Settings only | `False` | Enable alerting |
| `observability.alerting.min_severity` | `FAPILOG_OBSERVABILITY__ALERTING__MIN_SEVERITY` | Settings only | `"ERROR"` | Minimum alert severity |

---

## Plugin Settings

Settings path: `plugins.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `plugins.enabled` | `FAPILOG_PLUGINS__ENABLED` | `.with_plugins(enabled=True)` | `True` | Enable plugin loading |
| `plugins.allow_external` | `FAPILOG_PLUGINS__ALLOW_EXTERNAL` | `.with_plugins(allow_external=True)` | `False` | Allow entry point plugins |
| `plugins.allowlist` | `FAPILOG_PLUGINS__ALLOWLIST` | `.with_plugins(allowlist=[...])` | `[]` | Only allow these plugins |
| `plugins.denylist` | `FAPILOG_PLUGINS__DENYLIST` | `.with_plugins(denylist=[...])` | `[]` | Block these plugins |
| `plugins.validation_mode` | `FAPILOG_PLUGINS__VALIDATION_MODE` | `.with_plugins(validation_mode="warn")` | `"disabled"` | Mode: disabled, warn, strict |

---

## Enricher Settings

### Integrity Enricher (Tamper-Evident)

Settings path: `enricher_config.integrity.*`

| Setting | Env Var | Builder Method | Default | Description |
|---------|---------|----------------|---------|-------------|
| `enricher_config.integrity.algorithm` | `FAPILOG_ENRICHER_CONFIG__INTEGRITY__ALGORITHM` | Settings only | `"sha256"` | MAC algorithm: sha256 or ed25519 |
| `enricher_config.integrity.key_id` | `FAPILOG_ENRICHER_CONFIG__INTEGRITY__KEY_ID` | Settings only | `None` | Key identifier |
| `enricher_config.integrity.key_provider` | `FAPILOG_ENRICHER_CONFIG__INTEGRITY__KEY_PROVIDER` | Settings only | `"env"` | Key provider |
| `enricher_config.integrity.chain_state_path` | `FAPILOG_ENRICHER_CONFIG__INTEGRITY__CHAIN_STATE_PATH` | Settings only | `None` | Chain state directory |
| `enricher_config.integrity.rotate_chain` | `FAPILOG_ENRICHER_CONFIG__INTEGRITY__ROTATE_CHAIN` | Settings only | `False` | Reset chain after rotation |
| `enricher_config.integrity.use_kms_signing` | `FAPILOG_ENRICHER_CONFIG__INTEGRITY__USE_KMS_SIGNING` | Settings only | `False` | Sign via KMS provider |

---

## See Also

- [Configuration Guide](../user-guide/configuration.md) - Detailed configuration guide with examples
- [Environment Variables](../user-guide/environment-variables.md) - Full env var reference
- [Builder API](builder.md) - LoggerBuilder API reference
- [Redaction Presets](../redaction/presets.md) - Compliance-ready redaction presets
