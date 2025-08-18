# User Guide

Practical usage patterns and configuration for fapilog.

```{toctree}
:maxdepth: 2
:caption: User Guide

configuration
using-logger
context-enrichment
rotating-file-sink
redactors
graceful-shutdown
performance-tuning
integration-guide
```

## Overview

The User Guide covers everything you need to know to use fapilog effectively in real applications:

- **Configuration** - Environment variables, settings, and configuration
- **Using the Logger** - Logging methods, extra fields, exceptions
- **Context Enrichment** - Adding business context and correlation
- **Rotating File Sink** - File logging with rotation and retention
- **Redactors** - Data masking and security
- **Graceful Shutdown** - Proper cleanup and resource management
- **Performance Tuning** - Optimizing for your use case
- **Integration Guide** - FastAPI, Docker, Kubernetes

## Quick Reference

### Basic Logging

```python
from fapilog import get_logger

logger = get_logger()

# Standard logging methods
await logger.debug("Debug message")
await logger.info("Info message")
await logger.warning("Warning message")
await logger.error("Error message")
await logger.critical("Critical message")

# With extra fields
await logger.info("User action", extra={
    "user_id": "123",
    "action": "login",
    "ip_address": "192.168.1.100"
})
```

### Context Management

```python
from fapilog import bind, unbind

# Bind context for this request
bind(request_id="req-123", user_id="user-456")

# Log with automatic context
await logger.info("Request processed")

# Clear context when done
unbind()
```

### Configuration

```bash
# Basic configuration
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json

# File logging
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760

# Performance tuning
export FAPILOG_BATCH_MAX_SIZE=100
export FAPILOG_MAX_QUEUE_SIZE=8192
```

## What You'll Learn

1. **[Configuration](configuration.md)** - Environment variables, settings classes, and configuration hierarchy
2. **[Using the Logger](using-logger.md)** - All logging methods, extra fields, and exception handling
3. **[Context Enrichment](context-enrichment.md)** - Adding business context and correlation IDs
4. **[Rotating File Sink](rotating-file-sink.md)** - File logging with automatic rotation and compression
5. **[Redactors](redactors.md)** - Configuring data masking and security
6. **[Graceful Shutdown](graceful-shutdown.md)** - Proper cleanup with `runtime()` and `stop_and_drain()`
7. **[Performance Tuning](performance-tuning.md)** - Queue sizes, batching, and optimization
8. **[Integration Guide](integration-guide.md)** - FastAPI, Docker, Kubernetes, and more

## Common Patterns

### Request Logging

```python
from fapilog import get_logger

async def handle_request(request_id: str, user_id: str):
    logger = get_logger()

    # Log request start
    await logger.info("Request started", extra={
        "request_id": request_id,
        "user_id": user_id,
        "endpoint": "/api/users"
    })

    try:
        # Process request
        result = await process_request()

        # Log success
        await logger.info("Request completed", extra={
            "request_id": request_id,
            "status": "success",
            "duration_ms": 45
        })

        return result

    except Exception as e:
        # Log error with full context
        await logger.error("Request failed", exc_info=True, extra={
            "request_id": request_id,
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        raise
```

### Batch Processing

```python
from fapilog import runtime

async def process_batch(items):
    async with runtime() as logger:
        await logger.info("Batch processing started", extra={
            "batch_size": len(items),
            "batch_id": generate_batch_id()
        })

        for i, item in enumerate(items):
            try:
                await process_item(item)
                await logger.debug("Item processed", extra={
                    "item_index": i,
                    "item_id": item.id,
                    "status": "success"
                })
            except Exception as e:
                await logger.error("Item processing failed", extra={
                    "item_index": i,
                    "item_id": item.id,
                    "error": str(e)
                })

        await logger.info("Batch processing completed")
```

## Next Steps

- **[Core Concepts](../core-concepts/index.md)** - Understand the architecture
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[Examples](../examples/index.md)** - Real-world usage patterns

---

_The User Guide shows you how to use fapilog effectively in real applications._
