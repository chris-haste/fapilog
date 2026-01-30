# Execution Modes

Fapilog automatically detects your execution context and chooses the optimal mode for background processing. Understanding these modes helps you achieve maximum throughput and avoid common pitfalls.

## Quick Reference

| Mode | How to trigger | Throughput | Best for |
|------|----------------|------------|----------|
| **Async** | Use `AsyncLoggerFacade` | ~100K+ events/sec | FastAPI, aiohttp, async frameworks |
| **Bound loop** | Start `SyncLoggerFacade` inside async context | ~100K+ events/sec | Sync APIs called from async code |
| **Thread** | Start `SyncLoggerFacade` outside async context | ~10-15K events/sec | CLI tools, scripts, traditional frameworks |

## Understanding the Modes

### Async Mode (Fastest)

Use `AsyncLoggerFacade` for native async integration:

```python
from fapilog import get_async_logger

async def main():
    logger = await get_async_logger(preset="fastapi")

    # Each call is a coroutine - no blocking, no threads
    await logger.info("Processing request", user_id=123)
    await logger.error("Something failed", error="details")

    # Drain before shutdown
    await logger.drain()

asyncio.run(main())
```

**Why it's fast:** Log calls are coroutines that interact directly with the async queue. No thread synchronization, no blocking.

**Use when:**
- Building FastAPI, Starlette, or aiohttp applications
- Writing async libraries or frameworks
- Maximum throughput is critical

### Bound Loop Mode

When `SyncLoggerFacade` is started inside an async context, it binds to the current event loop:

```python
from fapilog import get_logger

async def main():
    # Started INSIDE async context = bound loop mode
    logger = get_logger(preset="production")

    # Sync API, but runs on the same event loop
    logger.info("This achieves ~100K events/sec")

    await logger.stop_and_drain()

asyncio.run(main())
```

**Why it's fast:** The logger detects the running event loop and creates worker tasks directly in it. No separate thread, no cross-thread synchronization.

**Use when:**
- You have sync code that runs inside an async application
- You want the familiar sync `logger.info()` API
- You're inside a FastAPI route handler or async middleware

### Thread Mode

When `SyncLoggerFacade` is started outside any async context, it creates a background thread:

```python
from fapilog import get_logger

# Started OUTSIDE async context = thread mode
logger = get_logger(preset="production")

# Each call synchronizes with the worker thread
logger.info("This achieves ~10-15K events/sec")

# Must drain before exit
import asyncio
asyncio.run(logger.stop_and_drain())
```

**Why it's slower:** Each `logger.info()` call must coordinate with the worker thread via `asyncio.run_coroutine_threadsafe()`. This cross-thread synchronization adds ~80-90µs per call.

**Use when:**
- Building CLI tools or scripts
- Using traditional sync frameworks (Flask, Django without async)
- The ~10-15K events/sec throughput is sufficient

## Choosing the Right Mode

### FastAPI Applications

**Recommended: Async mode with `setup_logging()`**

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import get_request_logger, setup_logging

app = FastAPI(lifespan=setup_logging(preset="fastapi"))

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_request_logger)):
    await logger.info("Fetching user", user_id=user_id)
    return {"user_id": user_id}
```

This uses `AsyncLoggerFacade` under the hood for maximum throughput.

### Sync Code in Async Applications

**Recommended: Bound loop mode**

```python
from fapilog import get_logger

async def async_handler():
    # Logger started inside async context
    logger = get_logger(name="handler")

    # Sync API works, full async performance
    process_data(logger)

def process_data(logger):
    # This sync function can use the logger normally
    logger.info("Processing...")
```

### CLI Tools and Scripts

**Use: Thread mode (automatic)**

```python
#!/usr/bin/env python
from fapilog import get_logger
import asyncio

logger = get_logger(preset="production")

def main():
    logger.info("Starting batch job")
    for item in items:
        process(item)
        logger.debug("Processed item", item_id=item.id)
    logger.info("Batch complete")

if __name__ == "__main__":
    main()
    # Ensure logs are flushed before exit
    asyncio.run(logger.stop_and_drain())
```

### Django / Flask (Traditional Sync)

**Use: Thread mode**

```python
# settings.py or app initialization
from fapilog import get_logger

# Started at module level (outside async) = thread mode
logger = get_logger(preset="production")

# In views/handlers
def my_view(request):
    logger.info("Handling request", path=request.path)
    return response
```

For Django with async views, consider initializing the logger inside the async view for bound loop mode.

## Performance Comparison

Measured on typical hardware with a no-op sink:

```
Mode              Throughput        Latency (p50)    Latency (p99)
─────────────────────────────────────────────────────────────────
Async             ~120K events/sec  ~8µs             ~15µs
Bound loop        ~100K events/sec  ~10µs            ~20µs
Thread            ~12K events/sec   ~80µs            ~150µs
```

The ~10x difference in thread mode is due to cross-thread synchronization overhead.

## Common Pitfalls

### Expecting 100K events/sec in Thread Mode

**Problem:** You read "100K events/sec" and use `get_logger()` in a sync script, but only achieve ~10K.

**Solution:** This is expected behavior. For 100K+ throughput, use async mode or ensure you start the logger inside an async context.

### Starting Logger at Module Level in Async Apps

**Problem:**
```python
# top of file - outside async context
logger = get_logger()  # Thread mode!

async def handler():
    logger.info("...")  # ~10K events/sec, not 100K
```

**Solution:**
```python
# Option 1: Initialize inside async context
async def handler():
    logger = get_logger()  # Bound loop mode
    logger.info("...")

# Option 2: Use AsyncLoggerFacade
logger = None

async def startup():
    global logger
    logger = await get_async_logger()
```

### Mixing Modes Unintentionally

**Problem:** Different parts of your app initialize loggers differently, leading to inconsistent performance.

**Solution:** Centralize logger initialization. In FastAPI, use `setup_logging()`. In other frameworks, create a single initialization point.

## Checking Which Mode You're In

```python
logger = get_logger()
logger.start()

if logger._worker_thread is not None:
    print("Thread mode - ~10-15K events/sec")
else:
    print("Bound loop mode - ~100K+ events/sec")
```

## Migration Tips

### From Thread Mode to Bound Loop Mode

If your async application is accidentally using thread mode:

```python
# Before (thread mode - logger created at import time)
from fapilog import get_logger
logger = get_logger()

@app.get("/")
async def root():
    logger.info("hello")

# After (bound loop mode - logger created inside async)
from fapilog import get_logger

@app.on_event("startup")
async def startup():
    global logger
    logger = get_logger()

@app.get("/")
async def root():
    logger.info("hello")  # Now ~100K events/sec
```

### From Sync Logger to Async Logger

For maximum performance in async applications:

```python
# Before
from fapilog import get_logger
logger = get_logger()
logger.info("sync call")

# After
from fapilog import get_async_logger
logger = await get_async_logger()
await logger.info("async call")
```

## See Also

- [Configuration Guide](configuration.md) - Logger configuration options
- [Performance Tuning](performance-tuning.md) - Workers, batch sizes, queue capacity
