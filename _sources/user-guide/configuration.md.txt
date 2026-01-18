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

### FastAPI one-liner

Use the presets with `setup_logging()` for FastAPI apps:

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import get_request_logger, setup_logging

app = FastAPI(lifespan=setup_logging(preset="fastapi"))

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_request_logger)):
    await logger.info("Fetching user", user_id=user_id)
    return {"user_id": user_id}
```

Automatic middleware registration is enabled by default. Disable it for manual control:

```python
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI(lifespan=setup_logging(preset="fastapi", auto_middleware=False))
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

If you need to attach the lifespan after app creation:

```python
app = FastAPI()
app.router.lifespan_context = setup_logging(preset="fastapi")
```

Set the lifespan before the application starts.

### Preset Comparison

| Preset | Log Level | Sinks | File Rotation | Redaction | Batch Size |
|--------|-----------|-------|---------------|-----------|------------|
| `dev` | DEBUG | stdout_pretty | No | No | 1 (immediate) |
| `production` | INFO | stdout_json + file | 50MB × 10 files | Yes (9 fields) | 100 |
| `fastapi` | INFO | stdout_json | No | No | 50 |
| `minimal` | INFO | stdout_json | No | No | 256 (default) |

### Preset Details

**`dev`** - Local development with maximum visibility:
- DEBUG level shows all messages
- Immediate flushing (batch_size=1) for real-time debugging
- Internal diagnostics enabled
- Pretty console output in terminals
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

## Output format

Use `format` to control stdout output without building a full `Settings` object:

```python
from fapilog import get_logger

logger = get_logger(format="auto")   # Default: pretty in TTY, JSON when piped
logger = get_logger(format="pretty") # Force human-readable output
logger = get_logger(format="json")   # Force structured JSON
```

Notes:
- `format` is mutually exclusive with `settings`.
- If both `preset` and `format` are provided, `format` overrides the preset's stdout sink.
- When `settings` is omitted, `format` defaults to `auto`.

## Default behaviors

When you call `get_logger()` without a preset, settings, or `FAPILOG_CORE__LOG_LEVEL`,
fapilog selects a sensible default log level:

- TTY (interactive terminal): `DEBUG`
- Non-TTY (pipes, scripts): `INFO`
- CI: forces `INFO` even if TTY

Explicit `core.log_level` or a preset always overrides these defaults.

On sink write failures (exceptions raised by a sink), fapilog falls back to stderr.
If stderr fails too, the entry is dropped. Diagnostics warnings are emitted when
internal diagnostics are enabled:

```bash
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
```

## Quick setup (env)

```bash
# Log level
export FAPILOG_CORE__LOG_LEVEL=INFO

# Rotating file sink (optional)
export FAPILOG_SINK_CONFIG__ROTATING_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES="10 MB"
export FAPILOG_SINK_CONFIG__ROTATING_FILE__INTERVAL_SECONDS="daily"

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

Size and duration fields accept human-readable strings (e.g., `"10 MB"`, `"5s"`) as well as
numeric values. Rotation keywords (`"hourly"`, `"daily"`, `"weekly"`) apply to rotation
interval settings and represent fixed intervals (not wall-clock boundaries).

## Common patterns

- **Stdout auto (default)**: pretty in TTY, JSON when piped.
- **Rotating file sink**: set `FAPILOG_SINK_CONFIG__ROTATING_FILE__DIRECTORY`; tune rotation via `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_BYTES`, `FAPILOG_SINK_CONFIG__ROTATING_FILE__MAX_FILES`.
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

## Plugin Security

By default, fapilog only loads **built-in plugins**. External plugins (registered via Python entry points) are blocked to prevent arbitrary code execution from untrusted packages.

### Enabling External Plugins

To use external plugins, explicitly opt-in using one of these approaches:

**Recommended: Allowlist specific plugins**

```python
from fapilog import Settings, get_logger

settings = Settings(plugins={"allowlist": ["my-trusted-sink", "approved-enricher"]})
logger = get_logger(settings=settings)
```

```bash
# Via environment variable
export FAPILOG_PLUGINS__ALLOWLIST='["my-trusted-sink", "approved-enricher"]'
```

**Less secure: Allow all external plugins**

```python
settings = Settings(plugins={"allow_external": True})
```

```bash
export FAPILOG_PLUGINS__ALLOW_EXTERNAL=true
```

### Security Implications

External plugins can execute arbitrary code during loading. Only enable plugins you trust:

- **Allowlist approach**: Limits exposure to specific, known plugins
- **allow_external=True**: Permits any entry point plugin (use with caution)

When external plugins are loaded, a diagnostic warning is emitted to help track plugin sources.

### Migration from Previous Versions

If you were using external plugins that now fail to load, add them to the allowlist:

```python
# Before (external plugins loaded automatically)
settings = Settings(core={"sinks": ["external-sink"]})

# After (explicit opt-in required)
settings = Settings(
    core={"sinks": ["external-sink"]},
    plugins={"allowlist": ["external-sink"]},
)
```

## Full reference

See [Environment Variables](environment-variables.md) for the full matrix of env names and aliases (including short forms like `FAPILOG_CLOUDWATCH__REGION`).
