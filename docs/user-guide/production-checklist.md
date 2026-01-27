# Production Checklist

Pre-deployment checklist for fapilog in production environments.

## 1. Choose Your Configuration Approach

- [ ] **Preset** or **Auto-detect** or **Custom Settings**?

| Approach | When to Use |
|----------|-------------|
| `preset="production"` | General backend services |
| `preset="fastapi"` | FastAPI applications |
| `preset="serverless"` | AWS Lambda, Cloud Functions |
| `auto_detect=True` | Let fapilog detect environment |
| Custom `Settings()` | Fine-grained control needed |

> See: [Configuration](configuration.md)

## 2. Enable Observability

### Metrics

- [ ] Enable metrics collection
- [ ] Configure metrics export (application-level)

```bash
export FAPILOG_CORE__ENABLE_METRICS=true
```

Fapilog records events submitted/dropped, queue high-watermark, backpressure waits, and flush latency. Expose these via your preferred exporter.

> See: [Metrics](../core-concepts/metrics.md)

### Diagnostics

- [ ] Understand diagnostics output location (stderr by default)
- [ ] Consider enabling internal logging for debugging

```bash
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
```

Diagnostics emit warnings for worker errors, sink errors, backpressure drops, and serialization issues.

> See: [Diagnostics & Resilience](../core-concepts/diagnostics-resilience.md)

## 3. Validate Redaction

- [ ] Review what gets redacted vs what doesn't
- [ ] Test redaction with production-like data
- [ ] Decide on `redaction_fail_mode` (warn vs closed)

```python
# Test redaction before deployment
from fapilog import get_logger

logger = get_logger(preset="production")
logger.info("Test", password="secret123", email="user@example.com")
# Verify output shows: password="***", email="***"
```

> **Warning:** Redaction is pattern-based, not content-aware.
> PII in message strings is NOT redacted.

> See: [Redaction Behavior](../redaction/behavior.md), [Testing Redaction](../redaction/testing.md)

## 4. Configure Backpressure

- [ ] Size queue for expected burst load
- [ ] Decide drop vs wait behavior
- [ ] Monitor for dropped events

```bash
# High-throughput settings
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__DROP_ON_FULL=true  # or false to wait
```

> See: [Troubleshooting Dropped Logs](../troubleshooting/logs-dropped-under-load.md)

## 5. Sink Configuration

- [ ] Configure production sinks (file, HTTP, cloud)
- [ ] Verify sink credentials/endpoints
- [ ] Test sink connectivity

> See: [CloudWatch](../plugins/sinks/cloudwatch.md), [Loki](../plugins/sinks/loki.md), [PostgreSQL](../plugins/sinks/postgres.md)

## 6. Graceful Shutdown

- [ ] Ensure application calls `logger.drain()` or uses context manager
- [ ] Verify shutdown handlers are installed (automatic with presets)

```python
# Option 1: Context manager (recommended for sync code)
from fapilog import runtime

with runtime() as logger:
    # application code
    pass  # Automatic drain on exit

# Option 2: Async context manager
from fapilog import runtime_async

async with runtime_async() as logger:
    await logger.info("Processing...")
    # Automatic drain on exit

# Option 3: Manual drain
logger = get_logger(preset="production")
# ... application code ...
await logger.drain()
```

> See: [Graceful Shutdown](graceful-shutdown.md)

## Quick Validation Script

```python
"""Run this script to validate production readiness."""
import asyncio
from fapilog import get_async_logger


async def validate_production_config():
    logger = await get_async_logger(preset="production")

    # Test basic logging
    await logger.info("Production validation test")

    # Test redaction
    await logger.info("Redaction test", password="SHOULD_BE_MASKED")

    # Test error logging
    try:
        raise ValueError("Test exception")
    except Exception:
        await logger.exception("Exception test")

    # Drain and report
    result = await logger.drain()
    print(f"Validation complete: {result.events_flushed} events flushed")


if __name__ == "__main__":
    asyncio.run(validate_production_config())
```
