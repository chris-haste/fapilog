# Grafana Loki Sink

Send structured logs to Grafana Loki with batching, labels, and retry/backoff.

## Quick start

```python
from fapilog.plugins.sinks.contrib.loki import LokiSink, LokiSinkConfig

sink = LokiSink(
    LokiSinkConfig(
        url="http://localhost:3100",
        labels={"service": "myapp", "env": "dev"},
        label_keys=["level", "component"],
    )
)
```

Environment-based setup:

```bash
export FAPILOG_CORE__SINKS='["loki"]'
export FAPILOG_LOKI__URL=http://localhost:3100
export FAPILOG_LOKI__LABELS='{"service":"myapp","env":"dev"}'
export FAPILOG_LOKI__LABEL_KEYS='["level","component"]'
```

## Configuration

- `url`: Loki base URL (required)
- `tenant_id`: Optional multi-tenant header (`X-Scope-OrgID`)
- `labels`: Static labels applied to every stream
- `label_keys`: Event keys promoted to labels (sanitized)
- `batch_size` / `batch_timeout_seconds`: Flush conditions
- `timeout_seconds`: HTTP timeout
- `max_retries` / `retry_base_delay`: Retry/backoff on errors/429
- Auth: `auth_username`/`auth_password` (basic) or `auth_token` (bearer)
- Circuit breaker: `circuit_breaker_enabled`, `circuit_breaker_threshold`

## Behavior

- Groups events by label combinations and pushes to `/loki/api/v1/push`
- Timestamps use nanoseconds since epoch; defaults to `time.time()` when absent
- Handles 429 with backoff, client errors (400/401/403) with diagnostics, and retries other failures
- Implements `write_serialized` for pipelines using `serialize_in_flush`
- Health check calls `/ready`

## Label best practices

1. Keep cardinality low (`level`, `service`, `env` are safe).
2. Avoid high-cardinality fields (`user_id`, `request_id`).
3. Label values are sanitized to `[A-Za-z0-9_-]`; long values are truncated.

## Structured metadata (Loki 2.9+)

Loki 2.9+ supports structured metadata alongside labels. This feature is planned
for a future fapilog release. Currently, all event data is serialized as the log
line content. Track progress in the project roadmap.

## Local testing (Docker)

```bash
docker run -d -p 3100:3100 grafana/loki:latest
export FAPILOG_LOKI__URL=http://localhost:3100
python - <<'PY'
from fapilog import runtime
with runtime() as logger:
    logger.info("hello loki", component="demo")
PY
```

See `tests/integration/test_loki_sink.py` for CI-ready patterns and `examples/loki_logging` for a complete FastAPI + Docker Compose setup.
