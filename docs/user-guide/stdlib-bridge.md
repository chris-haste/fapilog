# stdlib Logging Bridge

Capture Python's standard library `logging` output in fapilog's structured pipeline.

## Overview

Many Python libraries use the standard `logging` module. The stdlib bridge lets you:

- Capture third-party library logs in fapilog's structured format
- Migrate gradually from stdlib to fapilog
- Unify all application logs in a single pipeline

## Quick Start

```python
import logging
import fapilog
from fapilog.core.stdlib_bridge import enable_stdlib_bridge

# Get a fapilog logger
logger = fapilog.get_logger(preset="production")

# Enable the bridge - stdlib logs now flow to fapilog
enable_stdlib_bridge(logger)

# Third-party library logs are now captured
logging.getLogger("requests").info("This goes to fapilog")
logging.getLogger("sqlalchemy").warning("This too")
```

## API Reference

### `enable_stdlib_bridge()`

```python
def enable_stdlib_bridge(
    logger: Any,
    *,
    level: int = logging.INFO,
    remove_existing_handlers: bool = False,
    capture_warnings: bool = False,
    logger_namespace_prefix: str = "fapilog",
    target_loggers: Iterable[logging.Logger] | None = None,
    force_sync: bool = False,
    loop_thread_name: str = "fapilog-stdlib-bridge",
    startup_timeout: float = 2.0,
) -> None:
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `logger` | required | fapilog logger instance to forward logs to |
| `level` | `INFO` | Minimum level to capture |
| `remove_existing_handlers` | `False` | Remove existing handlers from target loggers |
| `capture_warnings` | `False` | Also capture `warnings.warn()` output |
| `logger_namespace_prefix` | `"fapilog"` | Prefix for loggers to ignore (loop prevention) |
| `target_loggers` | `None` | Specific loggers to bridge; `None` = root logger |
| `force_sync` | `False` | Force synchronous processing (avoid in async apps) |
| `loop_thread_name` | `"fapilog-stdlib-bridge"` | Background thread name |
| `startup_timeout` | `2.0` | Timeout for background loop startup |

## Common Use Cases

### Capture All stdlib Logs

```python
# Bridge root logger - captures everything
enable_stdlib_bridge(logger, level=logging.DEBUG)
```

### Capture Specific Libraries

```python
import logging

# Only capture requests and sqlalchemy
enable_stdlib_bridge(
    logger,
    target_loggers=[
        logging.getLogger("requests"),
        logging.getLogger("sqlalchemy.engine"),
    ],
)
```

### Capture Python Warnings

```python
import warnings

# Include warnings.warn() output
enable_stdlib_bridge(logger, capture_warnings=True)

warnings.warn("This will appear in fapilog output")
```

### Replace Existing Handlers

```python
# Remove default handlers, use only fapilog
enable_stdlib_bridge(logger, remove_existing_handlers=True)
```

## Framework Integration

### Django

Django uses stdlib logging extensively. To unify with fapilog:

```python
# settings.py or apps.py
import logging
import fapilog
from fapilog.core.stdlib_bridge import enable_stdlib_bridge

# In AppConfig.ready() or similar startup hook
logger = fapilog.get_logger(preset="production")
enable_stdlib_bridge(
    logger,
    target_loggers=[
        logging.getLogger("django"),
        logging.getLogger("django.request"),
        logging.getLogger("django.db.backends"),
    ],
)
```

> **Note:** For complete Django integration, see the Django cookbook (coming soon).

### Celery

Celery workers use stdlib logging for task execution:

```python
# celery.py or tasks.py
import logging
from celery.signals import worker_process_init
import fapilog
from fapilog.core.stdlib_bridge import enable_stdlib_bridge

@worker_process_init.connect
def setup_logging(**kwargs):
    logger = fapilog.get_logger(preset="production")
    enable_stdlib_bridge(
        logger,
        target_loggers=[
            logging.getLogger("celery"),
            logging.getLogger("celery.task"),
        ],
    )
```

## Level Mapping

| stdlib Level | fapilog Method |
|--------------|----------------|
| `CRITICAL` | `critical()` |
| `ERROR` | `error()` |
| `WARNING` | `warning()` |
| `INFO` | `info()` |
| `DEBUG` | `debug()` |

## Preserved Context

The bridge preserves stdlib LogRecord attributes:

```python
# These fields are added to fapilog events:
{
    "stdlib_logger": "requests.packages.urllib3",
    "module": "connectionpool",
    "filename": "connectionpool.py",
    "lineno": 824,
    "funcName": "urlopen",
}
```

## Loop Prevention

The bridge automatically ignores logs from fapilog's internal loggers to prevent infinite loops. By default, any logger starting with `"fapilog"` is ignored.

```python
# Customize the prefix if needed
enable_stdlib_bridge(logger, logger_namespace_prefix="myapp.fapilog")
```

## Performance Considerations

- The bridge runs in a background thread for non-blocking operation
- Async apps should NOT use `force_sync=True`
- High-volume stdlib logging may impact performance; consider raising `level`

## Troubleshooting

### Logs Not Appearing

1. Check the `level` parameter - default is `INFO`, not `DEBUG`
2. Verify the logger name matches `target_loggers`
3. Check if logs are being filtered by fapilog's log level

### Duplicate Logs

If you see duplicate logs:

```python
# Remove existing handlers when enabling bridge
enable_stdlib_bridge(logger, remove_existing_handlers=True)
```

### Import Errors

If `enable_stdlib_bridge` is not found:

```python
# Full import path
from fapilog.core.stdlib_bridge import enable_stdlib_bridge
```
