<!-- AUTO-GENERATED: do not edit by hand. Run scripts/generate_env_matrix.py -->
# Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FAPILOG__CORE__APP_NAME` | str | fapilog | Logical application name |
| `FAPILOG__CORE__BACKPRESSURE_WAIT_MS` | int | 50 | Milliseconds to wait for queue space before dropping |
| `FAPILOG__CORE__BATCH_MAX_SIZE` | int | 256 | Maximum number of events per batch before a flush is triggered |
| `FAPILOG__CORE__BATCH_TIMEOUT_SECONDS` | float | 0.25 | Maximum time to wait before flushing a partial batch |
| `FAPILOG__CORE__BENCHMARK_FILE_PATH` | str | None | — | Optional path used by performance benchmarks |
| `FAPILOG__CORE__CAPTURE_UNHANDLED_ENABLED` | bool | False | Automatically install unhandled exception hooks (sys/asyncio) |
| `FAPILOG__CORE__CONTEXT_BINDING_ENABLED` | bool | True | Enable per-task bound context via logger.bind/unbind/clear |
| `FAPILOG__CORE__DEFAULT_BOUND_CONTEXT` | dict | PydanticUndefined | Default bound context applied at logger creation when enabled |
| `FAPILOG__CORE__DROP_ON_FULL` | bool | True | If True, drop events after backpressure_wait_ms elapses when queue is full |
| `FAPILOG__CORE__ENABLE_METRICS` | bool | False | Enable Prometheus-compatible metrics |
| `FAPILOG__CORE__ENABLE_REDACTORS` | bool | True | Enable redactors stage between enrichers and sink emission |
| `FAPILOG__CORE__ENRICHERS` | list | PydanticUndefined | Enricher plugins to use (by name) |
| `FAPILOG__CORE__ERROR_DEDUPE_WINDOW_SECONDS` | float | 5.0 | Seconds to suppress duplicate ERROR logs with the same message; 0 disables deduplication |
| `FAPILOG__CORE__EXCEPTIONS_ENABLED` | bool | True | Enable structured exception serialization for log calls |
| `FAPILOG__CORE__EXCEPTIONS_MAX_FRAMES` | int | 50 | Maximum number of stack frames to capture for exceptions |
| `FAPILOG__CORE__EXCEPTIONS_MAX_STACK_CHARS` | int | 20000 | Maximum total characters for serialized stack string |
| `FAPILOG__CORE__FILTERS` | list | PydanticUndefined | Filter plugins to apply before enrichment (by name) |
| `FAPILOG__CORE__INTERNAL_LOGGING_ENABLED` | bool | False | Emit DEBUG/WARN diagnostics for internal errors |
| `FAPILOG__CORE__LOG_LEVEL` | Literal | INFO | Default log level |
| `FAPILOG__CORE__MAX_QUEUE_SIZE` | int | 10000 | Maximum in-memory queue size for async processing |
| `FAPILOG__CORE__PROCESSORS` | list | PydanticUndefined | Processor plugins to use (by name) |
| `FAPILOG__CORE__REDACTION_MAX_DEPTH` | int | None | 6 | Optional max depth guardrail for nested redaction |
| `FAPILOG__CORE__REDACTION_MAX_KEYS_SCANNED` | int | None | 5000 | Optional max keys scanned guardrail for redaction |
| `FAPILOG__CORE__REDACTORS` | list | PydanticUndefined | Redactor plugins to use (by name); empty to disable |
| `FAPILOG__CORE__REDACTORS_ORDER` | list | PydanticUndefined | Ordered list of redactor plugin names to apply |
| `FAPILOG__CORE__RESOURCE_POOL_ACQUIRE_TIMEOUT_SECONDS` | float | 2.0 | Default acquire timeout for pools |
| `FAPILOG__CORE__RESOURCE_POOL_MAX_SIZE` | int | 8 | Default max size for resource pools |
| `FAPILOG__CORE__SENSITIVE_FIELDS_POLICY` | list | PydanticUndefined | Optional list of dotted paths for sensitive fields policy; warning if no redactors configured |
| `FAPILOG__CORE__SERIALIZE_IN_FLUSH` | bool | False | If True, pre-serialize envelopes once during flush and pass SerializedView to sinks that support write_serialized |
| `FAPILOG__CORE__SHUTDOWN_TIMEOUT_SECONDS` | float | 3.0 | Maximum time to flush on shutdown signals |
| `FAPILOG__CORE__SINKS` | list | PydanticUndefined | Sink plugins to use (by name); falls back to env-based default when empty |
| `FAPILOG__CORE__SINK_CIRCUIT_BREAKER_ENABLED` | bool | False | Enable circuit breaker for sink fault isolation |
| `FAPILOG__CORE__SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | int | 5 | Number of consecutive failures before opening circuit |
| `FAPILOG__CORE__SINK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS` | float | 30.0 | Seconds to wait before probing a failed sink |
| `FAPILOG__CORE__SINK_PARALLEL_WRITES` | bool | False | Write to multiple sinks in parallel instead of sequentially |
| `FAPILOG__CORE__STRICT_ENVELOPE_MODE` | bool | False | If True, drop emission when envelope cannot be produced; otherwise fallback to best-effort serialization with diagnostics |
| `FAPILOG__CORE__WORKER_COUNT` | int | 1 | Number of worker tasks for flush processing |
| `FAPILOG__ENRICHER_CONFIG__CONTEXT_VARS` | dict | PydanticUndefined | Configuration for context_vars enricher |
| `FAPILOG__ENRICHER_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party enrichers by name |
| `FAPILOG__ENRICHER_CONFIG__INTEGRITY__ALGORITHM` | Literal | sha256 | MAC or signature algorithm |
| `FAPILOG__ENRICHER_CONFIG__INTEGRITY__CHAIN_STATE_PATH` | str | None | — | Directory to persist chain state |
| `FAPILOG__ENRICHER_CONFIG__INTEGRITY__KEY_ID` | str | None | — | Key identifier used for MAC/signature |
| `FAPILOG__ENRICHER_CONFIG__INTEGRITY__KEY_PROVIDER` | str | None | env | Key provider for MAC/signature |
| `FAPILOG__ENRICHER_CONFIG__INTEGRITY__ROTATE_CHAIN` | bool | False | Reset chain after rotation |
| `FAPILOG__ENRICHER_CONFIG__INTEGRITY__USE_KMS_SIGNING` | bool | False | Sign integrity hashes via KMS provider |
| `FAPILOG__ENRICHER_CONFIG__RUNTIME_INFO` | dict | PydanticUndefined | Configuration for runtime_info enricher |
| `FAPILOG__FILTER_CONFIG__ADAPTIVE_SAMPLING` | dict | PydanticUndefined | Configuration for adaptive_sampling filter |
| `FAPILOG__FILTER_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party filters by name |
| `FAPILOG__FILTER_CONFIG__FIRST_OCCURRENCE` | dict | PydanticUndefined | Configuration for first_occurrence filter |
| `FAPILOG__FILTER_CONFIG__LEVEL` | dict | PydanticUndefined | Configuration for level filter |
| `FAPILOG__FILTER_CONFIG__RATE_LIMIT` | dict | PydanticUndefined | Configuration for rate_limit filter |
| `FAPILOG__FILTER_CONFIG__SAMPLING` | dict | PydanticUndefined | Configuration for sampling filter |
| `FAPILOG__FILTER_CONFIG__TRACE_SAMPLING` | dict | PydanticUndefined | Configuration for trace_sampling filter |
| `FAPILOG__HTTP__BATCH_FORMAT` | str | array | Batch format: 'array', 'ndjson', or 'wrapped' |
| `FAPILOG__HTTP__BATCH_SIZE` | int | 1 | Maximum events per HTTP request (1 = no batching) |
| `FAPILOG__HTTP__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch |
| `FAPILOG__HTTP__BATCH_WRAPPER_KEY` | str | logs | Wrapper key when batch_format='wrapped' |
| `FAPILOG__HTTP__ENDPOINT` | str | None | — | HTTP endpoint to POST log events to |
| `FAPILOG__HTTP__HEADERS` | dict | PydanticUndefined | Default headers to send with each request |
| `FAPILOG__HTTP__HEADERS_JSON` | str | None | — | JSON-encoded headers map (e.g. '{"Authorization": "Bearer x"}') |
| `FAPILOG__HTTP__RETRY_BACKOFF_SECONDS` | float | None | — | Optional base backoff seconds between retries |
| `FAPILOG__HTTP__RETRY_MAX_ATTEMPTS` | int | None | — | Optional max attempts for HTTP retries |
| `FAPILOG__HTTP__TIMEOUT_SECONDS` | float | 5.0 | Request timeout for HTTP sink operations |
| `FAPILOG__OBSERVABILITY__ALERTING__ENABLED` | bool | False | Enable emitting alerts from the logging pipeline |
| `FAPILOG__OBSERVABILITY__ALERTING__MIN_SEVERITY` | Literal | ERROR | Minimum alert severity to emit (filter threshold) |
| `FAPILOG__OBSERVABILITY__LOGGING__FORMAT` | Literal | json | Output format for logs (machine-friendly JSON or text) |
| `FAPILOG__OBSERVABILITY__LOGGING__INCLUDE_CORRELATION` | bool | True | Include correlation IDs and trace/span metadata in logs |
| `FAPILOG__OBSERVABILITY__LOGGING__SAMPLING_RATE` | float | 1.0 | Log sampling probability in range 0.0–1.0 |
| `FAPILOG__OBSERVABILITY__METRICS__ENABLED` | bool | False | Enable internal metrics collection/export |
| `FAPILOG__OBSERVABILITY__METRICS__EXPORTER` | Literal | prometheus | Metrics exporter to use ('prometheus' or 'none') |
| `FAPILOG__OBSERVABILITY__METRICS__PORT` | int | 8000 | TCP port for metrics exporter |
| `FAPILOG__OBSERVABILITY__MONITORING__ENABLED` | bool | False | Enable health/monitoring checks and endpoints |
| `FAPILOG__OBSERVABILITY__MONITORING__ENDPOINT` | str | None | — | Monitoring endpoint URL |
| `FAPILOG__OBSERVABILITY__TRACING__ENABLED` | bool | False | Enable distributed tracing features |
| `FAPILOG__OBSERVABILITY__TRACING__PROVIDER` | Literal | otel | Tracing backend provider ('otel' or 'none') |
| `FAPILOG__OBSERVABILITY__TRACING__SAMPLING_RATE` | float | 0.1 | Trace sampling probability in range 0.0–1.0 |
| `FAPILOG__PLUGINS__ALLOWLIST` | list | PydanticUndefined | If non-empty, only these plugin names are allowed |
| `FAPILOG__PLUGINS__DENYLIST` | list | PydanticUndefined | Plugin names to block from loading |
| `FAPILOG__PLUGINS__ENABLED` | bool | True | Enable plugin loading |
| `FAPILOG__PLUGINS__VALIDATION_MODE` | str | disabled | Plugin validation mode: disabled, warn, or strict |
| `FAPILOG__PROCESSOR_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party processors by name |
| `FAPILOG__PROCESSOR_CONFIG__ZERO_COPY` | dict | PydanticUndefined | Configuration for zero_copy processor (reserved for future options) |
| `FAPILOG__REDACTOR_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party redactors by name |
| `FAPILOG__REDACTOR_CONFIG__FIELD_MASK__BLOCK_ON_UNREDACTABLE` | bool | False | Block log entry if redaction fails |
| `FAPILOG__REDACTOR_CONFIG__FIELD_MASK__FIELDS_TO_MASK` | list | PydanticUndefined | Field names to mask (case-insensitive) |
| `FAPILOG__REDACTOR_CONFIG__FIELD_MASK__MASK_STRING` | str | *** | Replacement mask string |
| `FAPILOG__REDACTOR_CONFIG__FIELD_MASK__MAX_DEPTH` | int | 16 | Max nested depth to scan |
| `FAPILOG__REDACTOR_CONFIG__FIELD_MASK__MAX_KEYS_SCANNED` | int | 1000 | Max keys to scan before stopping |
| `FAPILOG__REDACTOR_CONFIG__REGEX_MASK__BLOCK_ON_UNREDACTABLE` | bool | False | Block log entry if redaction fails |
| `FAPILOG__REDACTOR_CONFIG__REGEX_MASK__MASK_STRING` | str | *** | Replacement mask string |
| `FAPILOG__REDACTOR_CONFIG__REGEX_MASK__MAX_DEPTH` | int | 16 | Max nested depth to scan |
| `FAPILOG__REDACTOR_CONFIG__REGEX_MASK__MAX_KEYS_SCANNED` | int | 1000 | Max keys to scan before stopping |
| `FAPILOG__REDACTOR_CONFIG__REGEX_MASK__PATTERNS` | list | PydanticUndefined | Regex patterns to match and mask |
| `FAPILOG__REDACTOR_CONFIG__URL_CREDENTIALS__MAX_STRING_LENGTH` | int | 4096 | Max string length to parse for URL credentials |
| `FAPILOG__SCHEMA_VERSION` | str | 1.0 | Configuration schema version for forward/backward compatibility |
| `FAPILOG__SECURITY__ACCESS_CONTROL__ALLOWED_ROLES` | list | PydanticUndefined | List of roles granted access to protected operations |
| `FAPILOG__SECURITY__ACCESS_CONTROL__ALLOW_ANONYMOUS_READ` | bool | False | Permit read access without authentication (discouraged) |
| `FAPILOG__SECURITY__ACCESS_CONTROL__ALLOW_ANONYMOUS_WRITE` | bool | False | Permit write access without authentication (never recommended) |
| `FAPILOG__SECURITY__ACCESS_CONTROL__AUTH_MODE` | Literal | token | Authentication mode used by integrations (library-agnostic) |
| `FAPILOG__SECURITY__ACCESS_CONTROL__ENABLED` | bool | True | Enable access control checks across the system |
| `FAPILOG__SECURITY__ACCESS_CONTROL__REQUIRE_ADMIN_FOR_SENSITIVE_OPS` | bool | True | Require admin role for sensitive or destructive operations |
| `FAPILOG__SECURITY__ENCRYPTION__ALGORITHM` | Literal | AES-256 | Primary encryption algorithm |
| `FAPILOG__SECURITY__ENCRYPTION__ENABLED` | bool | True | Enable encryption features |
| `FAPILOG__SECURITY__ENCRYPTION__ENV_VAR_NAME` | str | None | — | Environment variable holding key material |
| `FAPILOG__SECURITY__ENCRYPTION__KEY_FILE_PATH` | str | None | — | Filesystem path to key material |
| `FAPILOG__SECURITY__ENCRYPTION__KEY_ID` | str | None | — | Key identifier for KMS/Vault sources |
| `FAPILOG__SECURITY__ENCRYPTION__KEY_SOURCE` | Optional | — | Source for key material |
| `FAPILOG__SECURITY__ENCRYPTION__MIN_TLS_VERSION` | Literal | 1.2 | Minimum TLS version for transport |
| `FAPILOG__SECURITY__ENCRYPTION__ROTATE_INTERVAL_DAYS` | int | 90 | Recommended key rotation interval |
| `FAPILOG__SINK_CONFIG__EXTRA` | dict | PydanticUndefined | Configuration for third-party sinks by name |
| `FAPILOG__SINK_CONFIG__HTTP__BATCH_FORMAT` | str | array | Batch format: 'array', 'ndjson', or 'wrapped' |
| `FAPILOG__SINK_CONFIG__HTTP__BATCH_SIZE` | int | 1 | Maximum events per HTTP request (1 = no batching) |
| `FAPILOG__SINK_CONFIG__HTTP__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial batch |
| `FAPILOG__SINK_CONFIG__HTTP__BATCH_WRAPPER_KEY` | str | logs | Wrapper key when batch_format='wrapped' |
| `FAPILOG__SINK_CONFIG__HTTP__ENDPOINT` | str | None | — | HTTP endpoint to POST log events to |
| `FAPILOG__SINK_CONFIG__HTTP__HEADERS` | dict | PydanticUndefined | Default headers to send with each request |
| `FAPILOG__SINK_CONFIG__HTTP__HEADERS_JSON` | str | None | — | JSON-encoded headers map (e.g. '{"Authorization": "Bearer x"}') |
| `FAPILOG__SINK_CONFIG__HTTP__RETRY_BACKOFF_SECONDS` | float | None | — | Optional base backoff seconds between retries |
| `FAPILOG__SINK_CONFIG__HTTP__RETRY_MAX_ATTEMPTS` | int | None | — | Optional max attempts for HTTP retries |
| `FAPILOG__SINK_CONFIG__HTTP__TIMEOUT_SECONDS` | float | 5.0 | Request timeout for HTTP sink operations |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__COMPRESS_ROTATED` | bool | False | Compress rotated log files with gzip |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__DIRECTORY` | str | None | — | Log directory for rotating file sink |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__FILENAME_PREFIX` | str | fapilog | Filename prefix |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__INTERVAL_SECONDS` | int | None | — | Rotation interval in seconds (optional) |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__MAX_BYTES` | int | 10485760 | Max bytes before rotation |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__MAX_FILES` | int | None | — | Max number of rotated files to keep |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__MAX_TOTAL_BYTES` | int | None | — | Max total bytes across all rotated files |
| `FAPILOG__SINK_CONFIG__ROTATING_FILE__MODE` | Literal | json | Output format: json or text |
| `FAPILOG__SINK_CONFIG__SEALED__CHAIN_STATE_PATH` | str | None | — | Directory to persist chain state |
| `FAPILOG__SINK_CONFIG__SEALED__COMPRESS_ROTATED` | bool | False | Compress rotated files after sealing |
| `FAPILOG__SINK_CONFIG__SEALED__FSYNC_ON_ROTATE` | bool | True | Fsync inner sink after rotation |
| `FAPILOG__SINK_CONFIG__SEALED__FSYNC_ON_WRITE` | bool | False | Fsync inner sink on every write |
| `FAPILOG__SINK_CONFIG__SEALED__INNER_CONFIG` | dict | PydanticUndefined | Configuration for the inner sink |
| `FAPILOG__SINK_CONFIG__SEALED__INNER_SINK` | str | rotating_file | Inner sink to wrap with sealing |
| `FAPILOG__SINK_CONFIG__SEALED__KEY_ID` | str | None | — | Optional override for signing key identifier |
| `FAPILOG__SINK_CONFIG__SEALED__KEY_PROVIDER` | str | None | env | Key provider for manifest signing |
| `FAPILOG__SINK_CONFIG__SEALED__MANIFEST_PATH` | str | None | — | Directory where manifests are written |
| `FAPILOG__SINK_CONFIG__SEALED__ROTATE_CHAIN` | bool | False | Reset chain state on rotation |
| `FAPILOG__SINK_CONFIG__SEALED__SIGN_MANIFESTS` | bool | True | Sign manifests when keys are available |
| `FAPILOG__SINK_CONFIG__SEALED__USE_KMS_SIGNING` | bool | False | Sign manifests via external KMS provider |
| `FAPILOG__SINK_CONFIG__STDOUT_JSON` | dict | PydanticUndefined | Configuration for stdout_json sink |
| `FAPILOG__SINK_CONFIG__WEBHOOK__BATCH_SIZE` | int | 1 | Maximum events per webhook request (1 = no batching) |
| `FAPILOG__SINK_CONFIG__WEBHOOK__BATCH_TIMEOUT_SECONDS` | float | 5.0 | Max seconds before flushing a partial webhook batch |
| `FAPILOG__SINK_CONFIG__WEBHOOK__ENDPOINT` | str | None | — | Webhook destination URL |
| `FAPILOG__SINK_CONFIG__WEBHOOK__HEADERS` | dict | PydanticUndefined | Additional HTTP headers |
| `FAPILOG__SINK_CONFIG__WEBHOOK__RETRY_BACKOFF_SECONDS` | float | None | — | Backoff between retries in seconds |
| `FAPILOG__SINK_CONFIG__WEBHOOK__RETRY_MAX_ATTEMPTS` | int | None | — | Maximum retry attempts on failure |
| `FAPILOG__SINK_CONFIG__WEBHOOK__SECRET` | str | None | — | Shared secret for signing |
| `FAPILOG__SINK_CONFIG__WEBHOOK__TIMEOUT_SECONDS` | float | 5.0 | Request timeout in seconds |
