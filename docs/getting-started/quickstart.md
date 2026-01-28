# Quickstart Tutorial

Get logging with fapilog in 2 minutes.

> **Choosing async vs sync:** Your log calls never block on I/O—both `get_logger()` and `get_async_logger()` write to background workers. A slow sink won't stall your app. The only difference is the calling API: use `get_logger()` for sync code, `get_async_logger()` when you want `await` syntax.

## Zero-Config Logging

The fastest way to start logging:

```python
from fapilog import get_logger

# Get a logger - no configuration needed (sync, non-awaitable methods)
logger = get_logger()

# Start logging immediately
logger.info("Application started")
logger.error("Something went wrong", exc_info=True)
```

**Output:**

```json
{"timestamp": "2024-01-15T10:30:00.123Z", "level": "INFO", "message": "Application started"}
{"timestamp": "2024-01-15T10:30:01.456Z", "level": "ERROR", "message": "Something went wrong", "exception": "..."}
```

## With Context

Bind context once, then it’s added automatically to each log entry:

```python
from fapilog import get_logger

logger = get_logger()

# Bind business context
logger.bind(user_id="123", ip_address="192.168.1.100")

logger.info("User action", action="login")
```

**Output:**

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "message": "User action",
  "user_id": "123",
  "action": "login",
  "ip_address": "192.168.1.100"
}
```

## Using runtime() for Cleanup

For applications that need graceful shutdown of the background worker (sync API):

```python
from fapilog import runtime

def main():
    with runtime() as logger:
        # Logging system is ready
        logger.info("Processing started")

        # Your application code here
        process_data()

        logger.info("Processing completed")

    # Logger automatically cleaned up

if __name__ == "__main__":
    main()
```

## Async Logger Usage

For async applications, use the async logger for native `await` syntax:

```python
from fapilog import get_async_logger, runtime_async

# Get an async logger
logger = await get_async_logger("my_service")

# All methods are awaitable
await logger.info("Async operation started")
await logger.debug("Processing data", data_size=1000)
await logger.error("Operation failed", error_code=500)

# Clean up when done
await logger.drain()
```

### Async Context Manager

Use `runtime_async` for automatic lifecycle management:

```python
async def process_batch():
    async with runtime_async() as logger:
        await logger.info("Batch processing started")

        for i in range(5):
            await logger.debug("Processing item", index=i)
            # ... your async processing code ...

        await logger.info("Batch processing completed")
    # Logger automatically drained on exit
```

### FastAPI Integration

Perfect for FastAPI applications with dependency injection:

```python
from fastapi import Depends, FastAPI
from fapilog import get_async_logger

app = FastAPI()

async def get_logger():
    return await get_async_logger("request")

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger = Depends(get_logger)):
    await logger.info("User lookup requested", user_id=user_id)
    # ... your code ...
    await logger.info("User found", user_id=user_id)
    return {"user_id": user_id}
```

## What Happens Automatically

When you call `get_logger()` or `get_async_logger()`:

1. **Environment detection** - Chooses best output format for your environment
2. **Background worker startup** - Creates async worker tasks for non-blocking I/O
3. **Queue setup** - Configures the buffer between your code and sink writes
4. **Context binding** - Sets up request correlation and context propagation

Your log calls enqueue and return immediately—actual sink I/O happens in background workers. A slow disk or network sink won't affect your application's response time.

## Environment Variables

Customize behavior with environment variables:

```bash
# Set log level (observability.logging.sampling also available)
export FAPILOG_CORE__LOG_LEVEL=DEBUG

# Enable file logging
export FAPILOG_FILE__DIRECTORY=/var/log/myapp

# Enable metrics
export FAPILOG_CORE__ENABLE_METRICS=true
```

Need the full matrix of supported env vars and short aliases? See [Environment Variables](../user-guide/environment-variables.md).

## Next Steps

**Ready to customize?** Choose your configuration approach:

```python
# Option 1: Presets - sensible defaults, minimal code
logger = get_logger(preset="production")

# Option 2: Builder - IDE autocomplete, full control
from fapilog import LoggerBuilder
logger = LoggerBuilder().with_preset("production").with_redaction(preset="GDPR_PII").build()
```

See [Configuration](../user-guide/configuration.md) for guidance on which approach fits your needs.

## Minimal Production Configuration

For production deployments, explicitly configure drop policy and redaction failure handling:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_backpressure(drop_on_full=False)      # Wait rather than drop under pressure
    .with_fallback_redaction(fail_mode="warn")  # Log warning if redaction fails
    .build()
)
```

Or via environment variables:

```bash
export FAPILOG_CORE__DROP_ON_FULL=false
export FAPILOG_CORE__REDACTION_FAIL_MODE=warn
```

See [Reliability Defaults](../user-guide/reliability-defaults.md) for the complete production checklist.

**Learn more:**

- **[Hello World](hello-world.md)** - Complete walkthrough with examples
- **[Configuration](../user-guide/configuration.md)** - Presets, Builder, and Settings comparison
- **[Core Concepts](../core-concepts/index.md)** - Understand the architecture
- **[Cookbook](../cookbook/index.md)** - Recipes for common patterns

---

_You're now logging with fapilog! Ready for more? Try the [Hello World](hello-world.md) walkthrough._
