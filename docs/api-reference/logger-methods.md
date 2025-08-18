# Logger Methods

All available logging methods for fapilog loggers.

## Overview

Logger instances provide several methods for logging messages at different levels.
All methods are async and should be awaited. Each method accepts a message string
and optional extra fields for structured logging.

## debug

```python
async def debug(self, message: str, **kwargs) -> None
```

Log a debug message.

Debug messages are typically used for detailed diagnostic information that is
only useful during development and debugging.

### Parameters

| Parameter  | Type  | Description                           |
| ---------- | ----- | ------------------------------------- |
| `message`  | `str` | The log message                       |
| `**kwargs` | `Any` | Additional structured data to include |

### Examples

```python
logger = get_logger()

# Basic debug message
await logger.debug("Processing user data")

# With extra fields
await logger.debug("Database query executed",
    query="SELECT * FROM users",
    duration_ms=45,
    rows_returned=100
)

# With exception info
try:
    result = await risky_operation()
except Exception as e:
    await logger.debug("Operation failed",
        operation="risky_operation",
        error=str(e)
    )
```

### Notes

- **Development only** - typically filtered out in production
- **Structured data** - use kwargs for additional context
- **Performance** - debug logging has minimal overhead
- **Level filtering** - controlled by `FAPILOG_LEVEL` setting

## info

```python
async def info(self, message: str, **kwargs) -> None
```

Log an informational message.

Info messages are used for general application events, user actions, and
operational information that is useful for monitoring and debugging.

### Parameters

| Parameter  | Type  | Description                           |
| ---------- | ----- | ------------------------------------- |
| `message`  | `str` | The log message                       |
| `**kwargs` | `Any` | Additional structured data to include |

### Examples

```python
logger = get_logger()

# Basic info message
await logger.info("Application started")

# With business context
await logger.info("User logged in",
    user_id="12345",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0..."
)

# With metrics
await logger.info("Request processed",
    endpoint="/api/users",
    method="GET",
    status_code=200,
    duration_ms=45
)
```

### Notes

- **Production logging** - typically enabled in all environments
- **Business events** - use for tracking user actions and system events
- **Structured context** - include relevant business data
- **Performance monitoring** - good for tracking request metrics

## warning

```python
async def warning(self, message: str, **kwargs) -> None
```

Log a warning message.

Warning messages indicate potential issues that don't prevent the application
from working but should be investigated.

### Parameters

| Parameter  | Type  | Description                           |
| ---------- | ----- | ------------------------------------- |
| `message`  | `str` | The log message                       |
| `**kwargs` | `Any` | Additional structured data to include |

### Examples

```python
logger = get_logger()

# Basic warning
await logger.warning("Database connection slow",
    connection_time_ms=5000,
    threshold_ms=1000
)

# Resource usage warning
await logger.warning("High memory usage detected",
    memory_usage_mb=1024,
    memory_limit_mb=2048,
    usage_percent=50
)

# Deprecation warning
await logger.warning("Deprecated API endpoint used",
    endpoint="/api/v1/users",
    alternative="/api/v2/users",
    client_ip="192.168.1.100"
)
```

### Notes

- **Investigation needed** - indicates potential problems
- **Not critical** - application continues to function
- **Monitoring** - good for alerting on trends
- **Performance impact** - minimal overhead

## error

```python
async def error(self, message: str, exc_info: bool = False, **kwargs) -> None
```

Log an error message.

Error messages indicate that something has gone wrong and the application
may not be functioning correctly.

### Parameters

| Parameter  | Type   | Default | Description                           |
| ---------- | ------ | ------- | ------------------------------------- |
| `message`  | `str`  | -       | The log message                       |
| `exc_info` | `bool` | `False` | Include exception traceback if True   |
| `**kwargs` | `Any`  | -       | Additional structured data to include |

### Examples

```python
logger = get_logger()

# Basic error
await logger.error("Failed to process user request")

# With exception info
try:
    result = await risky_operation()
except Exception as e:
    await logger.error("Operation failed",
        exc_info=True,
        operation="risky_operation",
        user_id="12345"
    )

# With context
await logger.error("Database connection failed",
    database="user_db",
    connection_string="postgresql://...",
    retry_attempt=3
)
```

### Notes

- **Exception handling** - use `exc_info=True` for full tracebacks
- **Critical issues** - indicates application problems
- **Alerting** - typically triggers monitoring alerts
- **Context important** - include relevant debugging information

## critical

```python
async def critical(self, message: str, exc_info: bool = False, **kwargs) -> None
```

Log a critical message.

Critical messages indicate severe problems that may cause the application
to fail or become unusable.

### Parameters

| Parameter  | Type   | Default | Description                           |
| ---------- | ------ | ------- | ------------------------------------- |
| `message`  | `str`  | -       | The log message                       |
| `exc_info` | `bool` | `False` | Include exception traceback if True   |
| `**kwargs` | `Any`  | -       | Additional structured data to include |

### Examples

```python
logger = get_logger()

# System failure
await logger.critical("Database cluster is down",
    cluster="prod-db-cluster",
    affected_services=["user-service", "order-service"],
    estimated_downtime="unknown"
)

# Security breach
await logger.critical("Unauthorized access detected",
    user_id="unknown",
    ip_address="192.168.1.100",
    attempted_action="admin_login",
    timestamp="2024-01-15T10:30:00Z"
)

# With exception
try:
    await critical_system_operation()
except Exception as e:
    await logger.critical("Critical system failure",
        exc_info=True,
        system="payment_processor",
        impact="payment_processing_unavailable"
    )
```

### Notes

- **Immediate attention** - requires immediate investigation
- **System impact** - indicates severe problems
- **High priority** - typically triggers immediate alerts
- **Business impact** - may affect core functionality

## exception

```python
async def exception(self, message: str, **kwargs) -> None
```

Log an exception message.

This is a convenience method that logs an error message with exception
information automatically included.

### Parameters

| Parameter  | Type  | Description                           |
| ---------- | ----- | ------------------------------------- |
| `message`  | `str` | The log message                       |
| `**kwargs` | `Any` | Additional structured data to include |

### Examples

```python
logger = get_logger()

# Basic exception logging
try:
    result = await risky_operation()
except Exception as e:
    await logger.exception("Operation failed",
        operation="risky_operation",
        user_id="12345"
    )

# With additional context
try:
    await process_payment(payment_data)
except PaymentError as e:
    await logger.exception("Payment processing failed",
        payment_id=payment_data.id,
        amount=payment_data.amount,
        currency=payment_data.currency
    )
```

### Notes

- **Exception info** - automatically includes traceback
- **Convenience method** - equivalent to `error(message, exc_info=True, **kwargs)`
- **Error handling** - use in exception handlers
- **Full context** - includes both message and exception details

## close

```python
async def close(self) -> None
```

Close the logger and cleanup resources.

This method should be called when you're done with the logger to ensure
proper cleanup of resources and flushing of any buffered messages.

### Parameters

None

### Returns

None

### Examples

```python
logger = get_logger()

try:
    await logger.info("Processing started")
    # ... do work ...
    await logger.info("Processing completed")
finally:
    await logger.close()  # Always cleanup

# Or use context manager
with runtime() as logger:
    await logger.info("Processing started")
    # ... do work ...
    await logger.info("Processing completed")
# Automatically closed
```

### Notes

- **Resource cleanup** - ensures all resources are freed
- **Message flushing** - flushes any buffered messages
- **Always call** - important for proper resource management
- **Context manager** - consider using `runtime()` for automatic cleanup

---

_These methods provide comprehensive logging capabilities for all levels of application events._
