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
| `FAPILOG__CORE__ERROR_DEDUPE_WINDOW_SECONDS` | float | 5.0 | Seconds to suppress duplicate ERROR logs with the same message; 0 disables deduplication |
| `FAPILOG__CORE__EXCEPTIONS_ENABLED` | bool | True | Enable structured exception serialization for log calls |
| `FAPILOG__CORE__EXCEPTIONS_MAX_FRAMES` | int | 50 | Maximum number of stack frames to capture for exceptions |
| `FAPILOG__CORE__EXCEPTIONS_MAX_STACK_CHARS` | int | 20000 | Maximum total characters for serialized stack string |
| `FAPILOG__CORE__INTERNAL_LOGGING_ENABLED` | bool | False | Emit DEBUG/WARN diagnostics for internal errors |
| `FAPILOG__CORE__LOG_LEVEL` | Literal | INFO | Default log level |
| `FAPILOG__CORE__MAX_QUEUE_SIZE` | int | 10000 | Maximum in-memory queue size for async processing |
| `FAPILOG__CORE__REDACTION_MAX_DEPTH` | int | None | 6 | Optional max depth guardrail for nested redaction |
| `FAPILOG__CORE__REDACTION_MAX_KEYS_SCANNED` | int | None | 5000 | Optional max keys scanned guardrail for redaction |
| `FAPILOG__CORE__REDACTORS_ORDER` | list | PydanticUndefined | Ordered list of redactor plugin names to apply |
| `FAPILOG__CORE__RESOURCE_POOL_ACQUIRE_TIMEOUT_SECONDS` | float | 2.0 | Default acquire timeout for pools |
| `FAPILOG__CORE__RESOURCE_POOL_MAX_SIZE` | int | 8 | Default max size for resource pools |
| `FAPILOG__CORE__SENSITIVE_FIELDS_POLICY` | list | PydanticUndefined | Optional list of dotted paths for sensitive fields policy; warning if no redactors configured |
| `FAPILOG__CORE__SERIALIZE_IN_FLUSH` | bool | False | If True, pre-serialize envelopes once during flush and pass SerializedView to sinks that support write_serialized |
| `FAPILOG__CORE__SHUTDOWN_TIMEOUT_SECONDS` | float | 3.0 | Maximum time to flush on shutdown signals |
| `FAPILOG__CORE__STRICT_ENVELOPE_MODE` | bool | False | If True, drop emission when envelope cannot be produced; otherwise fallback to best-effort serialization with diagnostics |
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
| `FAPILOG__PLUGINS__ALLOWLIST` | list | PydanticUndefined | If non-empty, only plugin names in this list are considered during load |
| `FAPILOG__PLUGINS__DENYLIST` | list | PydanticUndefined | Plugin names to skip during discovery/load |
| `FAPILOG__PLUGINS__DISCOVERY_PATHS` | list | PydanticUndefined | Additional filesystem paths to scan for local plugins |
| `FAPILOG__PLUGINS__ENABLED` | bool | True | Enable plugin discovery and loading |
| `FAPILOG__PLUGINS__LOAD_ON_STARTUP` | list | PydanticUndefined | Plugins to eagerly load during registry.initialize() if discovered |
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
