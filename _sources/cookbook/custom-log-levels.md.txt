# Custom log levels in Python (TRACE, AUDIT, NOTICE)

Python's standard logging library provides five levels (DEBUG, INFO, WARNING, ERROR, CRITICAL), but real applications often need more granularity. Whether you're adding TRACE for detailed debugging, AUDIT for compliance events, or NOTICE for operational alerts, custom levels help you filter and route logs precisely.

## The Problem

The standard five log levels force awkward compromises:

```python
import logging

logger = logging.getLogger(__name__)

# Is this DEBUG or INFO? Neither fits well.
logger.debug("Entering function")  # Too verbose for normal debugging
logger.info("Entering function")   # Clutters INFO output

# Security events need special handling, but what level?
logger.info("User login", extra={"user_id": "123"})  # Lost in noise
logger.warning("User login", extra={"user_id": "123"})  # Not a warning

# Operational alerts that aren't errors
logger.warning("Disk usage at 80%")  # Is this really a warning?
logger.info("Disk usage at 80%")     # Might get filtered out
```

This creates problems:

1. **Lost granularity** - TRACE events pollute DEBUG, or get omitted entirely
2. **No audit trail** - Security events mixed with application logs
3. **Filtering headaches** - Can't route AUDIT to a separate sink without custom code
4. **Inconsistent severity** - Teams disagree on what level to use

## The Solution

fapilog lets you register custom levels before creating loggers:

```python
import fapilog

# Register custom levels BEFORE creating any loggers
fapilog.register_level("TRACE", priority=5, add_method=True)
fapilog.register_level("AUDIT", priority=25, add_method=True)
fapilog.register_level("NOTICE", priority=35, add_method=True)

# Now create your logger
logger = fapilog.get_logger()

# Use custom levels naturally
logger.trace("Entering function", function="process_order")
logger.audit("User login", user_id="123", ip_address="192.168.1.1")
logger.notice("Disk usage elevated", percent=80, mount="/data")
logger.info("Order processed", order_id="456")
```

The `add_method=True` parameter generates `logger.trace()`, `logger.audit()`, etc. as callable methods.

## Priority Values

Priorities determine filtering order. Lower values are more verbose:

| Level    | Priority | Use Case                              |
|----------|----------|---------------------------------------|
| TRACE    | 5        | Function entry/exit, loop iterations  |
| DEBUG    | 10       | Variable values, decision branches    |
| INFO     | 20       | Normal operations, milestones         |
| AUDIT    | 25       | Security events, compliance logging   |
| WARNING  | 30       | Degraded performance, deprecations    |
| NOTICE   | 35       | Operational alerts, threshold alerts  |
| ERROR    | 40       | Failures that don't stop the app      |
| CRITICAL | 50       | System failures, data corruption      |

Custom levels integrate with fapilog's level filtering. Setting `min_level="AUDIT"` filters out TRACE, DEBUG, and INFO.

## Routing Custom Levels to Separate Sinks

Route specific levels to dedicated outputs:

```python
import fapilog
from fapilog.sinks import StdoutSink, FileSink
from fapilog.filters import LevelFilter

# Register custom level
fapilog.register_level("AUDIT", priority=25, add_method=True)

# Create sinks with different filters
console_sink = StdoutSink(
    filters=[LevelFilter(min_level="INFO")]  # INFO and above to console
)

audit_sink = FileSink(
    path="/var/log/audit.jsonl",
    filters=[LevelFilter(min_level="AUDIT", max_level="AUDIT")]  # AUDIT only
)

# Configure logger with multiple sinks
logger = fapilog.get_logger(sinks=[console_sink, audit_sink])

# AUDIT goes to both console AND audit file
logger.audit("Password changed", user_id="123")

# INFO goes only to console
logger.info("Request completed")
```

## Async Logger Support

Custom levels work identically with async loggers:

```python
import fapilog

fapilog.register_level("TRACE", priority=5, add_method=True)
fapilog.register_level("AUDIT", priority=25, add_method=True)

async def main():
    logger = await fapilog.get_async_logger()

    await logger.trace("Starting async operation")
    await logger.audit("API key created", key_id="abc123")
    await logger.info("Operation complete")
```

## Common Custom Level Patterns

### TRACE for Debugging

```python
fapilog.register_level("TRACE", priority=5, add_method=True)

logger = fapilog.get_logger()

def calculate_total(items):
    logger.trace("Entering calculate_total", item_count=len(items))
    total = 0
    for item in items:
        logger.trace("Processing item", item_id=item["id"], price=item["price"])
        total += item["price"]
    logger.trace("Exiting calculate_total", total=total)
    return total
```

### AUDIT for Compliance

```python
fapilog.register_level("AUDIT", priority=25, add_method=True)

logger = fapilog.get_logger()

def change_password(user_id: str, new_password: str):
    # Business logic here...
    logger.audit(
        "Password changed",
        user_id=user_id,
        event_type="security.password_change",
        compliance=["SOC2", "GDPR"]
    )
```

### NOTICE for Operations

```python
fapilog.register_level("NOTICE", priority=35, add_method=True)

logger = fapilog.get_logger()

def check_disk_usage():
    usage = get_disk_usage_percent()
    if usage > 80:
        logger.notice(
            "Disk usage elevated",
            percent=usage,
            threshold=80,
            mount="/data"
        )
    elif usage > 95:
        logger.error("Disk nearly full", percent=usage)
```

## Registration Timing

Custom levels must be registered before creating loggers:

```python
import fapilog

# This works
fapilog.register_level("TRACE", priority=5, add_method=True)
logger = fapilog.get_logger()
logger.trace("Works!")

# This raises RuntimeError
logger2 = fapilog.get_logger()
fapilog.register_level("AUDIT", priority=25)  # RuntimeError: Registry is frozen
```

The registry freezes when the first logger is created. This prevents inconsistent behavior where some loggers have custom levels and others don't.

### Application Startup Pattern

Register all custom levels in your application's entry point:

```python
# app/logging_config.py
import fapilog

def configure_logging():
    """Call once at application startup, before any imports that create loggers."""
    fapilog.register_level("TRACE", priority=5, add_method=True)
    fapilog.register_level("AUDIT", priority=25, add_method=True)
    fapilog.register_level("NOTICE", priority=35, add_method=True)

# app/main.py
from app.logging_config import configure_logging

configure_logging()  # Must be first!

from fastapi import FastAPI
from app.routes import router  # Now safe to import modules that create loggers
```

## Going Deeper

- [Using the Logger](../user-guide/using-logger.md) - Logger methods and patterns
- [Sink Routing](../user-guide/sink-routing.md) - Route logs to different destinations
- [Configuration](../user-guide/configuration.md) - Full configuration options
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
