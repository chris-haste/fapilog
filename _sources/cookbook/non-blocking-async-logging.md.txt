# Non-blocking logging in FastAPI (protect latency under slow sinks)

Slow log sinks can stall your async application. When a network hiccup delays CloudWatch or your disk fills up, synchronous logging blocks the event loop, affecting every concurrent request. fapilog's async pipeline with configurable backpressure lets you choose: drop logs to protect latency, or block to guarantee delivery.

> **Note:** Whether you use `get_logger()` in sync code or `get_async_logger()` in async code, your log calls never block on I/O. The non-blocking benefits described here apply to both APIs.

## The Problem: Slow Sinks Block Your App

In a traditional logging setup, each log call writes directly to the destination:

```
Request → log.info("...") → [WAIT for network/disk] → Continue processing
```

When the sink is fast, this works fine. But sinks can slow down:

- **Network latency**: CloudWatch API taking 500ms instead of 50ms
- **Disk I/O**: Log rotation or full disk causing writes to stall
- **External services**: Loki or Elasticsearch under heavy load

In an async framework like FastAPI, a blocking log call doesn't just slow one request—it blocks the entire event loop:

```
Request A → log.info() → [BLOCKED 500ms waiting for CloudWatch]
Request B → waiting...
Request C → waiting...
Request D → waiting...
```

A single slow log sink can turn your 10ms API into a 500ms+ API.

## The Solution: Async Pipeline with Backpressure

fapilog decouples log emission from sink delivery:

```
Request → log.info() → [Queue] → Worker → Sink
              ↓
         Returns immediately
```

Log calls return immediately after enqueueing. A background worker handles delivery, isolating your request handlers from sink latency.

But what happens when logs arrive faster than the sink can process them? The queue fills up. fapilog provides two backpressure modes to handle this:

| Mode | Behavior | Use When |
|------|----------|----------|
| **Drop** (default) | Wait briefly, then drop the log | Latency is critical |
| **Block** | Wait indefinitely for queue space | Every log must be delivered |

## Configuring Backpressure

### Drop Mode (Latency-Critical Services)

For APIs where response time matters more than log completeness:

```python
from fapilog import get_async_logger, Settings

settings = Settings()
settings.core.drop_on_full = True  # Drop logs if queue is full (default)
settings.core.backpressure_wait_ms = 100  # Wait up to 100ms before dropping

logger = await get_async_logger(settings=settings)
```

With these settings, `log.info()` will:
1. Try to enqueue immediately
2. If the queue is full, wait up to 100ms for space
3. If still full after 100ms, drop the log and return

Your request handler never blocks for more than 100ms on logging.

### Block Mode (Audit-Critical Services)

For services where every log must be delivered (financial transactions, security events):

```python
from fapilog import get_async_logger, Settings

settings = Settings()
settings.core.drop_on_full = False  # Never drop, wait indefinitely

logger = await get_async_logger(settings=settings)
```

With `drop_on_full=False`, log calls will wait as long as needed for queue space. This guarantees delivery but may add latency during sink slowdowns.

### Tuning Queue Size

The queue acts as a buffer between log emission and sink delivery:

```python
settings.core.max_queue_size = 50_000  # Default: 10,000
```

A larger queue absorbs longer bursts but uses more memory. A smaller queue triggers backpressure sooner.

## Choosing the Right Mode

| Scenario | Recommended Mode | Why |
|----------|------------------|-----|
| User-facing API | Drop | Users won't wait for logs |
| Background jobs | Block | No user waiting, logs are valuable |
| Financial transactions | Block | Audit trail must be complete |
| High-throughput metrics | Drop | Volume matters more than completeness |
| Debug logging in production | Drop | Debug logs are nice-to-have |
| Security event logging | Block | Security logs are critical |

**Default behavior**: fapilog defaults to drop mode (`drop_on_full=True`) with a 50ms wait (`backpressure_wait_ms=50`). This protects latency out of the box while giving sinks a brief chance to catch up.

## Monitoring Backpressure

fapilog exposes metrics to track queue health in production:

### Queue Depth

The `queue_depth_high_watermark` in logger stats shows the maximum queue depth reached:

```python
stats = await logger.get_stats()
print(f"Queue high watermark: {stats.queue_depth_high_watermark}")
```

If this approaches `max_queue_size`, you're hitting backpressure regularly.

### Dropped Events

When using Prometheus metrics (`enable_metrics=True`), fapilog exports:

```
fapilog_events_dropped_total
```

A rising counter indicates logs are being dropped due to backpressure. This is expected in drop mode during sink slowdowns, but sustained drops may indicate:

- Queue size too small for your throughput
- Sink consistently slower than log emission rate
- Need to scale sink capacity or reduce log volume

## Example: FastAPI with Protected Latency

```python
from fastapi import FastAPI, Depends
from fapilog import Settings
from fapilog.fastapi import setup_logging, get_request_logger

# Configure for latency-critical API
settings = Settings()
settings.core.drop_on_full = True
settings.core.backpressure_wait_ms = 50  # Max 50ms wait

lifespan = setup_logging(preset="fastapi", settings=settings)
app = FastAPI(lifespan=lifespan)

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, logger=Depends(get_request_logger)):
    # This log call returns in <50ms even if CloudWatch is slow
    await logger.info("Fetching order", order_id=order_id)
    return {"order_id": order_id}
```

## Going Deeper

- [FastAPI JSON Logging](fastapi-json-logging.md) - Structured logging setup
- [FastAPI request_id Logging](fastapi-request-id-logging.md) - Correlation IDs
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
