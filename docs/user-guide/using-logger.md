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

## Tips

- Lead with sync for scripts/CLI; use async in FastAPI/asyncio apps.
- Reuse a logger per request/task; bind context at request start and clear at the end.
