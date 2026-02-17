# Execution Modes

Fapilog always runs its logging pipeline on a dedicated background thread. The only work performed on the caller thread is `try_enqueue()` — a fast, non-blocking put onto an async queue. Workers, batch flushers, and sink writes all run on the dedicated thread's event loop.

## Quick Reference

| Facade | API style | Caller-thread cost | Best for |
|--------|-----------|-------------------|----------|
| **`AsyncLoggerFacade`** | `await logger.info()` | `try_enqueue()` | FastAPI, aiohttp, async frameworks |
| **`SyncLoggerFacade`** | `logger.info()` | `try_enqueue()` | CLI tools, scripts, Django, Flask |

## Architecture

```
Caller thread                    Dedicated background thread
─────────────                    ───────────────────────────
logger.info("msg")               event loop
  └─ build_envelope()              ├─ worker tasks (batch + flush)
  └─ try_enqueue() ──queue──►      ├─ sink writes
                                   └─ adaptive actuators
```

Every `logger.info()` call builds the envelope synchronously, then enqueues it. The dedicated thread owns the event loop where workers drain the queue, batch events, and write to sinks. This keeps sink I/O completely off the caller thread.

## AsyncLoggerFacade

Use `AsyncLoggerFacade` for native async integration:

```python
from fapilog import get_async_logger

async def main():
    logger = await get_async_logger(preset="production")

    # Each call is a coroutine - enqueue is non-blocking
    await logger.info("Processing request", user_id=123)
    await logger.error("Something failed", error="details")

    # Drain before shutdown
    await logger.drain()

asyncio.run(main())
```

**Use when:**
- Building FastAPI, Starlette, or aiohttp applications
- Writing async libraries or frameworks

### FastAPI Applications

**Recommended: `FastAPIBuilder`**

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import FastAPIBuilder, get_request_logger

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .build()
)

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_request_logger)):
    await logger.info("Fetching user", user_id=user_id)
    return {"user_id": user_id}
```

This uses `AsyncLoggerFacade` under the hood. Sink I/O runs on the dedicated thread, so it never blocks HTTP handlers.

## SyncLoggerFacade

Use `SyncLoggerFacade` for synchronous code:

```python
from fapilog import get_logger

logger = get_logger(preset="production")

logger.info("Starting batch job")
for item in items:
    process(item)
    logger.debug("Processed item", item_id=item.id)
logger.info("Batch complete")

# Ensure logs are flushed before exit
import asyncio
asyncio.run(logger.stop_and_drain())
```

**Use when:**
- Building CLI tools or scripts
- Using traditional sync frameworks (Flask, Django)

### Django / Flask

```python
# settings.py or app initialization
from fapilog import get_logger

logger = get_logger(preset="production")

# In views/handlers
def my_view(request):
    logger.info("Handling request", path=request.path)
    return response
```

## Performance

Measured on typical hardware with a no-op sink:

```
Facade              Throughput        Latency (p50)    Latency (p99)
─────────────────────────────────────────────────────────────────
AsyncLoggerFacade   ~120K events/sec  ~8us             ~15us
SyncLoggerFacade    ~100K events/sec  ~10us            ~20us
```

Both facades have similar performance because the hot path is the same: `build_envelope()` + `try_enqueue()`. The dedicated thread handles all downstream work.

## Common Pitfalls

### Not Draining Before Exit

**Problem:** Your process exits before the background thread finishes flushing.

**Solution:** Always drain before shutdown:
```python
# Sync
asyncio.run(logger.stop_and_drain())

# Async
await logger.drain()

# FastAPI - handled automatically by FastAPIBuilder lifespan
```

### Mixing Facades Unintentionally

**Problem:** Different parts of your app use different facade types, leading to multiple logger instances.

**Solution:** Centralize logger initialization. In FastAPI, use `FastAPIBuilder`. In other frameworks, create a single initialization point.

## See Also

- [Configuration Guide](configuration.md) - Logger configuration options
- [Performance Tuning](performance-tuning.md) - Workers, batch sizes, queue capacity
