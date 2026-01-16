# Sinks



Output plugins that deliver serialized log entries to destinations.

## Contract

Implement `BaseSink` methods:

- `async start(self) -> None`: optional initialization.
- `async write(self, entry: dict) -> None`: required; receives enriched/redacted envelope.
- `async stop(self) -> None`: optional teardown.

Errors should be contained; do not raise into the pipeline.

### Optional methods

#### write_serialized

```python
async def write_serialized(self, view: SerializedView) -> None
```

Fast path when `Settings.core.serialize_in_flush=True`. If present, fapilog pre-serializes entries once and calls this method instead of `write()` for sinks that consume bytes. If absent, fapilog automatically falls back to `write()`.

`SerializedView` exposes:

```python
@dataclass
class SerializedView:
    data: memoryview

    def __bytes__(self) -> bytes:
        return bytes(self.data)
```

## Built-in sinks

- **stdout_json**: JSON lines to stdout.
- **stdout_pretty**: human-readable console output with ANSI colors (TTY only).
- **rotating_file**: size/time-based rotation with optional compression.
- **http**: POST log entries to an HTTP endpoint.
- **webhook**: POST log entries to a webhook with optional signing.

## Convenience factories

### rotating_file (fapilog.sinks)

```python
from fapilog.sinks import rotating_file

sink = rotating_file(
    "logs/app.log",
    rotation="10 MB",
    retention=7,
    compression=True,
    mode="json",
)
```

Parameters:
- `path`: file path (directory is created if missing)
- `rotation`: size-based rotation (string or int bytes)
- `retention`: max rotated files to keep
- `compression`: gzip rotated files
- `mode`: `json` or `text`

## Configuration (env)

Rotating file:
```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES="10 MB"
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
export FAPILOG_FILE__INTERVAL_SECONDS="daily"
```

HTTP sink:
```bash
export FAPILOG_HTTP__ENDPOINT=https://logs.example.com/ingest
export FAPILOG_HTTP__TIMEOUT_SECONDS=5
export FAPILOG_HTTP__RETRY_MAX_ATTEMPTS=3
export FAPILOG_HTTP__BATCH_SIZE=100
export FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS=5
export FAPILOG_HTTP__BATCH_FORMAT=array   # array|ndjson|wrapped
export FAPILOG_HTTP__BATCH_WRAPPER_KEY=logs
```

## Building Blocks

### MemoryMappedPersistence

A low-level memory-mapped file writer for building custom zero-copy sinks.

**Note:** `MemoryMappedPersistence` is **not a sink itself**—it does not implement
the `BaseSink` protocol. Instead, it provides efficient byte-level append operations
that you can use to build performance-critical custom sinks.

```python
from fapilog.plugins.sinks import BaseSink, MemoryMappedPersistence
import json


class MyMmapSink:
    """Example custom sink using MemoryMappedPersistence."""
    
    name = "my_mmap"

    def __init__(self, path: str):
        self._mmap = MemoryMappedPersistence(path)

    async def start(self) -> None:
        await self._mmap.open()

    async def write(self, entry: dict) -> None:
        data = json.dumps(entry).encode()
        await self._mmap.append_line(data)

    async def stop(self) -> None:
        await self._mmap.close()

    async def health_check(self) -> bool:
        return await self._mmap.health_check()
```

See the `MemoryMappedPersistence` class documentation for full API details including
configuration options for initial size, growth factor, and sync behavior.

## CloudWatch Sink

AWS CloudWatch Logs sink with batching, retry, and circuit breaker support.

**Requires:** `boto3>=1.26.0`

```bash
pip install "fapilog[cloudwatch]"
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_group_name` | str | "/fapilog/default" | CloudWatch log group name |
| `log_stream_name` | str | None (auto-generated) | CloudWatch log stream name. If not set, defaults to `{hostname}-{timestamp}` |
| `region` | str | AWS_REGION env | AWS region for CloudWatch |
| `create_log_group` | bool | True | Auto-create log group if it doesn't exist |
| `create_log_stream` | bool | True | Auto-create log stream if it doesn't exist |
| `batch_size` | int | 100 | Maximum events per batch |
| `batch_timeout_seconds` | float | 5.0 | Maximum time to wait before flushing a batch |
| `max_retries` | int | 3 | Number of retry attempts on failure |
| `retry_base_delay` | float | 0.5 | Base delay in seconds for exponential backoff |
| `endpoint_url` | str | None | Custom endpoint URL (for LocalStack or testing) |
| `circuit_breaker_enabled` | bool | True | Enable circuit breaker for fault tolerance |
| `circuit_breaker_threshold` | int | 5 | Consecutive failures before circuit opens |

### Environment Variables

| Variable | Maps To |
|----------|---------|
| `AWS_REGION` | `region` (primary) |
| `AWS_DEFAULT_REGION` | `region` (fallback) |

AWS credentials are resolved via the standard boto3 credential chain:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. Shared credentials file (`~/.aws/credentials`)
3. IAM role (for EC2/ECS/Lambda)

### Usage Example

```python
from fapilog import Settings

settings = Settings(
    sinks=[
        {
            "type": "cloudwatch",
            "log_group_name": "/myapp/production",
            "log_stream_name": "api-server-1",
            "region": "us-east-1",
            "batch_size": 50,
        }
    ]
)
```

### Notes

- Events exceeding 256 KB are dropped with a diagnostic warning
- Batches are automatically chunked to respect CloudWatch limits (10,000 events, 1 MB per call)
- Sequence token handling is automatic (recovers from `InvalidSequenceTokenException`)

## Loki Sink

Grafana Loki sink with batching, label management, and retry support.

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `url` | str | "http://localhost:3100" | Loki server URL |
| `tenant_id` | str | None | Multi-tenant org ID (sets `X-Scope-OrgID` header) |
| `labels` | dict | {"service": "fapilog"} | Static labels applied to all log streams |
| `label_keys` | list | ["level"] | Fields to extract as dynamic labels |
| `batch_size` | int | 100 | Maximum events per batch |
| `batch_timeout_seconds` | float | 5.0 | Maximum time to wait before flushing a batch |
| `timeout_seconds` | float | 10.0 | HTTP request timeout |
| `max_retries` | int | 3 | Number of retry attempts on failure |
| `retry_base_delay` | float | 0.5 | Base delay in seconds for exponential backoff |
| `auth_username` | str | None | Basic authentication username |
| `auth_password` | str | None | Basic authentication password |
| `auth_token` | str | None | Bearer token for authentication |
| `circuit_breaker_enabled` | bool | True | Enable circuit breaker for fault tolerance |
| `circuit_breaker_threshold` | int | 5 | Consecutive failures before circuit opens |

### Environment Variables

| Variable | Maps To |
|----------|---------|
| `FAPILOG_LOKI__URL` | `url` |
| `FAPILOG_LOKI__TENANT_ID` | `tenant_id` |
| `FAPILOG_LOKI__AUTH_USERNAME` | `auth_username` |
| `FAPILOG_LOKI__AUTH_PASSWORD` | `auth_password` |
| `FAPILOG_LOKI__AUTH_TOKEN` | `auth_token` |

### Authentication Options

**Basic Authentication:**
```python
settings = Settings(
    sinks=[
        {
            "type": "loki",
            "url": "https://loki.example.com",
            "auth_username": "user",
            "auth_password": "secret",
        }
    ]
)
```

**Bearer Token:**
```python
settings = Settings(
    sinks=[
        {
            "type": "loki",
            "url": "https://loki.example.com",
            "auth_token": "your-api-token",
        }
    ]
)
```

### Labels Configuration

Labels determine how logs are grouped into streams in Loki. Use static labels for fixed metadata and dynamic labels for fields extracted from log entries.

```python
settings = Settings(
    sinks=[
        {
            "type": "loki",
            "labels": {
                "service": "api-gateway",
                "env": "production",
            },
            "label_keys": ["level", "logger"],  # Extract from each log entry
        }
    ]
)
```

**Note:** Label values are sanitized (non-alphanumeric characters replaced with `_`, max 128 chars).

## PostgreSQL Sink

PostgreSQL sink with async connection pooling, batching, and automatic table creation.

**Requires:** `asyncpg>=0.28.0`

```bash
pip install "fapilog[postgres]"
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dsn` | str | None | Full connection string (overrides individual connection options) |
| `host` | str | "localhost" | Database host |
| `port` | int | 5432 | Database port |
| `database` | str | "fapilog" | Database name |
| `user` | str | "fapilog" | Database user |
| `password` | str | None | Database password |
| `table_name` | str | "logs" | Target table name |
| `schema_name` | str | "public" | Target schema name |
| `create_table` | bool | True | Auto-create table and indexes if they don't exist |
| `min_pool_size` | int | 2 | Minimum connections in pool |
| `max_pool_size` | int | 10 | Maximum connections in pool |
| `pool_acquire_timeout` | float | 10.0 | Timeout in seconds to acquire a connection |
| `batch_size` | int | 100 | Maximum events per batch |
| `batch_timeout_seconds` | float | 5.0 | Maximum time to wait before flushing a batch |
| `max_retries` | int | 3 | Number of retry attempts on failure |
| `retry_base_delay` | float | 0.5 | Base delay in seconds for exponential backoff |
| `circuit_breaker_enabled` | bool | True | Enable circuit breaker for fault tolerance |
| `circuit_breaker_threshold` | int | 5 | Consecutive failures before circuit opens |
| `use_jsonb` | bool | True | Use JSONB type instead of JSON (enables indexing) |
| `include_raw_json` | bool | True | Include full event in the JSON/JSONB column |
| `extract_fields` | list | ["timestamp", "level", "logger", "correlation_id", "message"] | Fields to extract as dedicated columns |

### Environment Variables

| Variable | Maps To |
|----------|---------|
| `FAPILOG_POSTGRES__DSN` | `dsn` |
| `FAPILOG_POSTGRES__HOST` | `host` |
| `FAPILOG_POSTGRES__PORT` | `port` |
| `FAPILOG_POSTGRES__DATABASE` | `database` |
| `FAPILOG_POSTGRES__USER` | `user` |
| `FAPILOG_POSTGRES__PASSWORD` | `password` |

### Table Schema

When `create_table=True`, the sink auto-creates a table with:

```sql
CREATE TABLE IF NOT EXISTS "public"."logs" (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp TIMESTAMPTZ,
    level VARCHAR(10),
    logger VARCHAR(255),
    correlation_id VARCHAR(64),
    message TEXT,
    event JSONB NOT NULL
)
```

**Auto-created indexes:**
- `idx_logs_timestamp` on `timestamp DESC` - for time-range queries
- `idx_logs_level` on `level` - for filtering by severity
- `idx_logs_correlation_id` on `correlation_id` (partial, WHERE NOT NULL) - for tracing
- `idx_logs_event_gin` GIN index on `event` - for JSONB queries (only when `use_jsonb=True`)

### Usage Example

```python
from fapilog import Settings

settings = Settings(
    sinks=[
        {
            "type": "postgres",
            "host": "db.example.com",
            "database": "logs",
            "user": "fapilog_writer",
            "password": "secret",
            "table_name": "app_logs",
            "max_pool_size": 20,
        }
    ]
)
```

**Using DSN:**
```python
settings = Settings(
    sinks=[
        {
            "type": "postgres",
            "dsn": "postgresql://user:pass@host:5432/dbname",
        }
    ]
)
```

### Connection Pooling Notes

- Connections are pooled using `asyncpg.create_pool()`
- Set `min_pool_size` > 1 for high-throughput applications to avoid connection acquisition latency
- `max_pool_size` should match your expected concurrency; too high can exhaust database connections
- `pool_acquire_timeout` prevents indefinite blocking when pool is exhausted
