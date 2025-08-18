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

## What Happens Automatically

When you call `get_logger()`:

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
