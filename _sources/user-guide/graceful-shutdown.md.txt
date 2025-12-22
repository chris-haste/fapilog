# Graceful Shutdown

Ensure buffered logs are flushed before exit.

## Sync

```python
from fapilog import runtime

with runtime() as logger:
    logger.info("work started")
    # ... do work ...
    logger.info("work done")
# stop_and_drain is called internally
```

## Async

```python
from fapilog import runtime_async

async def main():
    async with runtime_async() as logger:
        await logger.info("async work")

# drains on context exit
```

## Manual drain

If you have a sync logger and need to drain explicitly:

```python
import asyncio
from fapilog import get_logger

logger = get_logger()
logger.info("done")
asyncio.run(logger.stop_and_drain())
```

## Settings

- `core.shutdown_timeout_seconds`: max wait when bound to a running loop.
- For threaded worker mode, the logger signals the worker thread to stop and joins with a timeout to avoid hangs.
