# Graceful shutdown & flushing logs (don't lose logs on deploy)

Your last log before a crash might be the most important one. When a container is killed during deployment, buffered logs can be lost forever—taking critical debugging information with them.

## The Problem: Lost Logs on Shutdown

Async loggers buffer events for performance. When Kubernetes sends SIGTERM, your app has limited time to flush before SIGKILL arrives:

```
App receives SIGTERM
├── Pending logs in queue: 47 events
├── Kubernetes grace period: 30 seconds
├── Time to flush: ~100ms
└── Result: Logs written ✓

vs.

App receives SIGKILL (no grace period)
├── Pending logs in queue: 47 events
├── Time to flush: 0ms
└── Result: Logs lost ✗
```

Common scenarios where logs get lost:

- **Deployment rollouts** - Container replaced before buffer drains
- **Pod evictions** - Memory pressure triggers immediate termination
- **Crash loops** - App exits before async flush completes
- **Scale-down** - Replicas removed during queue drain

The debugging pain is real: "I know there was an error log right before the crash, but I can't find it."

## The Solution: Lifespan Integration

With fapilog's FastAPI integration, logs are automatically flushed on graceful shutdown:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

lifespan = setup_logging()  # Automatic flush on shutdown
app = FastAPI(lifespan=lifespan)
```

When your app receives SIGTERM, the lifespan ensures:

1. No new requests are accepted
2. In-flight requests complete
3. Log buffer is flushed
4. Logger workers are stopped

This is the recommended approach for FastAPI applications.

## Manual Flush for Custom Scenarios

For non-FastAPI apps or custom shutdown handlers, use `drain()` directly:

```python
from fapilog import get_async_logger

logger = await get_async_logger()

async def shutdown():
    """Custom shutdown handler."""
    result = await logger.drain()
    print(f"Flushed {result.processed} logs")
```

The `drain()` method:

- Flushes all queued events
- Stops background workers
- Returns statistics about what was processed

### DrainResult Statistics

```python
result = await logger.drain()

print(f"Submitted: {result.submitted}")      # Total events submitted
print(f"Processed: {result.processed}")      # Events successfully written
print(f"Dropped: {result.dropped}")          # Events dropped (backpressure)
print(f"Latency: {result.flush_latency_seconds:.3f}s")  # Time to flush
```

Use these stats to monitor shutdown health in your observability stack.

## Timeout Handling

### Default Behavior

The FastAPI lifespan uses a 5-second drain timeout. If flushing takes longer, a warning is emitted but the app continues shutdown:

```
[WARN] fapilog: logger drain timeout (timeout=5.0)
```

### Configuring Timeout

For the manual approach with explicit timeout:

```python
import asyncio
from fapilog import get_async_logger

logger = await get_async_logger()

async def shutdown():
    try:
        await asyncio.wait_for(logger.drain(), timeout=10.0)
    except asyncio.TimeoutError:
        print("Drain timed out - some logs may be lost")
```

### Builder Configuration

Configure the default shutdown timeout via the builder:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_shutdown_timeout("5s")  # Maximum time to flush on shutdown
    .add_stdout()
    .build()
)
```

Or via environment variable:

```bash
export FAPILOG_CORE__SHUTDOWN_TIMEOUT_SECONDS=5.0
```

### What Happens When Timeout Exceeds

When drain times out:

1. A diagnostic warning is emitted
2. Remaining queued logs are abandoned
3. Shutdown continues

This is a tradeoff: waiting indefinitely would hang shutdown, but timing out loses logs. Choose a timeout that matches your Kubernetes `terminationGracePeriodSeconds` minus time for other shutdown tasks.

## Best Practices

### Match Kubernetes Grace Period

```yaml
# kubernetes deployment
spec:
  terminationGracePeriodSeconds: 30  # Total shutdown time
```

```python
# app.py - leave headroom for other shutdown tasks
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_shutdown_timeout("20s")  # 20s for logs, 10s buffer
    .add_stdout()
    .build()
)
```

### Handle Crash Scenarios

For truly critical logs, consider sync sinks for ERROR level:

```python
logger = (
    LoggerBuilder()
    .with_routing(
        rules=[
            # Errors go to sync sink (immediate write)
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["stderr"]},
            # Other levels go to async sink (buffered)
            {"levels": ["DEBUG", "INFO", "WARNING"], "sinks": ["stdout"]},
        ],
    )
    .add_stdout()
    .add_stderr()
    .build()
)
```

### Monitor Drain Statistics

Export drain metrics on shutdown:

```python
async def shutdown():
    result = await logger.drain()
    # Send to metrics before app exits
    metrics.record_gauge("log_drain_latency", result.flush_latency_seconds)
    metrics.record_gauge("log_drain_dropped", result.dropped)
```

## Going Deeper

- [Non-blocking Async Logging](non-blocking-async-logging.md) - Backpressure and queue configuration
- [Log Sampling and Rate Limiting](log-sampling-rate-limiting.md) - Control volume before it hits the queue
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
