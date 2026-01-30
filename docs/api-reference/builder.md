# Builder API Reference

The `LoggerBuilder` and `AsyncLoggerBuilder` classes provide a fluent API for configuring fapilog loggers. All configuration methods return `self` for chaining.

## Overview

The Builder API offers an alternative to Settings-based configuration with these advantages:

- **Discoverability** - IDE autocomplete shows all available options
- **Validation** - Errors caught at build time with clear messages
- **Readability** - Configuration intent is clear from method names
- **Type Safety** - Full type hints for all parameters

## Quick Start

```python
from fapilog import LoggerBuilder

# Minimal setup
logger = LoggerBuilder().add_stdout().build()

# Production setup
logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_level("INFO")
    .add_file("logs/app", max_bytes="100 MB", max_files=10)
    .with_circuit_breaker(enabled=True)
    .build()
)
```

For async applications:

```python
from fapilog import AsyncLoggerBuilder

logger = await (
    AsyncLoggerBuilder()
    .with_preset("fastapi")
    .add_stdout()
    .build_async()
)
```

---

## Core Configuration

### with_name(name)

Set the logger name for identification and caching.

**Parameters:**
- `name` (str): Logger name

**Returns:** `Self`

**Example:**
```python
builder.with_name("my-service")
```

**Equivalent Settings:**
```python
get_logger(name="my-service")
```

---

### with_level(level)

Set the minimum log level. Events below this level are filtered.

**Parameters:**
- `level` (str): Log level - `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`

**Returns:** `Self`

**Example:**
```python
builder.with_level("INFO")
```

**Equivalent Settings:**
```python
Settings(core=CoreSettings(log_level="INFO"))
```

---

### with_preset(preset)

Apply a preset configuration. Preset is applied first, then subsequent methods override specific values.

**Parameters:**
- `preset` (str): Preset name - `"dev"`, `"production"`, `"fastapi"`, `"minimal"`

**Returns:** `Self`

**Raises:**
- `ValueError`: If a preset is already set

**Example:**
```python
builder.with_preset("production")
```

**Preset Summary:**

| Preset | Log Level | File Logging | Redaction | Batch Size | Workers |
|--------|-----------|--------------|-----------|------------|---------|
| `dev` | DEBUG | No | No | 1 (immediate) | 1 |
| `production` | INFO | Yes (50MB rotation) | Yes | 100 | 2 |
| `fastapi` | INFO | No | Yes | 50 | 2 |
| `serverless` | INFO | No | Yes | 25 | 2 |
| `hardened` | INFO | Yes (50MB rotation) | Yes | 100 | 2 |
| `minimal` | INFO | No | No | 256 | 1 |

> **Performance note:** Production-oriented presets use 2 workers for ~30x better throughput. See [Performance Tuning](../user-guide/performance-tuning.md) for details.

---

### with_app_name(name)

Set application name for log identification.

**Parameters:**
- `name` (str): Application name

**Returns:** `Self`

**Example:**
```python
builder.with_app_name("my-service")
```

**Equivalent Settings:**
```python
Settings(core=CoreSettings(app_name="my-service"))
```

---

## Sinks

### add_stdout(format="json")

Add stdout sink with JSON or pretty output.

**Parameters:**
- `format` (str): Output format - `"json"` (default) or `"pretty"`

**Returns:** `Self`

**Example:**
```python
builder.add_stdout()  # JSON output
builder.add_stdout(format="pretty")  # Human-readable output
```

**Equivalent Settings:**
```python
Settings(core=CoreSettings(sinks=["stdout_json"]))
Settings(core=CoreSettings(sinks=["stdout_pretty"]))
```

---

### add_stdout_pretty()

Convenience method for pretty-formatted stdout (equivalent to `add_stdout(format="pretty")`).

**Returns:** `Self`

**Example:**
```python
builder.add_stdout_pretty()
```

---

### add_file(directory, *, max_bytes="10 MB", interval=None, max_files=None, compress=False)

Add rotating file sink.

**Parameters:**
- `directory` (str): Log directory (required)
- `max_bytes` (str | int): Max bytes before rotation (supports `"10 MB"` strings)
- `interval` (str | int | None): Rotation interval (supports `"daily"`, `"1h"` strings)
- `max_files` (int | None): Max rotated files to keep
- `compress` (bool): Compress rotated files with gzip

**Returns:** `Self`

**Raises:**
- `ValueError`: If directory is empty

**Example:**
```python
builder.add_file(
    "logs/app",
    max_bytes="50 MB",
    max_files=10,
    compress=True,
)
```

**Equivalent Settings:**
```python
Settings(
    core=CoreSettings(sinks=["rotating_file"]),
    sink_config=SinkConfig(
        rotating_file=RotatingFileSinkSettings(
            directory="logs/app",
            max_bytes="50 MB",
            max_files=10,
            compress_rotated=True,
        )
    ),
)
```

---

### add_http(endpoint, *, timeout="30s", headers=None)

Add HTTP sink for sending logs to a remote endpoint.

**Parameters:**
- `endpoint` (str): HTTP endpoint URL (required)
- `timeout` (str | float): Request timeout (supports `"30s"` strings)
- `headers` (dict[str, str] | None): Additional HTTP headers

**Returns:** `Self`

**Raises:**
- `ValueError`: If endpoint is empty

**Example:**
```python
builder.add_http(
    "https://logs.example.com/ingest",
    timeout="10s",
    headers={"Authorization": "Bearer token"},
)
```

---

### add_webhook(endpoint, *, secret=None, timeout="5s", headers=None)

Add webhook sink with optional HMAC signing.

**Parameters:**
- `endpoint` (str): Webhook destination URL (required)
- `secret` (str | None): Shared secret for HMAC signing
- `timeout` (str | float): Request timeout (supports `"5s"` strings)
- `headers` (dict[str, str] | None): Additional HTTP headers

**Returns:** `Self`

**Raises:**
- `ValueError`: If endpoint is empty

**Example:**
```python
builder.add_webhook(
    "https://alerts.example.com/webhook",
    secret="my-signing-secret",
)
```

---

### add_cloudwatch(log_group, *, stream=None, region=None, endpoint_url=None, batch_size=100, batch_timeout="5s", max_retries=3, retry_delay=0.5, create_group=True, create_stream=True, circuit_breaker=True, circuit_breaker_threshold=5)

Add AWS CloudWatch Logs sink.

**Parameters:**
- `log_group` (str): CloudWatch log group name (required)
- `stream` (str | None): Log stream name (auto-generated if not provided)
- `region` (str | None): AWS region (uses default if not provided)
- `endpoint_url` (str | None): Custom endpoint (e.g., LocalStack)
- `batch_size` (int): Events per batch (default: 100)
- `batch_timeout` (str | float): Batch flush timeout
- `max_retries` (int): Max retries for PutLogEvents (default: 3)
- `retry_delay` (str | float): Base delay for exponential backoff
- `create_group` (bool): Create log group if missing (default: True)
- `create_stream` (bool): Create log stream if missing (default: True)
- `circuit_breaker` (bool): Enable circuit breaker (default: True)
- `circuit_breaker_threshold` (int): Failures before opening (default: 5)

**Returns:** `Self`

**Example:**
```python
builder.add_cloudwatch(
    "/myapp/prod",
    region="us-east-1",
    batch_size=200,
)
```

**Equivalent Settings:**
```python
Settings(
    core=CoreSettings(sinks=["cloudwatch"]),
    sink_config=SinkConfig(
        cloudwatch=CloudWatchSinkSettings(
            log_group_name="/myapp/prod",
            region="us-east-1",
            batch_size=200,
        )
    ),
)
```

---

### add_loki(url="http://localhost:3100", *, tenant_id=None, labels=None, label_keys=None, batch_size=100, batch_timeout="5s", timeout="10s", max_retries=3, retry_delay=0.5, auth_username=None, auth_password=None, auth_token=None, circuit_breaker=True, circuit_breaker_threshold=5)

Add Grafana Loki sink.

**Parameters:**
- `url` (str): Loki push endpoint (default: `http://localhost:3100`)
- `tenant_id` (str | None): Multi-tenant identifier
- `labels` (dict[str, str] | None): Static labels for log streams
- `label_keys` (list[str] | None): Event keys to promote to labels
- `batch_size` (int): Events per batch (default: 100)
- `batch_timeout` (str | float): Batch flush timeout
- `timeout` (str | float): HTTP request timeout
- `max_retries` (int): Max retries on failure (default: 3)
- `retry_delay` (str | float): Base delay for exponential backoff
- `auth_username` (str | None): Basic auth username
- `auth_password` (str | None): Basic auth password
- `auth_token` (str | None): Bearer token
- `circuit_breaker` (bool): Enable circuit breaker (default: True)
- `circuit_breaker_threshold` (int): Failures before opening (default: 5)

**Returns:** `Self`

**Example:**
```python
builder.add_loki(
    "http://loki:3100",
    tenant_id="myapp",
    labels={"env": "production", "service": "api"},
)
```

---

### add_postgres(dsn=None, *, host="localhost", port=5432, database="fapilog", user="fapilog", password=None, table="logs", schema="public", batch_size=100, batch_timeout="5s", max_retries=3, retry_delay=0.5, min_pool=2, max_pool=10, pool_acquire_timeout="10s", create_table=True, use_jsonb=True, include_raw_json=None, extract_fields=None, circuit_breaker=True, circuit_breaker_threshold=5)

Add PostgreSQL sink for structured log storage.

**Parameters:**
- `dsn` (str | None): Full connection string (overrides host/port/database/user/password)
- `host` (str): Database host (default: `localhost`)
- `port` (int): Database port (default: 5432)
- `database` (str): Database name (default: `fapilog`)
- `user` (str): Database user (default: `fapilog`)
- `password` (str | None): Database password
- `table` (str): Target table name (default: `logs`)
- `schema` (str): Database schema (default: `public`)
- `batch_size` (int): Events per batch (default: 100)
- `batch_timeout` (str | float): Batch flush timeout
- `max_retries` (int): Max retries on failure (default: 3)
- `retry_delay` (str | float): Base delay for exponential backoff
- `min_pool` (int): Minimum pool connections (default: 2)
- `max_pool` (int): Maximum pool connections (default: 10)
- `pool_acquire_timeout` (str | float): Timeout for acquiring connections
- `create_table` (bool): Auto-create table if missing (default: True)
- `use_jsonb` (bool): Use JSONB column type (default: True)
- `include_raw_json` (bool | None): Store full event JSON payload
- `extract_fields` (list[str] | None): Fields to promote to columns
- `circuit_breaker` (bool): Enable circuit breaker (default: True)
- `circuit_breaker_threshold` (int): Failures before opening (default: 5)

**Returns:** `Self`

**Example:**
```python
builder.add_postgres(
    dsn="postgresql://user:pass@db.example.com/logs",
)
# Or with individual parameters:
builder.add_postgres(
    host="db.example.com",
    database="logs",
    user="fapilog",
    password="secret",
)
```

---

## Filters

### with_filters(*filters)

Enable filters by name.

**Parameters:**
- `*filters` (str): Filter names (e.g., `"level"`, `"sampling"`)

**Returns:** `Self`

**Example:**
```python
builder.with_filters("level", "sampling")
```

---

### with_sampling(rate=1.0, *, seed=None)

Configure probabilistic sampling filter.

**Parameters:**
- `rate` (float): Sample rate 0.0-1.0 (1.0 = keep all, 0.1 = keep 10%)
- `seed` (int | None): Random seed for reproducibility

**Returns:** `Self`

**Example:**
```python
builder.with_sampling(rate=0.1)  # Keep 10% of logs
```

**Equivalent Settings:**
```python
Settings(
    core=CoreSettings(filters=["sampling"]),
    filter_config=FilterConfig(
        sampling=SamplingFilterSettings(sample_rate=0.1)
    ),
)
```

---

### with_adaptive_sampling(min_rate=0.01, max_rate=1.0, *, target_events_per_sec=1000.0, window_seconds=60.0)

Configure adaptive sampling that adjusts rate based on event volume.

**Parameters:**
- `min_rate` (float): Minimum sample rate (default: 0.01)
- `max_rate` (float): Maximum sample rate (default: 1.0)
- `target_events_per_sec` (float): Target event throughput (default: 1000)
- `window_seconds` (float): Measurement window (default: 60)

**Returns:** `Self`

**Example:**
```python
builder.with_adaptive_sampling(target_events_per_sec=500)
```

---

### with_trace_sampling(default_rate=1.0, *, honor_upstream=True)

Configure distributed trace-aware sampling.

**Parameters:**
- `default_rate` (float): Default sample rate when no trace context (default: 1.0)
- `honor_upstream` (bool): Honor upstream sampling decisions (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_trace_sampling(default_rate=0.1)
```

---

### with_rate_limit(capacity=10, *, refill_rate=5.0, key_field=None, max_keys=10000, overflow_action="drop")

Configure token bucket rate limiting filter.

**Parameters:**
- `capacity` (int): Token bucket capacity (default: 10)
- `refill_rate` (float): Tokens refilled per second (default: 5.0)
- `key_field` (str | None): Event field for partitioning buckets
- `max_keys` (int): Maximum buckets to track (default: 10000)
- `overflow_action` (str): Action on overflow - `"drop"` or `"mark"`

**Returns:** `Self`

**Example:**
```python
builder.with_rate_limit(capacity=100, refill_rate=10.0)
```

---

### with_first_occurrence(window_seconds=300.0, *, max_entries=10000, key_fields=None)

Configure first-occurrence deduplication filter.

**Parameters:**
- `window_seconds` (float): Deduplication window (default: 300 = 5 minutes)
- `max_entries` (int): Maximum tracked messages (default: 10000)
- `key_fields` (list[str] | None): Fields to use as dedup key

**Returns:** `Self`

**Example:**
```python
builder.with_first_occurrence(window_seconds=60)
```

---

## Processors

### with_size_guard(max_bytes="256 KB", *, action="truncate", preserve_fields=None)

Configure payload size limiting processor.

**Parameters:**
- `max_bytes` (str | int): Maximum payload size (supports `"256 KB"` strings)
- `action` (str): Action on oversized payloads - `"truncate"`, `"drop"`, `"warn"`
- `preserve_fields` (list[str] | None): Fields to never remove during truncation

**Returns:** `Self`

**Example:**
```python
builder.with_size_guard(max_bytes="1 MB", action="truncate")
```

---

## Redaction

### with_redaction(*, fields=None, patterns=None)

Configure redaction with field names and/or regex patterns.

**Parameters:**
- `fields` (list[str] | None): Field names to redact (e.g., `["password", "ssn"]`)
- `patterns` (list[str] | None): Regex patterns to redact

**Returns:** `Self`

**Example:**
```python
builder.with_redaction(
    fields=["password", "api_key"],
    patterns=["(?i)secret.*"],
)
```

---

### with_field_mask(fields, *, mask="***", block_on_failure=False, max_depth=16, max_keys=1000)

Configure field-based redaction with full control.

**Parameters:**
- `fields` (list[str]): Field paths to mask (e.g., `["password", "user.ssn"]`)
- `mask` (str): Replacement string (default: `"***"`)
- `block_on_failure` (bool): Block log entry if redaction fails
- `max_depth` (int): Maximum nested depth to scan (default: 16)
- `max_keys` (int): Maximum keys to scan (default: 1000)

**Returns:** `Self`

**Example:**
```python
builder.with_field_mask(
    ["password", "api_key"],
    mask="[REDACTED]",
)
```

---

### with_regex_mask(patterns, *, mask="***", block_on_failure=False, max_depth=16, max_keys=1000)

Configure regex-based field path redaction.

**Note:** Patterns match field **paths** (e.g., `"context.password"`), not field content.

**Parameters:**
- `patterns` (list[str]): Regex patterns to match against field paths
- `mask` (str): Replacement string (default: `"***"`)
- `block_on_failure` (bool): Block log entry if redaction fails
- `max_depth` (int): Maximum nested depth to scan (default: 16)
- `max_keys` (int): Maximum keys to scan (default: 1000)

**Returns:** `Self`

**Example:**
```python
builder.with_regex_mask(["(?i).*password.*", "(?i).*secret.*"])
```

---

### with_url_credential_redaction(*, enabled=True, max_string_length=4096)

Configure URL credential redaction.

Scrubs credentials from URLs like `https://user:pass@host/...`

**Parameters:**
- `enabled` (bool): Enable URL credential redaction (default: True)
- `max_string_length` (int): Max string length to parse (default: 4096)

**Returns:** `Self`

**Example:**
```python
builder.with_url_credential_redaction(max_string_length=8192)
```

---

### with_redaction_guardrails(*, max_depth=6, max_keys=5000)

Configure global redaction guardrails.

**Parameters:**
- `max_depth` (int): Maximum nested depth for redaction (default: 6)
- `max_keys` (int): Maximum keys scanned during redaction (default: 5000)

**Returns:** `Self`

**Example:**
```python
builder.with_redaction_guardrails(max_depth=10, max_keys=10000)
```

---

## Performance & Reliability

### with_queue_size(size)

Set maximum queue size for buffering log events.

**Parameters:**
- `size` (int): Maximum queue size

**Returns:** `Self`

**Example:**
```python
builder.with_queue_size(10000)
```

---

### with_batch_size(size)

Set batch max size for sink writes.

**Parameters:**
- `size` (int): Maximum batch size

**Returns:** `Self`

**Example:**
```python
builder.with_batch_size(100)
```

---

### with_batch_timeout(timeout)

Set batch timeout for sink writes.

**Parameters:**
- `timeout` (str | float): Batch timeout (supports `"1s"`, `"500ms"` strings)

**Returns:** `Self`

**Example:**
```python
builder.with_batch_timeout("500ms")
```

---

### with_workers(count=1)

Set number of worker tasks for flush processing.

**Parameters:**
- `count` (int): Number of workers (default: 1)

**Returns:** `Self`

**Performance impact:** Worker count has the largest impact on throughput:

| Workers | Throughput |
|---------|------------|
| 1 | ~3,500/sec |
| 2 | ~105,000/sec (+30x) |

**Recommendation:** Use 2 workers for production. Production-oriented presets (`production`, `fastapi`, `serverless`, `hardened`) default to 2 workers automatically.

**Example:**
```python
builder.with_workers(count=2)  # Recommended for production
```

**Equivalent Settings:**
```python
Settings(core=CoreSettings(worker_count=2))
```

---

### with_circuit_breaker(*, enabled=True, failure_threshold=5, recovery_timeout="30s")

Configure sink circuit breaker for fault isolation.

**Parameters:**
- `enabled` (bool): Enable circuit breaker (default: True)
- `failure_threshold` (int): Consecutive failures before opening circuit
- `recovery_timeout` (str | float): Time before probing failed sink

**Returns:** `Self`

**Example:**
```python
builder.with_circuit_breaker(enabled=True, failure_threshold=3)
```

**Equivalent Settings:**
```python
Settings(
    core=CoreSettings(
        sink_circuit_breaker_enabled=True,
        sink_circuit_breaker_failure_threshold=3,
        sink_circuit_breaker_recovery_timeout_seconds=30.0,
    )
)
```

---

### with_backpressure(*, wait_ms=50, drop_on_full=True)

Configure queue backpressure behavior.

**Parameters:**
- `wait_ms` (int): Milliseconds to wait for queue space (default: 50)
- `drop_on_full` (bool): Drop events if queue still full after wait (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_backpressure(wait_ms=100, drop_on_full=False)
```

---

### with_shutdown_timeout(timeout="3s")

Set maximum time to flush on shutdown.

**Parameters:**
- `timeout` (str | float): Shutdown timeout

**Returns:** `Self`

**Example:**
```python
builder.with_shutdown_timeout("5s")
```

---

### with_parallel_sink_writes(enabled=True)

Enable parallel writes to multiple sinks.

**Parameters:**
- `enabled` (bool): Write to sinks in parallel (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_parallel_sink_writes(enabled=True)
```

---

## Routing

### with_routing(rules, *, fallback=None, overlap=True)

Configure level-based sink routing.

**Parameters:**
- `rules` (list[dict[str, Any]]): List of routing rules, each with `"levels"` and `"sinks"` keys
- `fallback` (list[str] | None): Sinks to use when no rules match
- `overlap` (bool): Allow events to match multiple rules (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_routing(
    rules=[
        {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
        {"levels": ["INFO", "DEBUG"], "sinks": ["file"]},
    ],
    fallback=["stdout_json"],
)
```

---

## Enrichers

### with_enrichers(*enrichers)

Enable enrichers by name.

**Parameters:**
- `*enrichers` (str): Enricher names (e.g., `"runtime_info"`, `"context_vars"`)

**Returns:** `Self`

**Example:**
```python
builder.with_enrichers("runtime_info", "context_vars")
```

---

### configure_enricher(name, **config)

Configure a specific enricher.

**Parameters:**
- `name` (str): Enricher name
- `**config` (Any): Enricher-specific configuration

**Returns:** `Self`

**Example:**
```python
builder.configure_enricher("runtime_info", service="my-api")
```

---

### with_context(**kwargs)

Set default bound context for all log entries.

**Parameters:**
- `**kwargs` (object): Context key-value pairs

**Returns:** `Self`

**Example:**
```python
builder.with_context(service="api", environment="production")
```

---

## Advanced Configuration

### with_exceptions(*, enabled=True, max_frames=10, max_stack_chars=20000)

Configure exception serialization.

**Parameters:**
- `enabled` (bool): Enable structured exception capture (default: True)
- `max_frames` (int): Maximum stack frames to capture (default: 10)
- `max_stack_chars` (int): Maximum total stack string length (default: 20000)

**Returns:** `Self`

**Example:**
```python
builder.with_exceptions(max_frames=20)
```

---

### with_metrics(enabled=True)

Enable Prometheus-compatible metrics.

**Parameters:**
- `enabled` (bool): Enable metrics collection (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_metrics(enabled=True)
```

---

### with_error_deduplication(window_seconds=5.0)

Configure error log deduplication.

**Parameters:**
- `window_seconds` (float): Seconds to suppress duplicate errors (0 disables)

**Returns:** `Self`

**Example:**
```python
builder.with_error_deduplication(window_seconds=10.0)
```

---

### with_diagnostics(*, enabled=True, output="stderr")

Configure internal diagnostics output.

**Parameters:**
- `enabled` (bool): Enable internal logging (default: True)
- `output` (str): Output stream - `"stderr"` or `"stdout"`

**Returns:** `Self`

**Example:**
```python
builder.with_diagnostics(enabled=True, output="stderr")
```

---

### with_strict_mode(enabled=True)

Enable strict envelope mode (drop on serialization failure).

**Parameters:**
- `enabled` (bool): Enable strict mode (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_strict_mode(enabled=True)
```

---

### with_unhandled_exception_capture(enabled=True)

Enable automatic capture of unhandled exceptions.

**Parameters:**
- `enabled` (bool): Install exception hooks (default: True)

**Returns:** `Self`

**Example:**
```python
builder.with_unhandled_exception_capture(enabled=True)
```

---

### with_plugins(*, enabled=True, allow_external=False, allowlist=None, denylist=None, validation_mode="disabled")

Configure plugin loading behavior.

**Parameters:**
- `enabled` (bool): Enable plugin loading (default: True)
- `allow_external` (bool): Allow entry point plugins (default: False)
- `allowlist` (list[str] | None): Only allow these plugins
- `denylist` (list[str] | None): Block these plugins
- `validation_mode` (str): Validation mode - `"disabled"`, `"warn"`, `"strict"`

**Returns:** `Self`

**Example:**
```python
builder.with_plugins(allowlist=["rotating_file", "stdout_json"])
```

---

## Building the Logger

### build()

Build and return a synchronous logger.

**Returns:** `SyncLoggerFacade`

**Raises:**
- `ValueError`: If configuration is invalid

**Example:**
```python
logger = LoggerBuilder().add_stdout().build()
```

---

### build_async() (AsyncLoggerBuilder only)

Build and return an asynchronous logger.

**Returns:** `AsyncLoggerFacade`

**Raises:**
- `ValueError`: If configuration is invalid

**Example:**
```python
logger = await AsyncLoggerBuilder().add_stdout().build_async()
```

---

## Complete Method Index

| Method | Category | Description |
|--------|----------|-------------|
| `with_name()` | Core | Set logger name |
| `with_level()` | Core | Set log level |
| `with_preset()` | Core | Apply preset configuration |
| `with_app_name()` | Core | Set application name |
| `add_stdout()` | Sinks | Add stdout sink |
| `add_stdout_pretty()` | Sinks | Add pretty stdout sink |
| `add_file()` | Sinks | Add rotating file sink |
| `add_http()` | Sinks | Add HTTP sink |
| `add_webhook()` | Sinks | Add webhook sink |
| `add_cloudwatch()` | Sinks | Add AWS CloudWatch sink |
| `add_loki()` | Sinks | Add Grafana Loki sink |
| `add_postgres()` | Sinks | Add PostgreSQL sink |
| `with_filters()` | Filters | Enable filters by name |
| `with_sampling()` | Filters | Configure probabilistic sampling |
| `with_adaptive_sampling()` | Filters | Configure adaptive sampling |
| `with_trace_sampling()` | Filters | Configure trace-aware sampling |
| `with_rate_limit()` | Filters | Configure rate limiting |
| `with_first_occurrence()` | Filters | Configure deduplication |
| `with_size_guard()` | Processors | Configure size limiting |
| `with_redaction()` | Redaction | Configure basic redaction |
| `with_field_mask()` | Redaction | Configure field masking |
| `with_regex_mask()` | Redaction | Configure regex masking |
| `with_url_credential_redaction()` | Redaction | Configure URL credential scrubbing |
| `with_redaction_guardrails()` | Redaction | Configure redaction limits |
| `with_queue_size()` | Performance | Set queue size |
| `with_batch_size()` | Performance | Set batch size |
| `with_batch_timeout()` | Performance | Set batch timeout |
| `with_workers()` | Performance | Set worker count |
| `with_circuit_breaker()` | Reliability | Configure circuit breaker |
| `with_backpressure()` | Reliability | Configure backpressure |
| `with_shutdown_timeout()` | Reliability | Set shutdown timeout |
| `with_parallel_sink_writes()` | Performance | Enable parallel writes |
| `with_routing()` | Routing | Configure sink routing |
| `with_enrichers()` | Enrichers | Enable enrichers |
| `configure_enricher()` | Enrichers | Configure enricher |
| `with_context()` | Enrichers | Set default context |
| `with_exceptions()` | Advanced | Configure exception handling |
| `with_metrics()` | Advanced | Enable metrics |
| `with_error_deduplication()` | Advanced | Configure error dedup |
| `with_diagnostics()` | Advanced | Configure diagnostics |
| `with_strict_mode()` | Advanced | Enable strict mode |
| `with_unhandled_exception_capture()` | Advanced | Capture unhandled exceptions |
| `with_plugins()` | Advanced | Configure plugin loading |
| `build()` | Build | Build sync logger |
| `build_async()` | Build | Build async logger |
