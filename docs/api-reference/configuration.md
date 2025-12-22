# Configuration

`Settings` is a Pydantic `BaseSettings` model that reads from keyword args and environment variables (`env_prefix="FAPILOG_"`, `env_nested_delimiter="__"`). Pass an instance to `get_logger` / `get_async_logger` / `runtime(_async)`.

## Constructing Settings {#constructing-settings}

```python
from fapilog import Settings, get_logger

settings = Settings(
    core__max_queue_size=5000,
    core__batch_max_size=128,
    core__enable_metrics=True,
    http__endpoint="https://logs.example.com/ingest",  # optional HTTP sink
    http__headers={"Authorization": "Bearer token"},
)

logger = get_logger("api", settings=settings)
logger.info("configured", queue=settings.core.max_queue_size)
```

## Common environment variables

```bash
export FAPILOG_CORE__LOG_LEVEL=INFO
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__ENABLE_METRICS=true

# Enable rotating file sink via env (uses defaults for prefix/size/rotation)
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__MAX_FILES=5

# Optional HTTP sink
export FAPILOG_HTTP__ENDPOINT=https://logs.example.com/ingest
export FAPILOG_HTTP__TIMEOUT_SECONDS=5
export FAPILOG_HTTP__RETRY_MAX_ATTEMPTS=3
```

## Notable fields (core)

- `core.log_level`: `"DEBUG" | "INFO" | "WARNING" | "ERROR"` (hint only; filtering not enforced yet)
- `core.max_queue_size`: in-memory ring buffer capacity
- `core.batch_max_size` and `core.batch_timeout_seconds`: batching controls
- `core.enable_metrics`: toggles internal metrics collection
- `core.drop_on_full` / `core.backpressure_wait_ms`: backpressure behavior
- `core.enable_redactors`, `core.redactors_order`, `core.sensitive_fields_policy`: redaction stage configuration
- `core.serialize_in_flush`: pre-serialize envelopes during drain and pass bytes to sinks that support it

## HTTP sink (optional)

Set `http.endpoint` (or `FAPILOG_HTTP__ENDPOINT`) to route logs to an HTTP endpoint. Optional retry/backoff and headers are available through the `http` settings group.

## Plugin discovery

`settings.plugins` controls plugin discovery allow/deny lists and additional search paths. Defaults: enabled, load-on-startup empty.

## Validation

`Settings` runs validation when instantiated; async validations (e.g., paths) run via `await settings.validate_async()` if invoked directly. `get_logger` and `get_async_logger` create settings on demand and apply defaults for missing values.

---

_Use Settings for programmatic control; prefer env vars for deployment-specific overrides._
