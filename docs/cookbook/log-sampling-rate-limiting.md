# Log sampling and rate limiting for FastAPI

Traffic spikes shouldn't mean log bill spikes. When your service goes from 100 requests/second to 10,000, your observability costs can explode. Sampling and rate limiting help you maintain visibility without drowning in data.

## The Problem

A traffic spike creates a cascade of costs:

```
Normal: 100 req/s × 86,400 sec/day = 8.6M logs/day
Spike:  10,000 req/s × 3,600 sec/hour = 36M logs/hour
```

At $0.50 per GB ingested, a single hour-long spike can cost more than a month of normal traffic. Worse, the flood of data makes it harder to find actual problems.

## Sampling: Log a Percentage

Sampling logs a random percentage of events. Use it when you need statistical visibility without capturing every request.

### Quick Setup (FastAPI Middleware)

The simplest approach uses the middleware's built-in sampling:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

lifespan = setup_logging(
    sample_rate=0.1,  # Log 10% of successful requests
)
app = FastAPI(lifespan=lifespan)
```

This samples at the request level—10% of successful requests are logged. Errors are always logged regardless of sample rate.

### Pipeline-Level Sampling

For more control, configure the sampling filter in the logging pipeline:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1)  # Keep 10% of all log events
    .add_stdout()
    .build()
)
```

Or via Settings:

```python
from fapilog import Settings, get_async_logger

settings = Settings()
settings.core.filters = ["sampling"]
settings.filter_config.sampling = {"sample_rate": 0.1}

logger = await get_async_logger(settings=settings)
```

### When to Use Sampling

| Scenario | Sample Rate | Rationale |
|----------|-------------|-----------|
| High-traffic API | 0.01–0.1 | Statistical debugging, cost control |
| Development | 1.0 | Full visibility |
| Load testing | 0.001 | Prevent log explosion |
| Batch processing | 0.1 | Representative sampling |

### Reproducible Sampling

For testing or debugging, set a seed to get deterministic sampling:

```python
logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1, seed=42)
    .add_stdout()
    .build()
)
```

## Rate Limiting: Cap Volume

Rate limiting uses a token bucket to cap log volume per second. Unlike sampling, it guarantees a maximum throughput regardless of traffic volume.

### Configuration

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_rate_limit(
        capacity=100,      # Bucket holds 100 tokens
        refill_rate=10.0,  # Refills 10 tokens per second
    )
    .add_stdout()
    .build()
)
```

Or via Settings:

```python
from fapilog import Settings, get_async_logger

settings = Settings()
settings.core.filters = ["rate_limit"]
settings.filter_config.rate_limit = {
    "capacity": 100,
    "refill_rate_per_sec": 10.0,
}

logger = await get_async_logger(settings=settings)
```

### How Token Bucket Works

1. Bucket starts with `capacity` tokens (e.g., 100)
2. Each log event consumes 1 token
3. Tokens refill at `refill_rate` per second (e.g., 10/sec)
4. When bucket is empty, logs are dropped until tokens refill

This creates a burst-capable rate limiter:
- **Burst**: Up to 100 logs instantly (full bucket)
- **Sustained**: 10 logs/second maximum

### Per-Key Rate Limiting

Rate limit by a specific field to prevent one noisy source from exhausting the budget:

```python
logger = (
    LoggerBuilder()
    .with_rate_limit(
        capacity=10,
        refill_rate=1.0,
        key_field="user_id",  # Separate bucket per user
    )
    .add_stdout()
    .build()
)
```

Each unique `user_id` gets its own token bucket.

### Overflow Actions

By default, excess logs are dropped. You can mark them instead:

```python
logger = (
    LoggerBuilder()
    .with_rate_limit(
        capacity=100,
        refill_rate=10.0,
        overflow_action="mark",  # Add rate_limited=True instead of dropping
    )
    .add_stdout()
    .build()
)
```

Marked logs can be filtered downstream or counted for alerting.

## Which Should I Use?

| Approach | Use When | Tradeoff |
|----------|----------|----------|
| Sampling | High volume, statistical debugging | Miss individual requests |
| Rate limiting | Spike protection, budget control | Drop excess during spikes |
| Both | Maximum protection | Combined limitations |

### Decision Guide

**Choose sampling when:**
- You need statistical trends, not every event
- Traffic is consistently high
- Cost is the primary concern

**Choose rate limiting when:**
- You need guaranteed throughput caps
- Traffic is spiky/unpredictable
- You want burst capability

**Combine both when:**
- You have both consistent high volume AND spikes
- You need defense in depth

### Combined Configuration

```python
logger = (
    LoggerBuilder()
    .with_sampling(rate=0.5)          # First: keep 50%
    .with_rate_limit(capacity=1000, refill_rate=100.0)  # Then: cap at 100/sec
    .add_stdout()
    .build()
)
```

Filters run in order—sampling first reduces volume, rate limiting caps the result.

## Preserving Important Logs

Neither sampling nor rate limiting should drop critical information. fapilog provides several mechanisms to ensure important logs get through.

### Errors Always Logged (Middleware)

When using `setup_logging()` with `sample_rate`, errors bypass sampling:

```python
lifespan = setup_logging(
    sample_rate=0.1,  # 10% of successful requests
    # Errors (5xx, unhandled exceptions) always logged
)
```

This is automatic—no configuration needed.

### Level-Based Filtering

Use the level filter to ensure ERROR and above always pass:

```python
logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1)  # Sample all levels at 10%
    .add_stdout()
    .build()
)

# For more control, use sink routing to send errors to a separate sink
logger = (
    LoggerBuilder()
    .with_routing(
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["errors"]},
            {"levels": ["INFO", "DEBUG", "WARNING"], "sinks": ["main"]},
        ],
    )
    .add_stdout()
    .build()
)
```

### Adaptive Sampling

For dynamic adjustment based on load, use adaptive sampling:

```python
logger = (
    LoggerBuilder()
    .with_adaptive_sampling(
        min_rate=0.01,           # Never below 1%
        max_rate=1.0,            # Up to 100% when quiet
        target_events_per_sec=1000,  # Target throughput
    )
    .add_stdout()
    .build()
)
```

This automatically reduces sampling during high load while maintaining full visibility during quiet periods.

## Monitoring Your Sampling

Track sampling effectiveness with fapilog metrics:

```python
logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1)
    .with_metrics(enabled=True)
    .add_stdout()
    .build()
)

# Metrics exposed:
# - fapilog_sample_rate: Current effective sample rate
# - fapilog_events_filtered: Events dropped by filters
```

## Environment-Based Configuration

Adjust sampling by environment:

```bash
# Production: aggressive sampling
export FAPILOG_CORE__FILTERS='["sampling", "rate_limit"]'
export FAPILOG_FILTER_CONFIG__SAMPLING__SAMPLE_RATE=0.1
export FAPILOG_FILTER_CONFIG__RATE_LIMIT__CAPACITY=1000
export FAPILOG_FILTER_CONFIG__RATE_LIMIT__REFILL_RATE_PER_SEC=100

# Development: full logging
export FAPILOG_FILTER_CONFIG__SAMPLING__SAMPLE_RATE=1.0
```

## Going Deeper

- [Configuration Guide](../user-guide/configuration.md) - Complete settings reference
- [Performance Tuning](../user-guide/performance-tuning.md) - Optimization strategies
- [Skipping Health Endpoints](skip-noisy-endpoints.md) - Eliminate noise at the source
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
