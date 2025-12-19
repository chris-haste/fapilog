# Quickstart Tutorial

Get logging with fapilog in 2 minutes.

## Zero-Config Logging

The fastest way to start logging:

```python
from fapilog import get_logger

# Get a logger - no configuration needed
logger = get_logger()

# Start logging immediately
await logger.info("Application started")
await logger.error("Something went wrong", exc_info=True)
```

**Output:**

```json
{"timestamp": "2024-01-15T10:30:00.123Z", "level": "INFO", "message": "Application started"}
{"timestamp": "2024-01-15T10:30:01.456Z", "level": "ERROR", "message": "Something went wrong", "exception": "..."}
```

## With Context

Add request context automatically:

```python
from fapilog import get_logger

logger = get_logger()

# Add business context
await logger.info("User action", extra={
    "user_id": "123",
    "action": "login",
    "ip_address": "192.168.1.100"
})
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

For applications that need graceful shutdown:

```python
from fapilog import runtime

async def main():
    async with runtime() as logger:
        # Logging system is ready
        await logger.info("Processing started")

        # Your application code here
        await process_data()

        await logger.info("Processing completed")

    # Logger automatically cleaned up

asyncio.run(main())
```

## Async Logger Usage

For async applications, use the async logger for better performance:

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

        for i in range(100):
            await logger.debug(f"Processing item {i}")
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

1. **Environment detection** - Chooses best output format
2. **Async setup** - Configures non-blocking processing
3. **Context binding** - Sets up request correlation
4. **Resource management** - Handles memory and connections

## Environment Variables

Customize behavior with environment variables:

```bash
# Set log level
export FAPILOG_LEVEL=DEBUG

# Enable file logging
export FAPILOG_FILE__DIRECTORY=/var/log/myapp

# Enable metrics
export FAPILOG_ENABLE_METRICS=true
```

## Next Steps

- **[Hello World](hello-world.md)** - Complete walkthrough with examples
- **[Core Concepts](../core-concepts/index.md)** - Understand the architecture
- **[User Guide](../user-guide/index.md)** - Practical usage patterns

---

_You're now logging with fapilog! Ready for more? Try the [Hello World](hello-world.md) walkthrough._
