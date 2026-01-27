# PostgreSQL Sink

Store structured logs in PostgreSQL with async batching, connection pooling, and JSONB storage.

## Installation

```bash
pip install "fapilog[postgres]"
```

## Quick start

```python
from fapilog.plugins.sinks.contrib.postgres import PostgresSink, PostgresSinkConfig

sink = PostgresSink(
    PostgresSinkConfig(
        host="localhost",
        database="fapilog",
        user="fapilog",
        password="secret",
        table_name="logs",
    )
)
```

Environment-based setup:

```bash
export FAPILOG_CORE__SINKS='["postgres"]'
export FAPILOG_POSTGRES__HOST=localhost
export FAPILOG_POSTGRES__DATABASE=fapilog
export FAPILOG_POSTGRES__USER=fapilog
export FAPILOG_POSTGRES__PASSWORD=secret
```

## Configuration highlights

- Connection: `dsn` or `host`/`port`/`database`/`user`/`password`
- Pooling: `min_pool_size`, `max_pool_size`, `pool_acquire_timeout`
- Batching: `batch_size`, `batch_timeout_seconds`
- Reliability: `max_retries`, `retry_base_delay`, `circuit_breaker_enabled`
- Storage: `use_jsonb`, `include_raw_json`, `extract_fields`
- Table management: `schema_name`, `table_name`, `create_table`

### Auto Table Creation

> **Warning:** By default, `create_table=True` causes the sink to execute DDL
> (CREATE TABLE, CREATE INDEX) at startup. In production environments with
> restricted database permissions or change management policies, set
> `create_table=False` and provision tables via migrations or infrastructure-as-code.
>
> The `production` preset automatically sets `create_table=False`.

| Setting | Default | Production Preset |
|---------|---------|-------------------|
| `create_table` | `True` | `False` |

For production deployments, either:
1. Use `preset="production"` which disables auto-creation
2. Explicitly set `create_table=False` in your configuration
3. Create tables via migrations before deploying the application

Environment variable aliases:

| Variable | Default |
| --- | --- |
| `FAPILOG_POSTGRES__DSN` | `None` |
| `FAPILOG_POSTGRES__HOST` | `localhost` |
| `FAPILOG_POSTGRES__PORT` | `5432` |
| `FAPILOG_POSTGRES__DATABASE` | `fapilog` |
| `FAPILOG_POSTGRES__USER` | `fapilog` |
| `FAPILOG_POSTGRES__PASSWORD` | `None` |
| `FAPILOG_POSTGRES__TABLE_NAME` | `logs` |
| `FAPILOG_POSTGRES__BATCH_SIZE` | `100` |
| `FAPILOG_POSTGRES__CREATE_TABLE` | `true` |
| `FAPILOG_POSTGRES__USE_JSONB` | `true` |

Programmatic configuration:

```python
from fapilog.plugins.sinks.contrib.postgres import PostgresSinkConfig

config = PostgresSinkConfig(
    dsn="postgresql://logger:secret@db/fapilog",
    table_name="application_logs",
    batch_size=200,
    use_jsonb=True,
    extract_fields=["timestamp", "level", "message", "correlation_id"],
)
```

## Schema and indexes

Default schema (JSONB event column):

```sql
CREATE TABLE IF NOT EXISTS public.logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp TIMESTAMPTZ,
    level VARCHAR(10),
    logger VARCHAR(255),
    correlation_id VARCHAR(64),
    message TEXT,
    event JSONB NOT NULL
);
```

Indexes:

- `timestamp DESC` for time range queries
- `level` for severity filters
- `correlation_id` for tracing
- `event` GIN index when `use_jsonb=True`

## Query examples

```sql
-- Recent errors
SELECT timestamp, message FROM logs WHERE level IN ('ERROR', 'CRITICAL') ORDER BY timestamp DESC LIMIT 50;

-- Requests by correlation id
SELECT * FROM logs WHERE correlation_id = 'req-123' ORDER BY timestamp;

-- JSONB fields
SELECT * FROM logs WHERE event->>'service' = 'api';
SELECT * FROM logs WHERE event->'metadata'->>'version' = '1.2.3';
```

## Performance tuning

- Increase `batch_size` for higher throughput (e.g., 500).
- Adjust `min_pool_size`/`max_pool_size` based on concurrent writers.
- Use `pool_acquire_timeout` to prevent stalls when the pool is exhausted.
- Consider partitioning or TimescaleDB for very large datasets (see below).

## High-volume scenarios

For applications generating millions of log events per day, consider these strategies:

### Native partitioning

PostgreSQL 10+ supports declarative partitioning. Partition by timestamp for efficient time-range queries and simplified retention:

```sql
-- Create partitioned table (run manually, set create_table=False)
CREATE TABLE logs (
    id BIGSERIAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    timestamp TIMESTAMPTZ,
    level VARCHAR(10),
    logger VARCHAR(255),
    correlation_id VARCHAR(64),
    message TEXT,
    event JSONB NOT NULL
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE logs_2024_01 PARTITION OF logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### TimescaleDB hypertables

[TimescaleDB](https://www.timescale.com/) is a PostgreSQL extension optimized for time-series data. Convert your logs table to a hypertable for automatic partitioning and compression:

```sql
-- Install TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert to hypertable (after creating base table)
SELECT create_hypertable('logs', 'timestamp');

-- Enable compression for older data (optional)
ALTER TABLE logs SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'level'
);

-- Add compression policy (compress data older than 7 days)
SELECT add_compression_policy('logs', INTERVAL '7 days');
```

Benefits of TimescaleDB:
- Automatic time-based partitioning (chunks)
- Built-in compression (10-20x storage reduction)
- Continuous aggregates for dashboards
- Retention policies for automatic cleanup

### Retention policies

For both native and TimescaleDB partitioning, implement retention to manage storage:

```sql
-- TimescaleDB: drop data older than 90 days
SELECT add_retention_policy('logs', INTERVAL '90 days');

-- Native partitioning: drop old partitions manually
DROP TABLE logs_2023_01;
```

## Troubleshooting

- Connection refused: verify PostgreSQL is reachable (`psql -h ... -c "SELECT 1"`).
- Pool exhaustion: increase `max_pool_size` or reduce the number of logger instances.
- Slow inserts: increase `batch_size`, reduce index count, or add partitioning.

## Related resources

- `tests/integration/test_postgres_sink.py` for CI usage
- `examples/postgres_logging/` for a Docker Compose + FastAPI sample
