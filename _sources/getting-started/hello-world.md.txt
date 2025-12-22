# Hello World Walkthrough

Complete walkthrough with real examples.

## Minimal App

Start with the simplest possible logging:

```python
from fapilog import get_logger

def main():
    # Get a logger - zero configuration
    logger = get_logger()

    # Basic logging (sync methods)
    logger.info("Hello, World!")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")

if __name__ == "__main__":
    main()
```

**Run it:**

```bash
python hello_world.py
```

**Output:**

```json
{"timestamp": "2024-01-15T10:30:00.123Z", "level": "INFO", "message": "Hello, World!"}
{"timestamp": "2024-01-15T10:30:00.124Z", "level": "DEBUG", "message": "Debug message"}
{"timestamp": "2024-01-15T10:30:00.125Z", "level": "WARNING", "message": "Warning message"}
{"timestamp": "2024-01-15T10:30:00.126Z", "level": "ERROR", "message": "Error message"}
```

## Rotating File Sink Example

Configure file logging with rotation:

```python
import asyncio
import os
from fapilog import get_logger

async def main():
    # Set environment for file logging
    os.environ["FAPILOG_FILE__DIRECTORY"] = "./logs"
    os.environ["FAPILOG_FILE__MAX_BYTES"] = "1024"  # 1KB for demo
    os.environ["FAPILOG_FILE__MAX_FILES"] = "3"

    logger = get_logger()

    # Generate some logs
    for i in range(5):
        logger.info(
            "Log message",
            iteration=i,
            timestamp=f"2024-01-15T10:30:{i:02d}Z",
        )

if __name__ == "__main__":
    asyncio.run(main())
```

**Check the logs:**

```bash
ls -la logs/
# You'll see rotating files like:
# fapilog.log
# fapilog.log.1
# fapilog.log.2.gz
```

## Redactor Demo

See automatic data redaction in action:

```python
import asyncio
from fapilog import get_logger

async def main():
    logger = get_logger()

    # Log sensitive data
    logger.info(
        "User credentials",
        username="john_doe",
        password="secret123",  # This will be redacted by regex redactor
        api_key="sk-1234567890abcdef",  # This too
        email="john@example.com",  # This will be redacted
    )

    # Log business data (safe)
    logger.info(
        "User profile",
        user_id="12345",
        preferences={"theme": "dark", "language": "en"},
        last_login="2024-01-15T10:30:00Z",
    )

if __name__ == "__main__":
    asyncio.run(main())
```

**Output (with redaction):**

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "message": "User credentials",
  "username": "john_doe",
  "password": "***REDACTED***",
  "api_key": "***REDACTED***",
  "email": "***REDACTED***"
}
```

Redaction is enabled by default (order: `field-mask`, `regex-mask`, `url-credentials`). To disable globally, set `FAPILOG_CORE__ENABLE_REDACTORS=false`. Tune ordering/paths via `redactors_order` and the relevant redactor settings.

## Stopping & Draining Logs

Proper cleanup ensures all logs are written:

```python
import asyncio
from fapilog import runtime_async

async def main():
    async with runtime_async() as logger:
        # Log some messages
        await logger.info("Processing started")

        # Simulate work
        for i in range(10):
            await logger.info("Processing item", index=i)
            await asyncio.sleep(0.1)  # Simulate work

        await logger.info("Processing completed")

    # All logs are automatically drained and written
    print("✅ All logs written successfully!")

if __name__ == "__main__":
    asyncio.run(main())
```

## Complete Example

Here's a complete application that demonstrates everything:

```python
import asyncio
import os
from fapilog import runtime_async

async def process_user(user_id: str, logger):
    """Process a user with structured logging."""
    await logger.info("Processing user", user_id=user_id)

    # Simulate some work
    await asyncio.sleep(0.1)

    # Log progress
    await logger.info(
        "User processed",
        user_id=user_id,
        status="success",
        processing_time_ms=100,
    )

async def main():
    # Configure file logging
    os.environ["FAPILOG_FILE__DIRECTORY"] = "./logs"
    os.environ["FAPILOG_CORE__LOG_LEVEL"] = "DEBUG"

    async with runtime_async() as logger:
        await logger.info("Application started")

        # Process multiple users
        users = ["user1", "user2", "user3"]
        tasks = [process_user(user_id, logger) for user_id in users]

        await asyncio.gather(*tasks)

        await logger.info("All users processed")

    print("✅ Application completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
```

## What You've Learned

1. **Zero-config logging** - `get_logger()` works immediately
2. **File rotation** - Automatic log file management
3. **Data redaction** - Sensitive data automatically masked
4. **Graceful shutdown** - `runtime()` ensures cleanup
5. **Structured logging** - JSON output with extra fields

## Next Steps

- **[Core Concepts](../core-concepts/index.md)** - Understand the architecture
- **[User Guide](../user-guide/index.md)** - Learn practical patterns
- **[API Reference](../api-reference/index.md)** - Complete API documentation

---

_You've completed the Hello World walkthrough! Ready to dive deeper into [Core Concepts](../core-concepts/index.md)?_
