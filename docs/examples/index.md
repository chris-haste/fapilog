# Examples & Recipes

Real-world usage patterns and practical examples for fapilog.

```{toctree}
:maxdepth: 2
:titlesonly:
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
logger.info(
    "User action",
    user_id="123",
    action="login",
    timestamp="2024-01-15T10:30:00Z",
)
```

### Context Binding

```python
from fapilog import get_logger

logger = get_logger()

# Bind context for this request
logger.bind(request_id="req-123", user_id="user-456")

# Context automatically included
logger.info("Processing request")
logger.info("Request completed")

# Output includes request_id and user_id automatically
# Clear when done
logger.clear_context()
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
from fapilog import get_logger
import uuid

def handle_request(user_id: str):
    # Generate unique request ID
    request_id = str(uuid.uuid4())

    logger = get_logger()

    try:
        logger.bind(request_id=request_id, user_id=user_id)
        logger.info("Request started")

        # Process request
        result = process_request()

        logger.info("Request completed", status="success", duration_ms=45)

        return result

    except Exception as e:
        logger.error(
            "Request failed",
            exc=e,
            error_type=type(e).__name__,
            error_message=str(e),
        )
        raise
    finally:
        # Clean up context
        logger.clear_context()
```

### Batch Processing

```python
from fapilog import runtime_async

async def process_items(items):
    async with runtime_async() as logger:
        await logger.info("Batch processing started", batch_size=len(items))

        processed = 0
        failed = 0

        for item in items:
            try:
                await process_item(item)
                processed += 1

                if processed % 100 == 0:
                    await logger.info(
                        "Progress update",
                        processed=processed,
                        total=len(items),
                        progress_pct=(processed / len(items)) * 100,
                    )

            except Exception as e:
                failed += 1
                await logger.error(
                    "Item processing failed",
                    item_id=item.id,
                    exc=e,
                )

        await logger.info(
            "Batch processing completed",
            total=len(items),
            processed=processed,
            failed=failed,
            success_rate=(processed / len(items)) * 100,
        )
```

### Error Handling

```python
from fapilog import get_logger

logger = get_logger()

async def risky_operation():
    try:
        # Attempt operation
        result = await perform_operation()

        await logger.info("Operation successful", operation="risky_operation", result=result)

        return result

    except ValueError as e:
        # Handle specific error type
        await logger.warning(
            "Operation failed with invalid input",
            operation="risky_operation",
            error_type="ValueError",
            error_message=str(e),
            input_data=get_input_data(),
        )
        raise

    except Exception as e:
        # Handle unexpected errors
        await logger.error(
            "Operation failed unexpectedly",
            exc_info=True,
            operation="risky_operation",
            error_type=type(e).__name__,
            error_message=str(e),
            context=get_operation_context(),
        )
        raise
```

## Environment-Specific Examples

### Development

```python
# Development logging - verbose and human-readable
export FAPILOG_CORE__LOG_LEVEL=DEBUG
```

### Production

```python
# Production logging - structured and efficient
export FAPILOG_CORE__LOG_LEVEL=INFO
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

### Testing

```python
# Testing - minimal and fast
export FAPILOG_CORE__LOG_LEVEL=WARNING
export FAPILOG_CORE__ENABLE_METRICS=false
export FAPILOG_CORE__DROP_ON_FULL=true
```

## Next Steps

- **[User Guide](../user-guide/index.md)** - Learn practical usage patterns
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[Troubleshooting](../troubleshooting/index.md)** - Common issues and solutions

---

_These examples show you how to use fapilog effectively in real applications._
