# Lifecycle & Results

Runtime management helpers and the `DrainResult` structure returned when stopping loggers.

## DrainResult {#drainresult}

```python
@dataclass
class DrainResult:
    submitted: int
    processed: int
    dropped: int
    retried: int
    queue_depth_high_watermark: int
    flush_latency_seconds: float
```

Returned by `AsyncLoggerFacade.drain()` / `stop_and_drain()` and the sync logger's `stop_and_drain()` (which you can run via `asyncio.run`).

### Example (async)

```python
from fapilog import get_async_logger

logger = await get_async_logger("worker")
await logger.info("shutting down")
result = await logger.drain()
print(f"processed={result.processed} dropped={result.dropped}")
```

### Example (sync)

```python
import asyncio
from fapilog import get_logger

logger = get_logger("cli")
logger.info("done")
result = asyncio.run(logger.stop_and_drain())
print(result.queue_depth_high_watermark)
```

## Context managers

Prefer `runtime()` / `runtime_async()` to manage startup and shutdown automatically:

```python
from fapilog import runtime, runtime_async

with runtime() as logger:
    logger.info("sync work")

async def main():
    async with runtime_async() as logger:
        await logger.info("async work")
```

## Shutdown timeout

`Settings.core.shutdown_timeout_seconds` controls how long the shutdown path will wait for background workers when bound to an event loop. Configure via env var `FAPILOG_CORE__SHUTDOWN_TIMEOUT_SECONDS`.

---

_Use the lifecycle helpers to ensure buffered logs are flushed before your app exits._
