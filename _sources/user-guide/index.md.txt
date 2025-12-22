# User Guide

Practical usage patterns and configuration for fapilog.

```{toctree}
:maxdepth: 2
:titlesonly:
:caption: User Guide

configuration
using-logger
context-enrichment
rotating-file-sink
redactors
graceful-shutdown
performance-tuning
integration-guide
fastapi
comparisons
reliability-defaults
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

### Basic Logging (sync)

```python
from fapilog import get_logger

logger = get_logger()
logger.debug("Debug message")
logger.info("Info message", user_id="123")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
```

### Basic Logging (async)

```python
from fapilog import get_async_logger

logger = await get_async_logger()
await logger.info("Async log entry", request_id="req-1")
await logger.error("Something went wrong", exc_info=True)
await logger.drain()
```

### Context Management

```python
logger = get_logger()

# Bind context for this request
logger.bind(request_id="req-123", user_id="user-456")

# Log with automatic context
logger.info("Request processed")

# Clear context when done
logger.clear_context()
```

### Configuration

```bash
# Basic configuration
export FAPILOG_CORE__LOG_LEVEL=INFO

# File logging
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760

# Performance tuning
export FAPILOG_CORE__BATCH_MAX_SIZE=100
export FAPILOG_CORE__MAX_QUEUE_SIZE=8192
```

## What You'll Learn

1. **[Configuration](configuration.md)** - Environment variables, settings classes, and configuration hierarchy
2. **[Using the Logger](using-logger.md)** - All logging methods, extra fields, and exception handling
3. **[Context Enrichment](context-enrichment.md)** - Adding business context and correlation IDs
4. **[Rotating File Sink](rotating-file-sink.md)** - File logging with automatic rotation and compression
5. **[Redactors](redactors.md)** - Configuring data masking and security
6. **[Graceful Shutdown](graceful-shutdown.md)** - Proper cleanup with `runtime()` / `runtime_async()`
7. **[Performance Tuning](performance-tuning.md)** - Queue sizes, batching, and optimization
8. **[Integration Guide](integration-guide.md)** - FastAPI, Docker, Kubernetes, and more

## Common Patterns

### Request Logging

```python
from fapilog import runtime_async

async def handle_request(request_id: str, user_id: str):
    async with runtime_async() as logger:
        logger.bind(request_id=request_id, user_id=user_id)
        await logger.info("Request started", endpoint="/api/users")
        try:
            result = await process_request()
            await logger.info("Request completed", status="success", duration_ms=45)
            return result
        except Exception:
            await logger.error("Request failed", exc_info=True)
            raise
```

### Batch Processing

```python
from fapilog import runtime

def process_batch(items):
    with runtime() as logger:
        logger.info("Batch processing started", batch_size=len(items))

        for i, item in enumerate(items):
            try:
                process_item(item)
                logger.debug("Item processed", item_index=i, item_id=item.id)
            except Exception as e:
                logger.error("Item processing failed", item_index=i, item_id=item.id, exc=e)

        logger.info("Batch processing completed")
```

## Next Steps

- **[Core Concepts](../core-concepts/index.md)** - Understand the architecture
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[Examples](../examples/index.md)** - Real-world usage patterns

---

_The User Guide shows you how to use fapilog effectively in real applications._
