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

Fapilog uses a dedicated background thread for its logging pipeline. The only work on your caller thread is `try_enqueue()` — a non-blocking put that takes microseconds:

```python
from fapilog import get_async_logger, Settings

settings = Settings()
settings.core.drop_on_full = True  # Drop logs if queue is full (default)

logger = await get_async_logger(settings=settings)
```

With the dedicated thread architecture, `log.info()` will:
1. Try to enqueue immediately (non-blocking)
2. If the queue is full, drop the log and return instantly

Your request handler never blocks on logging.

### Tuning Queue Size

The queue acts as a buffer between log emission and sink delivery. Size it to absorb traffic spikes:

```python
settings.core.max_queue_size = 50_000  # Default: 10,000
```

A larger queue absorbs longer bursts but uses more memory. A smaller queue drops sooner under load.

### Audit-Critical Services

For services where every log must be delivered (financial transactions, security events), use a large queue and protected levels:

```python
settings.core.max_queue_size = 100_000  # Large buffer
settings.core.protected_levels = ["ERROR", "CRITICAL", "AUDIT", "SECURITY"]
```

Protected levels use priority eviction — when the queue is full, lower-priority events are evicted to make room for protected ones.

**Default behavior**: fapilog defaults to drop mode (`drop_on_full=True`) with non-blocking enqueue. This protects latency out of the box. Size your queue to match your burst traffic profile.

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
from fapilog.fastapi import FastAPIBuilder, get_request_logger

# Configure for latency-critical API with backpressure
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .with_backpressure(drop_on_full=True, wait_ms=50)  # Max 50ms wait
        .build()
)

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
