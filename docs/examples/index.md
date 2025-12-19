# Examples & Recipes

Real-world usage patterns and practical examples for fapilog.

```{toctree}
:maxdepth: 2
:caption: Examples & Recipes

fastapi-logging
cli-tools
redacting-secrets
structured-error-logging
kubernetes-file-sink
prometheus-metrics
sampling-debug-logs
```

## Overview

These examples show fapilog in action across different use cases and environments:

- **FastAPI Logging** - Request/response IDs and middleware
- **CLI Tools** - Using `runtime()` for command-line applications
- **Redacting Secrets** - Password and token masking
- **Structured Error Logging** - Exception handling with context
- **Kubernetes File Sink** - Containerized logging with rotation
- **Prometheus Metrics** - Monitoring and observability
- **Sampling Debug Logs** - Development vs production logging

## Quick Examples

### Basic Logging

```python
from fapilog import get_logger

logger = get_logger()

# Simple logging
logger.info("Application started")

# With structured data
logger.info("User action", extra={
    "user_id": "123",
    "action": "login",
    "timestamp": "2024-01-15T10:30:00Z"
})
```

### Context Binding

```python
from fapilog import bind, get_logger

# Bind context for this request
bind(request_id="req-123", user_id="user-456")

logger = get_logger()

# Context automatically included
logger.info("Processing request")
logger.info("Request completed")

# Output includes request_id and user_id automatically
```

### File Logging

```python
import os
from fapilog import get_logger

# Configure file logging
os.environ["FAPILOG_FILE__DIRECTORY"] = "./logs"
os.environ["FAPILOG_FILE__MAX_BYTES"] = "1048576"  # 1MB
os.environ["FAPILOG_FILE__MAX_FILES"] = "5"

logger = get_logger()

# Logs go to rotating files
for i in range(1000):
    logger.info(f"Log message {i}")
```

## What You'll Learn

1. **[FastAPI Logging](fastapi-logging.md)** - Request correlation and middleware integration
2. **[CLI Tools](cli-tools.md)** - Command-line applications with proper cleanup
3. **[Redacting Secrets](redacting-secrets.md)** - Data masking and security
4. **[Structured Error Logging](structured-error-logging.md)** - Exception handling with context
5. **[Kubernetes File Sink](kubernetes-file-sink.md)** - Containerized logging best practices
6. **[Prometheus Metrics](prometheus-metrics.md)** - Monitoring and observability integration
7. **[Sampling Debug Logs](sampling-debug-logs.md)** - Development vs production strategies

## Common Patterns

### Request Correlation

```python
from fapilog import bind, get_logger
import uuid

async def handle_request(user_id: str):
    # Generate unique request ID
    request_id = str(uuid.uuid4())

    # Bind context for this request
    bind(request_id=request_id, user_id=user_id)

    logger = get_logger()

    try:
        logger.info("Request started")

        # Process request
        result = await process_request()

        logger.info("Request completed", extra={
            "status": "success",
            "duration_ms": 45
        })

        return result

    except Exception as e:
        await logger.error("Request failed", exc_info=True, extra={
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        raise
    finally:
        # Clean up context
        unbind()
```

### Batch Processing

```python
from fapilog import runtime

async def process_items(items):
    async with runtime() as logger:
        await logger.info("Batch processing started", extra={
            "batch_size": len(items),
            "batch_id": generate_batch_id()
        })

        processed = 0
        failed = 0

        for item in items:
            try:
                await process_item(item)
                processed += 1

                if processed % 100 == 0:
                    await logger.info("Progress update", extra={
                        "processed": processed,
                        "total": len(items),
                        "progress_pct": (processed / len(items)) * 100
                    })

            except Exception as e:
                failed += 1
                await logger.error("Item processing failed", extra={
                    "item_id": item.id,
                    "error": str(e)
                })

        await logger.info("Batch processing completed", extra={
            "total": len(items),
            "processed": processed,
            "failed": failed,
            "success_rate": (processed / len(items)) * 100
        })
```

### Error Handling

```python
from fapilog import get_logger

logger = get_logger()

async def risky_operation():
    try:
        # Attempt operation
        result = await perform_operation()

        await logger.info("Operation successful", extra={
            "operation": "risky_operation",
            "result": result
        })

        return result

    except ValueError as e:
        # Handle specific error type
        await logger.warning("Operation failed with invalid input", extra={
            "operation": "risky_operation",
            "error_type": "ValueError",
            "error_message": str(e),
            "input_data": get_input_data()
        })
        raise

    except Exception as e:
        # Handle unexpected errors
        await logger.error("Operation failed unexpectedly", exc_info=True, extra={
            "operation": "risky_operation",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "context": get_operation_context()
        })
        raise
```

## Environment-Specific Examples

### Development

```python
# Development logging - verbose and human-readable
export FAPILOG_LEVEL=DEBUG
export FAPILOG_FORMAT=pretty
export FAPILOG_ENABLE_METRICS=false
```

### Production

```python
# Production logging - structured and efficient
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json
export FAPILOG_ENABLE_METRICS=true
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

### Testing

```python
# Testing - minimal and fast
export FAPILOG_LEVEL=WARNING
export FAPILOG_FORMAT=json
export FAPILOG_ENABLE_METRICS=false
export FAPILOG_DROP_ON_FULL=true
```

## Next Steps

- **[User Guide](../user-guide/index.md)** - Learn practical usage patterns
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues and solutions

---

_These examples show you how to use fapilog effectively in real applications._
