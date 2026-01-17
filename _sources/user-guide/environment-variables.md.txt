# Environment Variable Configuration

Fapilog follows 12-factor conventions: every setting can be supplied via environment variables using the `FAPILOG_` prefix and double-underscore nesting (e.g., `FAPILOG_CORE__LOG_LEVEL`). Short aliases exist for common sinks and guards so you don't have to remember deeply nested names.

## Naming Convention

- Prefix: `FAPILOG_`
- Nested fields: `__` (double underscore)
- Lists: JSON strings (e.g., `["stdout_json","audit"]`)
- Booleans: `true/false`, `1/0`, `yes/no`

Example: `FAPILOG_CORE__SINKS='["cloudwatch"]'` maps to `settings.core.sinks`.

Size and duration fields accept human-readable strings (e.g., `"10 MB"`, `"5s"`) as
well as numeric values. Rotation intervals also accept `"hourly"`, `"daily"`, `"weekly"`.

## How Env Vars Are Resolved

Fapilog env vars fall into three categories:

| Category | Example | How It Works |
| --- | --- | --- |
| **Top-level** | `FAPILOG_CORE__*`, `FAPILOG_HTTP__*` | Standard Pydantic parsing—these are top-level settings |
| **Short aliases** | `FAPILOG_CLOUDWATCH__*`, `FAPILOG_LOKI__*`, `FAPILOG_POSTGRES__*`, `FAPILOG_SIZE_GUARD__*`, `FAPILOG_SINK_ROUTING__*` | Dedicated handlers map short forms to nested paths |
| **Full paths** | `FAPILOG_SINK_CONFIG__WEBHOOK__*` | Require the complete nested path |

Short aliases like `FAPILOG_CLOUDWATCH__REGION` are convenience mappings—they're equivalent to the full path `FAPILOG_SINK_CONFIG__CLOUDWATCH__REGION` but easier to type.

## Quick Reference

### Core Settings (top-level)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_CORE__LOG_LEVEL` | string | `INFO` | Minimum log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `FAPILOG_CORE__MAX_QUEUE_SIZE` | int | `10000` | Queue depth before backpressure/drop |
| `FAPILOG_CORE__BATCH_MAX_SIZE` | int | `256` | Max events per flush batch |
| `FAPILOG_CORE__BATCH_TIMEOUT_SECONDS` | float | `0.25` | Max seconds before flushing a partial batch |
| `FAPILOG_CORE__BACKPRESSURE_WAIT_MS` | int | `50` | Milliseconds to wait for space before dropping |
| `FAPILOG_CORE__DROP_ON_FULL` | bool | `true` | Drop when queue full after wait |
| `FAPILOG_CORE__SINKS` | JSON list | `[]` (auto-pick) | Sink plugin names (e.g., `["stdout_json","audit"]`) |
| `FAPILOG_CORE__FILTERS` | JSON list | `[]` | Filter plugin names |
| `FAPILOG_CORE__ENABLE_METRICS` | bool | `false` | Enable internal metrics |
| `FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS` | float | `5.0` | Suppress duplicate errors within window |
| `FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED` | bool | `false` | Enable sink circuit breakers |
| `FAPILOG_CORE__SINK_PARALLEL_WRITES` | bool | `false` | Fan out writes in parallel |

### File Sink (env-only shortcut)

When `FAPILOG_FILE__DIRECTORY` is set, the rotating file sink is auto-enabled without touching `core.sinks`.

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_FILE__DIRECTORY` | string | unset | Directory for rotated files |
| `FAPILOG_FILE__FILENAME_PREFIX` | string | `fapilog` | Filename prefix |
| `FAPILOG_FILE__MODE` | string | `json` | `json` or `text` |
| `FAPILOG_FILE__MAX_BYTES` | size | `10485760` | Rotate at/after this size (e.g., `"10 MB"`) |
| `FAPILOG_FILE__INTERVAL_SECONDS` | duration | unset | Optional time-based rotation (e.g., `"daily"`, `"1h"`) |
| `FAPILOG_FILE__MAX_FILES` | int | unset | Retain at most this many rotated files |
| `FAPILOG_FILE__MAX_TOTAL_BYTES` | size | unset | Retain up to this many bytes across rotated files (e.g., `"100 MB"`) |
| `FAPILOG_FILE__COMPRESS_ROTATED` | bool | `false` | Gzip rotated files |

### CloudWatch Sink (short aliases)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_CLOUDWATCH__LOG_GROUP_NAME` | string | `/fapilog/default` | Log group |
| `FAPILOG_CLOUDWATCH__LOG_STREAM_NAME` | string | unset | Log stream |
| `FAPILOG_CLOUDWATCH__REGION` | string | unset | AWS region |
| `FAPILOG_CLOUDWATCH__ENDPOINT_URL` | string | unset | Custom endpoint/LocalStack |
| `FAPILOG_CLOUDWATCH__BATCH_SIZE` | int | `100` | Events per batch |
| `FAPILOG_CLOUDWATCH__BATCH_TIMEOUT_SECONDS` | float | `5.0` | Max seconds before flush |
| `FAPILOG_CLOUDWATCH__CREATE_LOG_GROUP` | bool | `true` | Auto-create group |
| `FAPILOG_CLOUDWATCH__CREATE_LOG_STREAM` | bool | `true` | Auto-create stream |
| `FAPILOG_CLOUDWATCH__MAX_RETRIES` | int | `3` | Retry attempts |
| `FAPILOG_CLOUDWATCH__RETRY_BASE_DELAY` | float | `0.5` | Backoff base seconds |
| `FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_ENABLED` | bool | `true` | Enable sink CB |
| `FAPILOG_CLOUDWATCH__CIRCUIT_BREAKER_THRESHOLD` | int | `5` | Failures to open circuit |

### Loki Sink (short aliases)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_LOKI__URL` | string | `http://localhost:3100` | Loki push endpoint |
| `FAPILOG_LOKI__TENANT_ID` | string | unset | Tenant |
| `FAPILOG_LOKI__LABELS` | JSON object | `{"service":"fapilog"}` | Static labels |
| `FAPILOG_LOKI__LABEL_KEYS` | JSON list | `["level"]` | Event keys promoted to labels |
| `FAPILOG_LOKI__BATCH_SIZE` | int | `100` | Events per batch |
| `FAPILOG_LOKI__BATCH_TIMEOUT_SECONDS` | float | `5.0` | Max seconds before flush |
| `FAPILOG_LOKI__TIMEOUT_SECONDS` | float | `10.0` | HTTP timeout |
| `FAPILOG_LOKI__MAX_RETRIES` | int | `3` | Retry attempts |
| `FAPILOG_LOKI__RETRY_BASE_DELAY` | float | `0.5` | Backoff base seconds |
| `FAPILOG_LOKI__CIRCUIT_BREAKER_ENABLED` | bool | `true` | Enable sink CB |
| `FAPILOG_LOKI__CIRCUIT_BREAKER_THRESHOLD` | int | `5` | Failures to open circuit |
| `FAPILOG_LOKI__AUTH_USERNAME` | string | unset | Basic auth username |
| `FAPILOG_LOKI__AUTH_PASSWORD` | string | unset | Basic auth password |
| `FAPILOG_LOKI__AUTH_TOKEN` | string | unset | Bearer token |

### PostgreSQL Sink (short aliases)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_POSTGRES__DSN` | string | unset | Full DSN (overrides host/port/db/user/pass) |
| `FAPILOG_POSTGRES__HOST` | string | `localhost` | Host |
| `FAPILOG_POSTGRES__PORT` | int | `5432` | Port |
| `FAPILOG_POSTGRES__DATABASE` | string | `fapilog` | Database |
| `FAPILOG_POSTGRES__USER` | string | `fapilog` | User |
| `FAPILOG_POSTGRES__PASSWORD` | string | unset | Password |
| `FAPILOG_POSTGRES__TABLE_NAME` | string | `logs` | Table |
| `FAPILOG_POSTGRES__SCHEMA_NAME` | string | `public` | Schema |
| `FAPILOG_POSTGRES__CREATE_TABLE` | bool | `true` | Auto-create table |
| `FAPILOG_POSTGRES__USE_JSONB` | bool | `true` | Store payload as JSONB |
| `FAPILOG_POSTGRES__INCLUDE_RAW_JSON` | bool | `true` | Store raw JSON alongside columns |
| `FAPILOG_POSTGRES__MIN_POOL_SIZE` | int | `2` | Min pool size |
| `FAPILOG_POSTGRES__MAX_POOL_SIZE` | int | `10` | Max pool size |
| `FAPILOG_POSTGRES__POOL_ACQUIRE_TIMEOUT` | float | `10.0` | Acquire timeout seconds |
| `FAPILOG_POSTGRES__BATCH_SIZE` | int | `100` | Events per batch |
| `FAPILOG_POSTGRES__BATCH_TIMEOUT_SECONDS` | float | `5.0` | Max seconds before flush |
| `FAPILOG_POSTGRES__MAX_RETRIES` | int | `3` | Retry attempts |
| `FAPILOG_POSTGRES__RETRY_BASE_DELAY` | float | `0.5` | Backoff base seconds |
| `FAPILOG_POSTGRES__CIRCUIT_BREAKER_ENABLED` | bool | `true` | Enable sink CB |
| `FAPILOG_POSTGRES__CIRCUIT_BREAKER_THRESHOLD` | int | `5` | Failures to open circuit |
| `FAPILOG_POSTGRES__EXTRACT_FIELDS` | JSON list | unset | Fields to extract into columns |

### HTTP Sink (top-level)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_HTTP__ENDPOINT` | string | unset | HTTP sink endpoint |
| `FAPILOG_HTTP__TIMEOUT_SECONDS` | float | `5.0` | Request timeout |
| `FAPILOG_HTTP__RETRY_MAX_ATTEMPTS` | int | unset | Max retry attempts |
| `FAPILOG_HTTP__RETRY_BACKOFF_SECONDS` | float | unset | Base backoff seconds |
| `FAPILOG_HTTP__BATCH_SIZE` | int | `1` | Events per request |
| `FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS` | float | `5.0` | Max seconds before flush |
| `FAPILOG_HTTP__BATCH_FORMAT` | string | `array` | `array`, `ndjson`, or `wrapped` |
| `FAPILOG_HTTP__BATCH_WRAPPER_KEY` | string | `logs` | Wrapper key for `wrapped` format |
| `FAPILOG_HTTP__HEADERS_JSON` | JSON object | unset | Headers map as JSON |

### Webhook Sink (full path)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_SINK_CONFIG__WEBHOOK__ENDPOINT` | string | unset | Webhook URL |
| `FAPILOG_SINK_CONFIG__WEBHOOK__SECRET` | string | unset | Shared secret for signing |
| `FAPILOG_SINK_CONFIG__WEBHOOK__HEADERS` | JSON object | `{}` | Extra headers |
| `FAPILOG_SINK_CONFIG__WEBHOOK__RETRY_MAX_ATTEMPTS` | int | unset | Max retry attempts |
| `FAPILOG_SINK_CONFIG__WEBHOOK__RETRY_BACKOFF_SECONDS` | float | unset | Backoff seconds |
| `FAPILOG_SINK_CONFIG__WEBHOOK__TIMEOUT_SECONDS` | float | `5.0` | Request timeout |
| `FAPILOG_SINK_CONFIG__WEBHOOK__BATCH_SIZE` | int | `1` | Events per webhook call |
| `FAPILOG_SINK_CONFIG__WEBHOOK__BATCH_TIMEOUT_SECONDS` | float | `5.0` | Max seconds before flush |

### Sink Routing (short aliases)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_SINK_ROUTING__ENABLED` | bool | `false` | Enable level-based routing |
| `FAPILOG_SINK_ROUTING__OVERLAP` | bool | `true` | Allow overlapping routes |
| `FAPILOG_SINK_ROUTING__RULES` | JSON list | `[]` | Routing rules list |
| `FAPILOG_SINK_ROUTING__FALLBACK_SINKS` | JSON list | `[]` | Fallback sink names |

### Size Guard Processor (short aliases)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_SIZE_GUARD__ACTION` | string | `truncate` | Action on oversize (`truncate`, `drop`, `warn`) |
| `FAPILOG_SIZE_GUARD__MAX_BYTES` | size | `256000` | Max bytes before action (e.g., `"1 MB"`) |
| `FAPILOG_SIZE_GUARD__PRESERVE_FIELDS` | JSON list | `["level","timestamp","logger","correlation_id"]` | Fields to keep when truncating |

### Runtime Info Enricher (common env helpers)

| Variable | Type | Default | Description |
| --- | --- | --- | --- |
| `FAPILOG_SERVICE` | string | `fapilog` | Service name emitted by `runtime_info` enricher |
| `FAPILOG_ENV` / `ENV` | string | `dev` | Environment name |
| `FAPILOG_VERSION` | string | unset | Service/app version |

## Deployment Examples

### Kubernetes (ConfigMap/Env)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fapilog-config
data:
  FAPILOG_CORE__LOG_LEVEL: "INFO"
  FAPILOG_CORE__SINKS: '["cloudwatch"]'
  FAPILOG_CLOUDWATCH__LOG_GROUP_NAME: "/myapp/prod"
  FAPILOG_CLOUDWATCH__REGION: "us-east-1"
```

### Docker Compose

```yaml
services:
  app:
    environment:
      FAPILOG_CORE__LOG_LEVEL: DEBUG
      FAPILOG_CORE__SINKS: '["loki"]'
      FAPILOG_LOKI__URL: http://loki:3100
      FAPILOG_LOKI__LABELS: '{"service":"app","env":"dev"}'
```

### Heroku / Railway

```bash
heroku config:set FAPILOG_CORE__LOG_LEVEL=INFO
heroku config:set FAPILOG_POSTGRES__DSN=$DATABASE_URL
heroku config:set FAPILOG_CORE__SINKS='["postgres"]'
```

## Tips

- Prefer JSON strings for lists/objects to avoid parsing surprises.
- Short aliases (e.g., `FAPILOG_LOKI__...`) override nested settings and keep manifests readable.
- Keep secrets in your secrets manager (Kubernetes Secret, Docker secrets, etc.) instead of ConfigMaps.

## Complete Reference

This guide covers the most commonly used settings. For the exhaustive list of all 200+ env vars (including advanced security, observability, and plugin settings), see the auto-generated [Environment Variables Reference](../env-vars.md).
