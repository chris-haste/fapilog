# Configuration

Configure fapilog using presets for quick setup, environment variables, or the `Settings` class for full control.

## Choosing an Approach

| Situation | Recommended Approach | Why |
|-----------|---------------------|-----|
| **Just getting started** | `get_logger(preset="...")` | Zero config, sensible defaults |
| **FastAPI app** | `setup_logging(preset="fastapi")` | Automatic middleware and request context |
| **Writing new code** | `LoggerBuilder()` | IDE autocomplete, type safety, discoverable API |
| **Config from env/files** | `Settings` + environment variables | 12-factor apps, Kubernetes, external config |
| **Need compliance presets** | `LoggerBuilder().with_redaction(preset="GDPR_PII")` | One-liner GDPR, HIPAA, PCI-DSS protection |

**Quick decision:**

```
Start here
    │
    ├── Want sensible defaults with minimal code?
    │   └── Use presets: get_logger(preset="production")
    │
    ├── Want IDE autocomplete and type checking?
    │   └── Use Builder: LoggerBuilder().with_preset("production").build()
    │
    └── Config comes from environment or external files?
        └── Use Settings + env vars: FAPILOG_CORE__LOG_LEVEL=INFO
```

All approaches can be combined. For example, start with a preset and customize with the builder:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")           # Start with production defaults
    .with_redaction(preset="HIPAA_PHI")  # Add HIPAA compliance
    .with_sampling(rate=0.1)             # Sample 10% of debug logs
    .build()
)
```

## Configuration Presets (Recommended)

Presets provide pre-configured settings for common use cases. Use a preset when you want quick, sensible defaults:

```python
from fapilog import get_logger, get_async_logger

# Choose the preset that matches your use case
logger = get_logger(preset="dev")                # Local development
logger = get_logger(preset="production")         # Durable production (never drops logs)
logger = get_logger(preset="production-latency") # Low-latency production (prioritizes speed)
logger = get_logger(preset="serverless")         # Lambda, Cloud Run, Azure Functions
logger = await get_async_logger(preset="fastapi")  # FastAPI apps
logger = get_logger(preset="minimal")            # Backwards compatible default
```

**See [Presets Guide](presets.md)** for complete documentation including:
- Decision matrix for choosing the right preset
- Detailed comparison of `production` vs `production-latency`
- Full settings tables and customization examples

### Quick Comparison

| Preset | Drops Logs? | File Output | Redaction | Best For |
|--------|-------------|-------------|-----------|----------|
| `dev` | No | No | No | Local development |
| `production` | Never | Yes | Yes | Audit trails, compliance |
| `production-latency` | If needed | No | Yes | High-throughput APIs |
| `fastapi` | If needed | No | Yes | FastAPI applications |
| `serverless` | If needed | No | Yes | Lambda/Cloud Functions |
| `hardened` | Never | Yes | Yes (HIPAA+PCI) | Regulated environments |
| `minimal` | Default | No | No | Migration, explicit defaults |

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

If you need customization beyond what presets offer, use the `Settings` class directly or customize via the Builder API.

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

## Environment Auto-Detection

When you call `get_logger()` without a preset or settings, fapilog automatically detects your runtime environment and applies lightweight configuration tweaks. This is controlled by `auto_detect=True` (the default).

| Detected Environment | Detection Method | Applied Configuration |
|---------------------|------------------|----------------------|
| Lambda | `AWS_LAMBDA_FUNCTION_NAME` env var | Smaller batches (10), faster flush (0.1s), smaller queue (1000) |
| Kubernetes | `/var/run/secrets/kubernetes.io/serviceaccount` or `POD_NAME` env var | INFO level, `kubernetes` enricher |
| Docker | `/.dockerenv` file or `/proc/1/cgroup` contains "docker" | INFO level |
| CI | Common CI env vars (`CI`, `GITHUB_ACTIONS`, etc.) | INFO level |
| Local | Default fallback | Uses TTY-based log level defaults |

**Important:** Auto-detection applies incremental tweaks to the base configuration—it does **not** apply full preset configurations. For example:

- Auto-detecting Lambda adds smaller batches and the `runtime_info` enricher
- `preset="serverless"` provides the complete serverless config **including redactors**

If you need full preset behavior (especially redaction) in cloud environments, use explicit presets:

```python
# Full preset with redaction enabled
logger = get_logger(preset="serverless")

# Auto-detect only (applies tweaks but no redaction beyond url_credentials default)
logger = get_logger()

# Explicit environment without full preset
logger = get_logger(environment="lambda")  # Same as auto-detect for Lambda
```

To disable auto-detection entirely:

```python
logger = get_logger(auto_detect=False)
```

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

## Drop and Dedupe Visibility

When `drop_on_full=True` (the default), events may be dropped during queue backpressure. Similarly, error deduplication (`error_dedupe_window_seconds`) suppresses duplicate ERROR/CRITICAL messages. By default, these events are silently handled.

Enable `emit_drop_summary` to receive visibility into dropped and deduplicated events:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_drop_summary(enabled=True, window_seconds=60.0)
    .build()
)
```

Or via environment variables:

```bash
export FAPILOG_CORE__EMIT_DROP_SUMMARY=true
export FAPILOG_CORE__DROP_SUMMARY_WINDOW_SECONDS=60
```

When enabled:

- **Drop summaries**: Emitted when events are dropped due to backpressure. Contains `dropped_count` and `window_seconds`.
- **Dedupe summaries**: Emitted when error deduplication window expires with suppressed messages. Contains `error_message`, `suppressed_count`, and `window_seconds`.

Summary events are:

- Level `WARNING` (drops) or `INFO` (dedupe)
- Marked with `data._fapilog_internal: True` for filtering
- Rate-limited by `drop_summary_window_seconds` (default: 60s, minimum: 1s)
- Written directly to sinks, bypassing the queue

This feature is disabled by default to maintain backwards compatibility.

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

## Shutdown Handler Installation

Fapilog automatically installs signal handlers (SIGTERM/SIGINT) and atexit handlers for graceful shutdown. These handlers ensure pending logs are drained before process exit.

### Lazy Installation (Default)

Handlers are installed lazily on first logger start, not at module import time. This design:

- Avoids conflicts with frameworks (FastAPI, Uvicorn, Gunicorn) that manage their own signal handlers
- Follows library best practices by not modifying global state at import time
- Allows opt-out before any handlers are installed

```python
import fapilog

# No handlers installed yet - safe to configure framework handlers first
logger = fapilog.get_logger()  # Handlers installed here
```

### Manual Installation

For cases where you need handlers installed before creating a logger, use `install_shutdown_handlers()`:

```python
import fapilog

# Explicitly install handlers early
fapilog.install_shutdown_handlers()

# Later, create loggers
logger = fapilog.get_logger()
```

This function is idempotent - calling it multiple times has no effect after the first call.

### Disabling Handlers

To prevent handler installation entirely:

```bash
# Disable signal handlers (atexit still active)
export FAPILOG_CORE__SIGNAL_HANDLER_ENABLED=false

# Disable atexit drain (signal handlers still active)
export FAPILOG_CORE__ATEXIT_DRAIN_ENABLED=false

# Disable both
export FAPILOG_CORE__SIGNAL_HANDLER_ENABLED=false
export FAPILOG_CORE__ATEXIT_DRAIN_ENABLED=false
```

Or via code:

```python
from fapilog import Settings, get_logger

settings = Settings(
    core={
        "signal_handler_enabled": False,
        "atexit_drain_enabled": False,
    }
)
logger = get_logger(settings=settings)
```

### Framework Integration

When using fapilog with frameworks that manage their own shutdown:

**FastAPI/Uvicorn**: The lazy installation works well because FastAPI's lifespan handlers run after fapilog handlers are installed. Use the `setup_logging()` lifespan for proper integration.

**Gunicorn**: If you need to ensure fapilog handlers don't conflict, disable them and rely on Gunicorn's worker lifecycle:

```python
settings = Settings(core={"signal_handler_enabled": False})
logger = get_logger(settings=settings)
```

**Testing**: The handlers are designed for test isolation. Each test can reset handler state if needed using internal APIs.

## Full reference

- **[Execution Modes](execution-modes.md)** - Understanding async, bound loop, and thread modes for optimal throughput
- **[Configuration Map](../api-reference/configuration-map.md)** - Complete reference mapping every setting to its env var and builder method
- **[Environment Variables](environment-variables.md)** - Full matrix of env names and aliases (including short forms like `FAPILOG_CLOUDWATCH__REGION`)
