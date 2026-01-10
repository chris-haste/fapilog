# Configuration

Configure fapilog using presets for quick setup, environment variables, or the `Settings` class for full control.

## Configuration Presets (Recommended)

Presets provide pre-configured settings for common use cases. Use a preset when you want quick, sensible defaults:

```python
from fapilog import get_logger, get_async_logger

# Choose the preset that matches your use case
logger = get_logger(preset="dev")         # Local development
logger = get_logger(preset="production")  # Production deployment
logger = await get_async_logger(preset="fastapi")  # FastAPI apps
logger = get_logger(preset="minimal")     # Backwards compatible default
```

### Preset Comparison

| Preset | Log Level | Sinks | File Rotation | Redaction | Batch Size |
|--------|-----------|-------|---------------|-----------|------------|
| `dev` | DEBUG | stdout | No | No | 1 (immediate) |
| `production` | INFO | stdout + file | 50MB × 10 files | Yes (9 fields) | 100 |
| `fastapi` | INFO | stdout | No | No | 50 |
| `minimal` | INFO | stdout | No | No | 256 (default) |

### Preset Details

**`dev`** - Local development with maximum visibility:
- DEBUG level shows all messages
- Immediate flushing (batch_size=1) for real-time debugging
- Internal diagnostics enabled
- No redaction (safe for local secrets)

**`production`** - Production deployments with safety features:
- File rotation: `./logs/fapilog-*.log`, 50MB max, 10 files retained, gzip compressed
- Automatic redaction of: `password`, `api_key`, `token`, `secret`, `authorization`, `api_secret`, `private_key`, `ssn`, `credit_card`
- `drop_on_full=False` ensures no log loss under pressure

**`fastapi`** - Optimized for async FastAPI applications:
- `context_vars` enricher enabled for request context propagation
- Container-friendly stdout JSON output
- Balanced batch size for latency/throughput tradeoff

**`minimal`** - Matches `get_logger()` with no arguments:
- Use for explicit preset selection while maintaining backwards compatibility

### Preset vs Settings

Presets and `Settings` are mutually exclusive. Choose one approach:

```python
# Option 1: Use a preset (simple)
logger = get_logger(preset="production")

# Option 2: Use Settings (full control)
logger = get_logger(settings=Settings(...))

# NOT allowed - raises ValueError
logger = get_logger(preset="production", settings=Settings(...))
```

If you need customization beyond what presets offer, use the `Settings` class directly.

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

## Deprecated setting: legacy sampling

`observability.logging.sampling_rate` is deprecated and now raises a `DeprecationWarning`. Move to filter-based sampling to avoid double-sampling and to unlock sampling metrics:

```yaml
core:
  filters: ["sampling"]
filter_config:
  sampling:
    config:
      sample_rate: 0.25
```

## Full reference

See [Environment Variables](environment-variables.md) for the full matrix of env names and aliases (including short forms like `FAPILOG_CLOUDWATCH__REGION`).
