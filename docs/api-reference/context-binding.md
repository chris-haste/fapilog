# Context Binding

Request context and correlation management for fapilog.

## Overview

Context binding allows you to attach request-scoped information to all log
messages automatically. This is essential for distributed tracing, debugging,
and understanding the flow of operations through your system.

## bind

```python
def bind(**kwargs) -> None
```

Bind context variables to the current request.

This function attaches key-value pairs to the current execution context.
All subsequent log messages will automatically include these values.

### Parameters

| Parameter  | Type  | Description                            |
| ---------- | ----- | -------------------------------------- |
| `**kwargs` | `Any` | Key-value pairs to bind to the context |

### Examples

```python
from fapilog import bind, get_logger

# Basic context binding
bind(request_id="req-123", user_id="user-456")

logger = get_logger()
await logger.info("Request started")
# Output includes: {"request_id": "req-123", "user_id": "user-456"}

# Multiple context variables
bind(
    service_name="user-service",
    environment="production",
    version="1.2.3",
    deployment_id="deploy-abc123"
)

# Nested context
bind(
    user=dict(
        id="user-123",
        role="admin",
        permissions=["read", "write", "delete"]
    ),
    request=dict(
        method="POST",
        endpoint="/api/users",
        client_ip="192.168.1.100"
    )
)
```

### Notes

- **Request-scoped** - context is isolated to the current request
- **Automatic inheritance** - child tasks inherit parent context
- **Structured data** - supports complex nested structures
- **Performance** - minimal overhead for context binding
- **Thread-safe** - works across multiple threads and async tasks

## unbind

```python
def unbind(*keys: str) -> None
```

Remove specific context variables.

This function removes the specified keys from the current context. If no
keys are provided, it removes all context variables.

### Parameters

| Parameter | Type  | Description                                         |
| --------- | ----- | --------------------------------------------------- |
| `*keys`   | `str` | Keys to remove from context. If empty, removes all. |

### Examples

```python
from fapilog import bind, unbind, get_logger

# Bind some context
bind(request_id="req-123", user_id="user-456", temp_flag="debug")

logger = get_logger()
await logger.info("With all context")

# Remove specific keys
unbind("temp_flag", "user_id")
await logger.info("With partial context")
# Output includes: {"request_id": "req-123"}

# Remove all context
unbind()
await logger.info("No context")
# Output has no context variables
```

### Notes

- **Selective removal** - can remove specific keys while keeping others
- **Complete cleanup** - `unbind()` removes all context variables
- **Immediate effect** - changes take effect for the next log message
- **Safe operation** - removing non-existent keys is harmless

## clear_context

```python
def clear_context() -> None
```

Clear all context variables.

This is an alias for `unbind()` with no arguments. It removes all
context variables from the current execution context.

### Parameters

None

### Returns

None

### Examples

```python
from fapilog import bind, clear_context, get_logger

# Bind context
bind(request_id="req-123", user_id="user-456")

logger = get_logger()
await logger.info("With context")

# Clear all context
clear_context()
await logger.info("Context cleared")
# Output has no context variables
```

### Notes

- **Complete cleanup** - removes all context variables
- **Equivalent to unbind()** - same functionality as `unbind()`
- **Common pattern** - useful for explicit context management
- **Request boundaries** - typically called at request end

## Context Inheritance

Context binding automatically inherits across async boundaries:

```python
from fapilog import bind, get_logger
import asyncio

async def main():
    # Bind context in main function
    bind(request_id="req-123", user_id="user-456")

    # Spawn child tasks
    task1 = asyncio.create_task(child_task("task1"))
    task2 = asyncio.create_task(child_task("task2"))

    await asyncio.gather(task1, task2)

async def child_task(name):
    # Automatically inherits request_id and user_id from parent
    logger = get_logger()
    await logger.info(f"{name} started")
    # Output includes: {"request_id": "req-123", "user_id": "user-456"}

# Run the example
asyncio.run(main())
```

## Common Patterns

### Request Context

```python
from fapilog import bind, unbind, get_logger
import uuid

async def handle_request(user_id: str):
    # Generate unique request ID
    request_id = str(uuid.uuid4())

    # Bind context for this request
    bind(
        request_id=request_id,
        user_id=user_id,
        timestamp=datetime.utcnow().isoformat()
    )

    try:
        logger = get_logger()
        await logger.info("Request started")

        # Process request
        result = await process_request()

        await logger.info("Request completed", extra={
            "status": "success",
            "duration_ms": 45
        })

        return result

    except Exception as e:
        await logger.error("Request failed", exc_info=True)
        raise
    finally:
        # Clean up context
        unbind()
```

### Service Context

```python
from fapilog import bind

# Bind service-level context (typically done at startup)
bind(
    service_name="user-service",
    environment="production",
    version="1.2.3",
    region="us-west-2"
)

# This context is inherited by all requests
async def process_user(user_id: str):
    logger = get_logger()

    # Add request-specific context
    bind(request_id=str(uuid.uuid4()), user_id=user_id)

    try:
        await logger.info("Processing user")
        # ... do work ...
    finally:
        # Remove request context, keep service context
        unbind("request_id", "user_id")
```

### Debug Context

```python
from fapilog import bind, unbind

async def debug_operation():
    # Add debug context
    bind(debug_mode=True, trace_id=str(uuid.uuid4()))

    try:
        logger = get_logger()
        await logger.debug("Debug operation started")
        # ... do work ...
        await logger.debug("Debug operation completed")
    finally:
        # Remove debug context
        unbind("debug_mode", "trace_id")
```

## Best Practices

1. **Bind early** - Set context as soon as you have the information
2. **Clean up** - Always call `unbind()` or `clear_context()` when done
3. **Use meaningful keys** - Choose descriptive names for context variables
4. **Keep it simple** - Avoid deeply nested structures for better performance
5. **Request boundaries** - Clear context at request end
6. **Async awareness** - Context automatically inherits across async boundaries

## Performance Considerations

- **Minimal overhead** - Context binding has very low performance impact
- **Memory efficient** - Context variables are stored efficiently
- **Fast lookup** - Context retrieval is optimized for speed
- **Async safe** - No locks or blocking operations

---

_Context binding provides powerful correlation and debugging capabilities for distributed systems._
