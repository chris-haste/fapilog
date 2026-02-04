# Custom log levels in Python (TRACE, VERBOSE, NOTICE)

Python's standard logging library provides five levels (DEBUG, INFO, WARNING, ERROR, CRITICAL), but real applications often need more granularity. Whether you're adding TRACE for detailed debugging, VERBOSE for extra context, or NOTICE for operational alerts, custom levels help you filter and route logs precisely.

> **Note:** fapilog includes AUDIT (60) and SECURITY (70) as built-in levels above CRITICAL. Use `logger.audit()` and `logger.security()` directly without registration. This guide covers adding *additional* custom levels.

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
fapilog.register_level("VERBOSE", priority=15, add_method=True)
fapilog.register_level("NOTICE", priority=35, add_method=True)

# Now create your logger
logger = fapilog.get_logger()

# Use custom levels naturally
logger.trace("Entering function", function="process_order")
logger.verbose("Request details", headers={"X-Request-Id": "abc"})
logger.notice("Disk usage elevated", percent=80, mount="/data")
logger.info("Order processed", order_id="456")

# Built-in AUDIT and SECURITY work without registration
logger.audit("User login", user_id="123", ip_address="192.168.1.1")
logger.security("Failed auth attempt", user_id="123", attempts=5)
```

The `add_method=True` parameter generates `logger.trace()`, `logger.verbose()`, etc. as callable methods.

## Priority Values

Priorities determine filtering order. Lower values are more verbose:

| Level    | Priority | Type     | Use Case                              |
|----------|----------|----------|---------------------------------------|
| TRACE    | 5        | Custom   | Function entry/exit, loop iterations  |
| DEBUG    | 10       | Built-in | Variable values, decision branches    |
| VERBOSE  | 15       | Custom   | Extra context, request details        |
| INFO     | 20       | Built-in | Normal operations, milestones         |
| WARNING  | 30       | Built-in | Degraded performance, deprecations    |
| NOTICE   | 35       | Custom   | Operational alerts, threshold alerts  |
| ERROR    | 40       | Built-in | Failures that don't stop the app      |
| CRITICAL | 50       | Built-in | System failures, data corruption      |
| AUDIT    | 60       | Built-in | Compliance events, accountability     |
| SECURITY | 70       | Built-in | Security events, threat detection     |

Custom levels integrate with fapilog's level filtering. Setting `min_level="AUDIT"` filters out everything below priority 60.

## Routing Levels to Separate Sinks

Route specific levels to dedicated outputs:

```python
import fapilog
from fapilog.sinks import StdoutSink, FileSink
from fapilog.filters import LevelFilter

# Create sinks with different filters
console_sink = StdoutSink(
    filters=[LevelFilter(min_level="INFO")]  # INFO and above to console
)

audit_sink = FileSink(
    path="/var/log/audit.jsonl",
    filters=[LevelFilter(min_level="AUDIT", max_level="AUDIT")]  # AUDIT only
)

security_sink = FileSink(
    path="/var/log/security.jsonl",
    filters=[LevelFilter(min_level="SECURITY")]  # SECURITY only (highest level)
)

# Configure logger with multiple sinks
logger = fapilog.get_logger(sinks=[console_sink, audit_sink, security_sink])

# AUDIT goes to console AND audit file
logger.audit("Password changed", user_id="123")

# SECURITY goes to console AND security file
logger.security("Brute force detected", ip="10.0.0.1", attempts=100)

# INFO goes only to console
logger.info("Request completed")
```

## Async Logger Support

Custom levels work identically with async loggers:

```python
import fapilog

fapilog.register_level("TRACE", priority=5, add_method=True)

async def main():
    logger = await fapilog.get_async_logger()

    await logger.trace("Starting async operation")
    await logger.audit("API key created", key_id="abc123")  # Built-in
    await logger.security("Suspicious request", ip="10.0.0.1")  # Built-in
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

### AUDIT for Compliance (Built-in)

AUDIT is a built-in level (priority 60) - no registration needed:

```python
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

### SECURITY for Threat Detection (Built-in)

SECURITY is the highest built-in level (priority 70):

```python
logger = fapilog.get_logger()

def detect_brute_force(ip: str, failed_attempts: int):
    if failed_attempts > 10:
        logger.security(
            "Brute force attack detected",
            ip=ip,
            attempts=failed_attempts,
            action="blocked"
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
fapilog.register_level("VERBOSE", priority=15)  # RuntimeError: Registry is frozen
```

The registry freezes when the first logger is created. This prevents inconsistent behavior where some loggers have custom levels and others don't.

> **Note:** Built-in levels (DEBUG, INFO, WARNING, ERROR, CRITICAL, AUDIT, SECURITY) are always available and don't need registration.

### Application Startup Pattern

Register all custom levels in your application's entry point:

```python
# app/logging_config.py
import fapilog

def configure_logging():
    """Call once at application startup, before any imports that create loggers."""
    # Only register custom levels - AUDIT and SECURITY are built-in
    fapilog.register_level("TRACE", priority=5, add_method=True)
    fapilog.register_level("VERBOSE", priority=15, add_method=True)
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
