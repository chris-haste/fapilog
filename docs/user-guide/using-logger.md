# Using the Logger

Choose sync or async depending on your app; both share the same semantics.

## Sync logger

```python
from fapilog import get_logger, runtime

logger = get_logger()
logger.info("Hello, world", env="prod")

with runtime() as log:
    log.error("Something happened", code=500)
    # drained automatically on exit
```

## Async logger

```python
from fapilog import get_async_logger, runtime_async

logger = await get_async_logger("service")
await logger.debug("Processing", item=1)
await logger.exception("Oops")  # includes traceback
await logger.drain()

async with runtime_async() as log:
    await log.info("Batch started")
```

## Methods

- `debug/info/warning/error/exception(message, **kwargs)`: emit a log entry; async variants must be awaited.
- `bind(**context)`, `clear_context()`: manage bound context for the current task/thread.
- `stop_and_drain()` / `drain()`: graceful shutdown; use `asyncio.run(logger.stop_and_drain())` for sync loggers if needed outside `runtime()`.

## Logger Caching

By default, `get_logger()` and `get_async_logger()` cache instances by name (like Python's `logging.getLogger()`):

```python
# These return the same instance
logger1 = get_logger("my-service")
logger2 = get_logger("my-service")
assert logger1 is logger2

# Same for async
logger_a = await get_async_logger("my-service")
logger_b = await get_async_logger("my-service")
assert logger_a is logger_b
```

This prevents resource exhaustion from accidentally creating thousands of logger instances.

### Creating Independent Instances

Use `reuse=False` when you need a fresh instance:

```python
# Create a new instance even if one with this name exists
logger = get_logger("test-logger", reuse=False)

# Don't forget to drain when done
await logger.stop_and_drain()
```

### Cache Management

```python
from fapilog import get_cached_loggers, clear_logger_cache

# See what's cached
cached = get_cached_loggers()
# {"my-service": "sync", "other-service": "async"}

# Clear all cached loggers (drains them first)
await clear_logger_cache()
```

## Tips

- Lead with sync for scripts/CLI; use async in FastAPI/asyncio apps.
- Reuse a logger per request/task; bind context at request start and clear at the end.
- Let caching handle instance reuse; avoid storing loggers in global variables.
