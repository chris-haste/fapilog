<!-- AUTO-GENERATED: do not edit by hand. Run scripts/generate_env_matrix.py -->
# Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FAPILOG_CORE__APP_NAME` | str | fapilog | Logical application name |
| `FAPILOG_CORE__ATEXIT_DRAIN_ENABLED` | bool | True | Register atexit handler to drain pending logs on normal process exit |
| `FAPILOG_CORE__ATEXIT_DRAIN_TIMEOUT_SECONDS` | float | 2.0 | Maximum seconds to wait for log drain during atexit handler |
| `FAPILOG_CORE__BACKPRESSURE_WAIT_MS` | int | 50 | Milliseconds to wait for queue space before dropping |
| `FAPILOG_CORE__BATCH_MAX_SIZE` | int | 256 | Maximum number of events per batch before a flush is triggered |
| `FAPILOG_CORE__BATCH_TIMEOUT_SECONDS` | float | 0.25 | Maximum time to wait before flushing a partial batch |
| `FAPILOG_CORE__BENCHMARK_FILE_PATH` | str | None | — | Optional path used by performance benchmarks |
| `FAPILOG_CORE__CAPTURE_UNHANDLED_ENABLED` | bool | False | Automatically install unhandled exception hooks (sys/asyncio) |
| `FAPILOG_CORE__CONTEXT_BINDING_ENABLED` | bool | True | Enable per-task bound context via logger.bind/unbind/clear |
| `FAPILOG_CORE__DEFAULT_BOUND_CONTEXT` | dict | PydanticUndefined | Default bound context applied at logger creation when enabled |
| `FAPILOG_CORE__DIAGNOSTICS_OUTPUT` | Literal | stderr | Output stream for internal diagnostics: stderr (default, Unix convention) or stdout (backward compat) |
| `FAPILOG_CORE__DROP_ON_FULL` | bool | True | If True, drop events after backpressure_wait_ms elapses when queue is full |
| `FAPILOG_CORE__DROP_SUMMARY_WINDOW_SECONDS` | float | 60.0 | Window in seconds for aggregating drop/dedupe summary events. Summaries are emitted at most once per window. |
| `FAPILOG_CORE__EMIT_DROP_SUMMARY` | bool | False | Emit summary log events when events are dropped due to backpressure or deduplicated due to error dedupe window |
| `FAPILOG_CORE__ENABLE_METRICS` | bool | False | Enable Prometheus-compatible metrics |
| `FAPILOG_CORE__ENABLE_REDACTORS` | bool | True | Enable redactors stage between enrichers and sink emission |
| `FAPILOG_CORE__ENRICHERS` | list | PydanticUndefined | Enricher plugins to use (by name) |
| `FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS` | float | 5.0 | Seconds to suppress duplicate ERROR logs with the same message; 0 disables deduplication |
| `FAPILOG_CORE__EXCEPTIONS_ENABLED` | bool | True | Enable structured exception serialization for log calls |
| `FAPILOG_CORE__EXCEPTIONS_MAX_FRAMES` | int | 10 | Maximum number of stack frames to capture for exceptions |
| `FAPILOG_CORE__EXCEPTIONS_MAX_STACK_CHARS` | int | 20000 | Maximum total characters for serialized stack string |
| `FAPILOG_CORE__FALLBACK_RAW_MAX_BYTES` | int | None | — | Optional limit for raw fallback output bytes; payloads exceeding this are truncated with '[truncated]' marker |
| `FAPILOG_CORE__FALLBACK_REDACT_MODE` | Literal | minimal | Redaction mode for fallback stderr output: 'inherit' uses pipeline redactors, 'minimal' applies built-in sensitive field masking, 'none' writes unredacted (opt-in to legacy behavior) |
| `FAPILOG_CORE__FALLBACK_SCRUB_RAW` | bool | True | Apply keyword scrubbing to raw (non-JSON) fallback output; set to False for debugging when raw output is needed |
| `FAPILOG_CORE__FILTERS` | list | PydanticUndefined | Filter plugins to apply before enrichment (by name) |
| `FAPILOG_CORE__FLUSH_ON_CRITICAL` | bool | False | Immediately flush ERROR and CRITICAL logs (bypass batching) to reduce log loss on abrupt shutdown |
| `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED` | bool | False | Emit DEBUG/WARN diagnostics for internal errors |
| `FAPILOG_CORE__LOG_LEVEL` | Literal | INFO | Default log level |
| `FAPILOG_CORE__MAX_QUEUE_SIZE` | int | 10000 | Maximum in-memory queue size for async processing |
| `FAPILOG_CORE__PROCESSORS` | list | PydanticUndefined | Processor plugins to use (by name) |
| `FAPILOG_CORE__REDACTION_FAIL_MODE` | Literal | warn | Behavior when _apply_redactors() catches an unexpected exception: 'open' passes original event, 'closed' drops the event, 'warn' (default) passes event but emits diagnostic warning |
| `FAPILOG_CORE__REDACTION_MAX_DEPTH` | int | None | 6 | Optional max depth guardrail for nested redaction |
| `FAPILOG_CORE__REDACTION_MAX_KEYS_SCANNED` | int | None | 5000 | Optional max keys scanned guardrail for redaction |
| `FAPILOG_CORE__REDACTORS` | list | PydanticUndefined | Redactor plugins to use (by name); defaults to ['url_credentials'] for secure defaults; set to [] to disable all redaction |
| `FAPILOG_CORE__REDACTORS_ORDER` | list | PydanticUndefined | Ordered list of redactor plugin names to apply |
| `FAPILOG_CORE__RESOURCE_POOL_ACQUIRE_TIMEOUT_SECONDS` | float | 2.0 | Default acquire timeout for pools |
| `FAPILOG_CORE__RESOURCE_POOL_MAX_SIZE` | int | 8 | Default max size for resource pools |
| `FAPILOG_CORE__SENSITIVE_FIELDS_POLICY` | list | PydanticUndefined | Optional list of dotted paths for sensitive fields policy; warning if no redactors configured |
| `FAPILOG_CORE__SERIALIZE_IN_FLUSH` | bool | False | If True, pre-serialize envelopes once during flush and pass SerializedView to sinks that support write_serialized |
| `FAPILOG_CORE__SHUTDOWN_TIMEOUT_SECONDS` | float | 3.0 | Maximum time to flush on shutdown signals |
| `FAPILOG_CORE__SIGNAL_HANDLER_ENABLED` | bool | True | Install signal handlers for SIGTERM/SIGINT to enable graceful drain |
| `FAPILOG_CORE__SINKS` | list | PydanticUndefined | Sink plugins to use (by name); falls back to env-based default when empty |
| `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED` | bool | False | Enable circuit breaker for sink fault isolation |
| `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | int | 5 | Number of consecutive failures before opening circuit |
| `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS` | float | 30.0 | Seconds to wait before probing a failed sink |
| `FAPILOG_CORE__SINK_PARALLEL_WRITES` | bool | False | Write to multiple sinks in parallel instead of sequentially |
| `FAPILOG_CORE__STRICT_ENVELOPE_MODE` | bool | False | If True, drop emission when envelope cannot be produced; otherwise fallback to best-effort serialization with diagnostics |
| `FAPILOG_CORE__WORKER_COUNT` | int | 1 | Number of worker tasks for flush processing |
| `FAPILOG_ENRICHER_CONFIG__CONTEXT_VARS` | dict | PydanticUndefined | Configuration for context_vars enricher |
| `FAPILOG_ENRICHER_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party enrichers by name |
| `FAPILOG_ENRICHER_CONFIG__INTEGRITY__ALGORITHM` | Literal | sha256 | MAC or signature algorithm |
| `FAPILOG_ENRICHER_CONFIG__INTEGRITY__CHAIN_STATE_PATH` | str | None | — | Directory to persist chain state |
| `FAPILOG_ENRICHER_CONFIG__INTEGRITY__KEY_ID` | str | None | — | Key identifier used for MAC/signature |
| `FAPILOG_ENRICHER_CONFIG__INTEGRITY__KEY_PROVIDER` | str | None | env | Key provider for MAC/signature |
| `FAPILOG_ENRICHER_CONFIG__INTEGRITY__ROTATE_CHAIN` | bool | False | Reset chain after rotation |
| `FAPILOG_ENRICHER_CONFIG__INTEGRITY__USE_KMS_SIGNING` | bool | False | Sign integrity hashes via KMS provider |
| `FAPILOG_ENRICHER_CONFIG__RUNTIME_INFO` | dict | PydanticUndefined | Configuration for runtime_info enricher |
| `FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING` | dict | PydanticUndefined | Configuration for adaptive_sampling filter |
| `FAPILOG_FILTER_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party filters by name |
| `FAPILOG_FILTER_CONFIG__FIRST_OCCURRENCE` | dict | PydanticUndefined | Configuration for first_occurrence filter |
| `FAPILOG_FILTER_CONFIG__LEVEL` | dict | PydanticUndefined | Configuration for level filter |
| `FAPILOG_FILTER_CONFIG__RATE_LIMIT` | dict | PydanticUndefined | Configuration for rate_limit filter |
| `FAPILOG_FILTER_CONFIG__SAMPLING` | dict | PydanticUndefined | Configuration for sampling filter |
| `FAPILOG_FILTER_CONFIG__TRACE_SAMPLING` | dict | PydanticUndefined | Configuration for trace_sampling filter |
| `FAPILOG_HTTP__BATCH_FORMAT` | str | array | Batch format: 'array', 'ndjson', or 'wrapped' |
| `FAPILOG_HTTP__BATCH_SIZE` | int | 1 | Maximum events per HTTP request (1 = no batching) |
| `FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch. Accepts '5s' or 5.0 |
| `FAPILOG_HTTP__BATCH_WRAPPER_KEY` | str | logs | Wrapper key when batch_format='wrapped' |
| `FAPILOG_HTTP__ENDPOINT` | str | None | — | HTTP endpoint to POST log events to |
| `FAPILOG_HTTP__HEADERS` | dict | PydanticUndefined | Default headers to send with each request |
| `FAPILOG_HTTP__HEADERS_JSON` | str | None | — | JSON-encoded headers map (e.g. '{"Authorization": "Bearer x"}') |
| `FAPILOG_HTTP__RETRY_BACKOFF_SECONDS` | float | None | — | Optional base backoff between retries. Accepts '2s' or 2.0 |
| `FAPILOG_HTTP__RETRY_MAX_ATTEMPTS` | int | None | — | Optional max attempts for HTTP retries |
| `FAPILOG_HTTP__TIMEOUT_SECONDS` | float | 5.0 | Request timeout for HTTP sink operations. Accepts '5s' or 5.0 |
| `FAPILOG_OBSERVABILITY__ALERTING__ENABLED` | bool | False | Enable emitting alerts from the logging pipeline |
| `FAPILOG_OBSERVABILITY__ALERTING__MIN_SEVERITY` | Literal | ERROR | Minimum alert severity to emit (filter threshold) |
| `FAPILOG_OBSERVABILITY__LOGGING__FORMAT` | Literal | json | Output format for logs (machine-friendly JSON or text) |
| `FAPILOG_OBSERVABILITY__LOGGING__INCLUDE_CORRELATION` | bool | True | Include correlation IDs and trace/span metadata in logs |
| `FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE` | float | 1.0 | DEPRECATED: Use core.filters=['sampling'] with filter_config.sampling instead. Log sampling probability in range 0.0–1.0. |
| `FAPILOG_OBSERVABILITY__METRICS__ENABLED` | bool | False | Enable internal metrics collection/export |
| `FAPILOG_OBSERVABILITY__METRICS__EXPORTER` | Literal | prometheus | Metrics exporter to use ('prometheus' or 'none') |
| `FAPILOG_OBSERVABILITY__METRICS__PORT` | int | 8000 | TCP port for metrics exporter |
| `FAPILOG_OBSERVABILITY__MONITORING__ENABLED` | bool | False | Enable health/monitoring checks and endpoints |
| `FAPILOG_OBSERVABILITY__MONITORING__ENDPOINT` | str | None | — | Monitoring endpoint URL |
| `FAPILOG_OBSERVABILITY__TRACING__ENABLED` | bool | False | Enable distributed tracing features |
| `FAPILOG_OBSERVABILITY__TRACING__PROVIDER` | Literal | otel | Tracing backend provider ('otel' or 'none') |
| `FAPILOG_OBSERVABILITY__TRACING__SAMPLING_RATE` | float | 0.1 | Trace sampling probability in range 0.0–1.0 |
| `FAPILOG_PLUGINS__ALLOWLIST` | list | PydanticUndefined | If non-empty, only these plugin names are allowed |
| `FAPILOG_PLUGINS__ALLOW_EXTERNAL` | bool | False | Allow loading plugins from entry points (security risk) |
| `FAPILOG_PLUGINS__DENYLIST` | list | PydanticUndefined | Plugin names to block from loading |
| `FAPILOG_PLUGINS__ENABLED` | bool | True | Enable plugin loading |
| `FAPILOG_PLUGINS__VALIDATION_MODE` | str | disabled | Plugin validation mode: disabled, warn, or strict |
| `FAPILOG_PROCESSOR_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party processors by name |
| `FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION` | Literal | truncate | Action to take when payload exceeds max_bytes |
| `FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES` | int | 256000 | Maximum payload size in bytes (min 100). Accepts '1 MB' or 1048576 |
| `FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__PRESERVE_FIELDS` | list | PydanticUndefined | Fields that should never be removed during truncation |
| `FAPILOG_PROCESSOR_CONFIG__ZERO_COPY` | dict | PydanticUndefined | Configuration for zero_copy processor (reserved for future options) |
| `FAPILOG_REDACTOR_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party redactors by name |
| `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__BLOCK_ON_UNREDACTABLE` | bool | False | Block log entry if redaction fails |
| `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__FIELDS_TO_MASK` | list | PydanticUndefined | Field names to mask (case-insensitive) |
| `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MASK_STRING` | str | *** | Replacement mask string |
| `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MAX_DEPTH` | int | 16 | Max nested depth to scan |
| `FAPILOG_REDACTOR_CONFIG__FIELD_MASK__MAX_KEYS_SCANNED` | int | 1000 | Max keys to scan before stopping |
| `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__BLOCK_ON_UNREDACTABLE` | bool | False | Block log entry if redaction fails |
| `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__MASK_STRING` | str | *** | Replacement mask string |
| `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__MAX_DEPTH` | int | 16 | Max nested depth to scan |
| `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__MAX_KEYS_SCANNED` | int | 1000 | Max keys to scan before stopping |
| `FAPILOG_REDACTOR_CONFIG__REGEX_MASK__PATTERNS` | list | PydanticUndefined | Regex patterns to match and mask |
| `FAPILOG_REDACTOR_CONFIG__URL_CREDENTIALS__MAX_STRING_LENGTH` | int | 4096 | Max string length to parse for URL credentials |
| `FAPILOG_SCHEMA_VERSION` | str | 1.0 | Configuration schema version for forward/backward compatibility |
| `FAPILOG_SECURITY__ACCESS_CONTROL__ALLOWED_ROLES` | list | PydanticUndefined | List of roles granted access to protected operations |
| `FAPILOG_SECURITY__ACCESS_CONTROL__ALLOW_ANONYMOUS_READ` | bool | False | Permit read access without authentication (discouraged) |
| `FAPILOG_SECURITY__ACCESS_CONTROL__ALLOW_ANONYMOUS_WRITE` | bool | False | Permit write access without authentication (never recommended) |
| `FAPILOG_SECURITY__ACCESS_CONTROL__AUTH_MODE` | Literal | token | Authentication mode used by integrations (library-agnostic) |
| `FAPILOG_SECURITY__ACCESS_CONTROL__ENABLED` | bool | True | Enable access control checks across the system |
| `FAPILOG_SECURITY__ACCESS_CONTROL__REQUIRE_ADMIN_FOR_SENSITIVE_OPS` | bool | True | Require admin role for sensitive or destructive operations |
| `FAPILOG_SECURITY__ENCRYPTION__ALGORITHM` | Literal | AES-256 | Primary encryption algorithm |
| `FAPILOG_SECURITY__ENCRYPTION__ENABLED` | bool | True | Enable encryption features |
| `FAPILOG_SECURITY__ENCRYPTION__ENV_VAR_NAME` | str | None | — | Environment variable holding key material |
| `FAPILOG_SECURITY__ENCRYPTION__KEY_FILE_PATH` | str | None | — | Filesystem path to key material |
| `FAPILOG_SECURITY__ENCRYPTION__KEY_ID` | str | None | — | Key identifier for KMS/Vault sources |
| `FAPILOG_SECURITY__ENCRYPTION__KEY_SOURCE` | Optional | — | Source for key material |
| `FAPILOG_SECURITY__ENCRYPTION__MIN_TLS_VERSION` | Literal | 1.2 | Minimum TLS version for transport |
| `FAPILOG_SECURITY__ENCRYPTION__ROTATE_INTERVAL_DAYS` | int | 90 | Recommended key rotation interval |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__BATCH_SIZE` | int | 100 | Events per batch |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__CIRCUIT_BREAKER_ENABLED` | bool | True | Enable internal circuit breaker for CloudWatch sink |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD` | int | 5 | Failures before opening circuit |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__CREATE_LOG_GROUP` | bool | True | Create log group if missing |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__CREATE_LOG_STREAM` | bool | True | Create log stream if missing |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__ENDPOINT_URL` | str | None | — | Custom endpoint (e.g., LocalStack) |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__LOG_GROUP_NAME` | str | /fapilog/default | CloudWatch log group name |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__LOG_STREAM_NAME` | str | None | — | CloudWatch log stream name |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__MAX_RETRIES` | int | 3 | Max retries for PutLogEvents |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__REGION` | str | None | — | AWS region for CloudWatch Logs API calls |
| `FAPILOG_SINK_CONFIG__CLOUDWATCH__RETRY_BASE_DELAY` | float | 0.5 | Base delay for exponential backoff. Accepts '1s' or 0.5 |
| `FAPILOG_SINK_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party sinks by name |
| `FAPILOG_SINK_CONFIG__HTTP__BATCH_FORMAT` | str | array | Batch format: 'array', 'ndjson', or 'wrapped' |
| `FAPILOG_SINK_CONFIG__HTTP__BATCH_SIZE` | int | 1 | Maximum events per HTTP request (1 = no batching) |
| `FAPILOG_SINK_CONFIG__HTTP__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_CONFIG__HTTP__BATCH_WRAPPER_KEY` | str | logs | Wrapper key when batch_format='wrapped' |
| `FAPILOG_SINK_CONFIG__HTTP__ENDPOINT` | str | None | — | HTTP endpoint to POST log events to |
| `FAPILOG_SINK_CONFIG__HTTP__HEADERS` | dict | PydanticUndefined | Default headers to send with each request |
| `FAPILOG_SINK_CONFIG__HTTP__HEADERS_JSON` | str | None | — | JSON-encoded headers map (e.g. '{"Authorization": "Bearer x"}') |
| `FAPILOG_SINK_CONFIG__HTTP__RETRY_BACKOFF_SECONDS` | float | None | — | Optional base backoff between retries. Accepts '2s' or 2.0 |
| `FAPILOG_SINK_CONFIG__HTTP__RETRY_MAX_ATTEMPTS` | int | None | — | Optional max attempts for HTTP retries |
| `FAPILOG_SINK_CONFIG__HTTP__TIMEOUT_SECONDS` | float | 5.0 | Request timeout for HTTP sink operations. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_CONFIG__LOKI__AUTH_PASSWORD` | str | None | — | Basic auth password |
| `FAPILOG_SINK_CONFIG__LOKI__AUTH_TOKEN` | str | None | — | Bearer token for Loki |
| `FAPILOG_SINK_CONFIG__LOKI__AUTH_USERNAME` | str | None | — | Basic auth username |
| `FAPILOG_SINK_CONFIG__LOKI__BATCH_SIZE` | int | 100 | Events per batch |
| `FAPILOG_SINK_CONFIG__LOKI__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_CONFIG__LOKI__CIRCUIT_BREAKER_ENABLED` | bool | True | Enable circuit breaker for the Loki sink |
| `FAPILOG_SINK_CONFIG__LOKI__CIRCUIT_BREAKER_THRESHOLD` | int | 5 | Failures before opening circuit |
| `FAPILOG_SINK_CONFIG__LOKI__LABELS` | dict | PydanticUndefined | Static labels to apply to each log stream |
| `FAPILOG_SINK_CONFIG__LOKI__LABEL_KEYS` | list | PydanticUndefined | Event keys to promote to labels |
| `FAPILOG_SINK_CONFIG__LOKI__MAX_RETRIES` | int | 3 | Max retries on push failure |
| `FAPILOG_SINK_CONFIG__LOKI__RETRY_BASE_DELAY` | float | 0.5 | Base delay for backoff. Accepts '1s' or 0.5 |
| `FAPILOG_SINK_CONFIG__LOKI__TENANT_ID` | str | None | — | Optional multi-tenant identifier |
| `FAPILOG_SINK_CONFIG__LOKI__TIMEOUT_SECONDS` | float | 10.0 | HTTP timeout seconds. Accepts '10s' or 10.0 |
| `FAPILOG_SINK_CONFIG__LOKI__URL` | str | http://localhost:3100 | Loki push endpoint base URL |
| `FAPILOG_SINK_CONFIG__POSTGRES__BATCH_SIZE` | int | 100 | Events per batch |
| `FAPILOG_SINK_CONFIG__POSTGRES__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_CONFIG__POSTGRES__CIRCUIT_BREAKER_ENABLED` | bool | True | Enable circuit breaker for the PostgreSQL sink |
| `FAPILOG_SINK_CONFIG__POSTGRES__CIRCUIT_BREAKER_THRESHOLD` | int | 5 | Failures before opening circuit breaker |
| `FAPILOG_SINK_CONFIG__POSTGRES__CREATE_TABLE` | bool | True | Auto-create table if missing |
| `FAPILOG_SINK_CONFIG__POSTGRES__DATABASE` | str | fapilog | PostgreSQL database name to connect to |
| `FAPILOG_SINK_CONFIG__POSTGRES__DSN` | str | None | — | PostgreSQL connection string |
| `FAPILOG_SINK_CONFIG__POSTGRES__EXTRACT_FIELDS` | list | PydanticUndefined | Fields to promote to columns for fast queries |
| `FAPILOG_SINK_CONFIG__POSTGRES__HOST` | str | localhost | PostgreSQL server hostname or IP address |
| `FAPILOG_SINK_CONFIG__POSTGRES__INCLUDE_RAW_JSON` | bool | True | Store full event JSON payload |
| `FAPILOG_SINK_CONFIG__POSTGRES__MAX_POOL_SIZE` | int | 10 | Maximum pool connections |
| `FAPILOG_SINK_CONFIG__POSTGRES__MAX_RETRIES` | int | 3 | Maximum retries for failed inserts |
| `FAPILOG_SINK_CONFIG__POSTGRES__MIN_POOL_SIZE` | int | 2 | Minimum pool connections |
| `FAPILOG_SINK_CONFIG__POSTGRES__PASSWORD` | str | None | — | Database password |
| `FAPILOG_SINK_CONFIG__POSTGRES__POOL_ACQUIRE_TIMEOUT` | float | 10.0 | Timeout when acquiring connections. Accepts '10s' or 10.0 |
| `FAPILOG_SINK_CONFIG__POSTGRES__PORT` | int | 5432 | PostgreSQL server port number |
| `FAPILOG_SINK_CONFIG__POSTGRES__RETRY_BASE_DELAY` | float | 0.5 | Base delay for exponential backoff. Accepts '1s' or 0.5 |
| `FAPILOG_SINK_CONFIG__POSTGRES__SCHEMA_NAME` | str | public | Database schema name |
| `FAPILOG_SINK_CONFIG__POSTGRES__TABLE_NAME` | str | logs | Target table name |
| `FAPILOG_SINK_CONFIG__POSTGRES__USER` | str | fapilog | PostgreSQL username for authentication |
| `FAPILOG_SINK_CONFIG__POSTGRES__USE_JSONB` | bool | True | Use JSONB column type |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__COMPRESS_ROTATED` | bool | False | Compress rotated log files with gzip |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__DIRECTORY` | str | None | — | Log directory for rotating file sink |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__FILENAME_PREFIX` | str | fapilog | Filename prefix |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__INTERVAL_SECONDS` | float | None | — | Rotation interval. Accepts '1h', 'daily', or 3600 |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES` | int | 10485760 | Max bytes before rotation. Accepts '10 MB' or 10485760 |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_FILES` | int | None | — | Max number of rotated files to keep |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_TOTAL_BYTES` | int | None | — | Max total bytes across all rotated files. Accepts '100 MB' or 104857600 |
| `FAPILOG_SINK_CONFIG__ROTATING_FILE__MODE` | Literal | json | Output format: json or text |
| `FAPILOG_SINK_CONFIG__SEALED__CHAIN_STATE_PATH` | str | None | — | Directory to persist chain state |
| `FAPILOG_SINK_CONFIG__SEALED__COMPRESS_ROTATED` | bool | False | Compress rotated files after sealing |
| `FAPILOG_SINK_CONFIG__SEALED__FSYNC_ON_ROTATE` | bool | True | Fsync inner sink after rotation |
| `FAPILOG_SINK_CONFIG__SEALED__FSYNC_ON_WRITE` | bool | False | Fsync inner sink on every write |
| `FAPILOG_SINK_CONFIG__SEALED__INNER_CONFIG` | dict | PydanticUndefined | Configuration for the inner sink |
| `FAPILOG_SINK_CONFIG__SEALED__INNER_SINK` | str | rotating_file | Inner sink to wrap with sealing |
| `FAPILOG_SINK_CONFIG__SEALED__KEY_ID` | str | None | — | Optional override for signing key identifier |
| `FAPILOG_SINK_CONFIG__SEALED__KEY_PROVIDER` | str | None | env | Key provider for manifest signing |
| `FAPILOG_SINK_CONFIG__SEALED__MANIFEST_PATH` | str | None | — | Directory where manifests are written |
| `FAPILOG_SINK_CONFIG__SEALED__ROTATE_CHAIN` | bool | False | Reset chain state on rotation |
| `FAPILOG_SINK_CONFIG__SEALED__SIGN_MANIFESTS` | bool | True | Sign manifests when keys are available |
| `FAPILOG_SINK_CONFIG__SEALED__USE_KMS_SIGNING` | bool | False | Sign manifests via external KMS provider |
| `FAPILOG_SINK_CONFIG__STDOUT_JSON` | dict | PydanticUndefined | Configuration for stdout_json sink |
| `FAPILOG_SINK_CONFIG__WEBHOOK__BATCH_SIZE` | int | 1 | Maximum events per webhook request (1 = no batching) |
| `FAPILOG_SINK_CONFIG__WEBHOOK__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial webhook batch. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_CONFIG__WEBHOOK__ENDPOINT` | str | None | — | Webhook destination URL |
| `FAPILOG_SINK_CONFIG__WEBHOOK__HEADERS` | dict | PydanticUndefined | Additional HTTP headers |
| `FAPILOG_SINK_CONFIG__WEBHOOK__RETRY_BACKOFF_SECONDS` | float | None | — | Backoff between retries. Accepts '2s' or 2.0 |
| `FAPILOG_SINK_CONFIG__WEBHOOK__RETRY_MAX_ATTEMPTS` | int | None | — | Maximum retry attempts on failure |
| `FAPILOG_SINK_CONFIG__WEBHOOK__SECRET` | str | None | — | Shared secret for signing |
| `FAPILOG_SINK_CONFIG__WEBHOOK__TIMEOUT_SECONDS` | float | 5.0 | Request timeout. Accepts '5s' or 5.0 |
| `FAPILOG_SINK_ROUTING__ENABLED` | bool | False | Enable routing (False = fanout to all sinks) |
| `FAPILOG_SINK_ROUTING__FALLBACK_SINKS` | list | PydanticUndefined | Sinks used when no rules match |
| `FAPILOG_SINK_ROUTING__OVERLAP` | bool | True | Allow events to match multiple rules |
| `FAPILOG_SINK_ROUTING__RULES` | list | PydanticUndefined | Routing rules in priority order |
