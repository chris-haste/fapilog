# Why Fapilog?

Fapilog is an **async-first structured logging library** for Python services. If you're building FastAPI applications, microservices, or any system where logging shouldn't slow down your requests, fapilog was designed for your use case.

## Quick Decision Guide

| If you need... | Best choice |
|----------------|-------------|
| Async-first logging with backpressure handling | **fapilog** |
| Simplest possible API, sync is fine | loguru |
| Processor ecosystem, stdlib compatibility | structlog |
| Full observability (logs + traces + metrics) | OpenTelemetry |
| Zero dependencies | stdlib logging |

**Not sure?** Read on for details, or jump to the [full comparison](comparisons.md).

## Is Fapilog Right for Your Project?

Use fapilog if you're building:

- **Microservices and distributed systems** - Request ID tracking, async-first, multiple cloud sinks
- **FastAPI/async applications** - Built-in middleware, non-blocking logging
- **High-throughput services** - Backpressure handling, won't impact request latency
- **Production services at scale** - Reliability features (circuit breaker, sink routing, batching)
- **Applications with compliance needs** - Built-in PII redaction (field/regex/URL)
- **Cloud-native applications** - Native CloudWatch, Loki, PostgreSQL sinks
- **Services with variable load patterns** - Backpressure policies handle bursts gracefully

## What Makes Fapilog Different

### 1. True Async-First Architecture

Most Python logging libraries are synchronous—they block your application while writing to disk or network. **With fapilog, your log calls never block on I/O.** Whether you use `get_logger()` in sync code or `get_async_logger()` in async code, the actual writes happen in background workers. A slow CloudWatch API or full disk won't stall your request handlers.

```
Your code          Background worker
    │                     │
log.info("msg") ──queue──→ │
    │ (returns)           ↓
    │               serialize → enrich → write to sink
    ↓
(continues)
```

The difference between the two APIs is the calling convention, not the architecture:

```python
# Sync API - for sync code or when you don't want to await
from fapilog import get_logger
logger = get_logger()
logger.info("Request processed")  # Enqueues and returns

# Async API - for async code with tighter event loop integration
from fapilog import get_async_logger
logger = await get_async_logger()
await logger.info("Request processed")  # Enqueues and returns
```

**In async contexts**, both are non-blocking. **In sync contexts**, `get_logger()` may briefly wait (up to 50ms by default) for queue space before returning—still far faster than blocking on network I/O.

### 2. Backpressure Handling

What happens when logs arrive faster than they can be written? Most libraries either block (hurting latency) or silently drop logs (hurting reliability). Fapilog lets you configure the tradeoff:

```python
from fapilog import LoggerBuilder

# Protect latency: wait briefly, then drop if still full
logger = (
    LoggerBuilder()
    .with_backpressure(wait_ms=50, drop_on_full=True)
    .build()
)

# Protect durability: never lose logs (may block longer)
logger = (
    LoggerBuilder()
    .with_backpressure(wait_ms=0, drop_on_full=False)
    .build()
)
```

| Configuration | Behavior |
|--------------|----------|
| `wait_ms=50, drop_on_full=True` | Wait up to 50ms for space, then drop (default) |
| `wait_ms=0, drop_on_full=True` | Drop immediately if queue full |
| `wait_ms=0, drop_on_full=False` | Block indefinitely until space available |
| `wait_ms=100, drop_on_full=False` | Wait 100ms, then block indefinitely |

### 3. Built-in Redaction

PII and secrets are masked by default with the production preset. No compliance surprises.

```python
from fapilog import get_logger

logger = get_logger(preset="production")
logger.info("User login", password="secret123", email="user@example.com")
# Output: password=**REDACTED**, email=**REDACTED**
```

### 4. FastAPI Integration

One line gets you request logging, correlation IDs, and context propagation:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

app = FastAPI(lifespan=setup_logging(preset="production"))
```

### 5. Level-Based Sink Routing

Send errors to a database for alerting while info logs go to stdout:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_routing(
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["postgres"]},
            {"levels": ["DEBUG", "INFO", "WARNING"], "sinks": ["stdout"]},
        ]
    )
    .build()
)
```

## Honest Trade-offs

| Consideration | Reality |
|---------------|---------|
| **Maturity** | New (2024) vs structlog (2013), loguru (2018) |
| **Community** | Growing vs established ecosystems with more tutorials and Stack Overflow answers |
| **Sync use cases** | If you don't need async, loguru is simpler |
| **Processor ecosystem** | structlog has more built-in processors and community extensions |

### When fapilog might not be the best fit

- **Simple scripts or CLIs**: If you're writing to fast local stdout with minimal structure, stdlib or loguru is simpler.
- **Existing structlog codebases**: Migration effort may not be worth it unless you're hitting blocking I/O issues.
- **Need full observability**: If you want unified logs + traces + metrics, OpenTelemetry is the industry standard.

## Learn More

- **[Full Feature Comparison](comparisons.md)** - Detailed comparison with structlog, loguru, stdlib, and OpenTelemetry
- **[Getting Started](getting-started/index.md)** - Install and start logging in 2 minutes
- **[Architecture](core-concepts/pipeline-architecture.md)** - How the async pipeline works
- **[Cookbook](cookbook/index.md)** - Copy-paste solutions for common problems
