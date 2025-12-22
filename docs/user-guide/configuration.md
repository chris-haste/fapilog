# Configuration


Configure fapilog via environment variables or the `Settings` class.

## Quick setup (env)

```bash
# Log level
export FAPILOG_CORE__LOG_LEVEL=INFO

# File sink (optional)
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760

# Performance tuning
export FAPILOG_CORE__BATCH_MAX_SIZE=128
export FAPILOG_CORE__MAX_QUEUE_SIZE=10000
```

## Programmatic settings

```python
from fapilog import Settings, get_logger

settings = Settings(
    core__log_level="INFO",
    core__enable_metrics=True,
    http__endpoint=None,  # default stdout/file selection applies
)

logger = get_logger(settings=settings)
logger.info("configured", queue=settings.core.max_queue_size)
```

## Common patterns

- **Stdout JSON (default)**: no env needed; `get_logger()` works out of the box.
- **File sink**: set `FAPILOG_FILE__DIRECTORY`; tune rotation via `FAPILOG_FILE__MAX_BYTES`, `FAPILOG_FILE__MAX_FILES`.
- **HTTP sink**: set `FAPILOG_HTTP__ENDPOINT` and optional timeout/retry envs.
- **Metrics**: set `FAPILOG_CORE__ENABLE_METRICS=true` to record internal metrics.

## Full reference

See `docs/env-vars.md` for the auto-generated environment variable matrix.
