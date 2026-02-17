---
orphan: true
---

# Migrating from setup_logging() to FastAPIBuilder

This guide helps you migrate from the deprecated `setup_logging()` function to the new `FastAPIBuilder` class.

## Why migrate?

`FastAPIBuilder` provides:

- **Full configuration access**: All `AsyncLoggerBuilder` methods (backpressure, sampling, redaction, queue size, etc.)
- **Environment variable support**: FastAPI-specific env vars with override warnings
- **Consistent API**: Same builder pattern as regular logger configuration
- **Better discoverability**: IDE autocompletion for all options

## Quick migration

### Before (deprecated)

```python
from fapilog.fastapi import setup_logging

app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        skip_paths=["/health", "/metrics"],
        sample_rate=0.1,
        include_headers=True,
        allow_headers=["content-type", "user-agent"],
        log_errors_on_skip=True,
    )
)
```

### After (recommended)

```python
from fapilog.fastapi import FastAPIBuilder

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("production")
        .skip_paths(["/health", "/metrics"])
        .sample_rate(0.1)
        .include_headers(["content-type", "user-agent"])
        .log_errors_on_skip(True)
        .build()
)
```

## Parameter mapping

| setup_logging() parameter | FastAPIBuilder method |
|---------------------------|----------------------|
| `preset="production"` | `.with_preset("production")` |
| `skip_paths=[...]` | `.skip_paths([...])` |
| `sample_rate=0.1` | `.sample_rate(0.1)` |
| `include_headers=True` | Not needed (use `.include_headers()`) |
| `allow_headers=[...]` | `.include_headers([...])` |
| `log_errors_on_skip=True` | `.log_errors_on_skip(True)` |
| `redact_headers=[...]` | Use middleware directly |
| `additional_redact_headers=[...]` | Use middleware directly |

## Advanced configuration

With `FastAPIBuilder`, you now have access to all core fapilog options:

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("production")
        # FastAPI-specific
        .skip_paths(["/health"])
        .sample_rate(0.1)
        # Core options (not available with setup_logging)
        .with_backpressure(drop_on_full=False)
        .with_sampling(rate=0.1)  # Log-level sampling
        .with_redaction(preset="GDPR_PII")
        .with_queue_size(50000)
        .with_batch_size(100)
        .add_cloudwatch("/myapp/prod")
        .build()
)
```

## Environment variables

FastAPI-specific settings can now be configured via environment variables:

```bash
# FastAPI-specific env vars
FAPILOG_FASTAPI__SKIP_PATHS=/health,/metrics,/ready
FAPILOG_FASTAPI__INCLUDE_HEADERS=content-type,user-agent
FAPILOG_FASTAPI__SAMPLE_RATE=0.1
FAPILOG_FASTAPI__LOG_ERRORS_ON_SKIP=true
```

Environment variables take priority over code-specified values. When an override occurs, a warning is emitted via internal diagnostics:

```
Config override: sample_rate=1.0 overridden by FAPILOG_FASTAPI__SAMPLE_RATE=0.1
```

## Deprecation timeline

- **v0.14.0**: `setup_logging()` emits `DeprecationWarning`
- **v0.15.0** (planned): `setup_logging()` will be removed

## Need help?

If you encounter issues during migration, please [open an issue](https://github.com/chris-haste/fapilog/issues).
