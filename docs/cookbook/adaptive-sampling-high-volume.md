# Adaptive Sampling for High-Volume Services

When your service handles thousands of requests per second, logging everything is expensive and often unnecessary. But during incidents, you need full visibility. The `high-volume` preset solves this with adaptive sampling that automatically adjusts based on traffic.

## The Problem

A flash sale or viral moment creates a cost explosion:

```
Normal:     100 req/s × 86,400 sec = 8.6M logs/day    ($4.30/day)
Flash sale: 10,000 req/s × 3,600 sec = 36M logs/hour  ($18/hour)
```

At $0.50/GB ingested (typical cloud pricing), a 4-hour sale event costs more than a month of normal operation. Worse, the flood makes it harder to find actual problems.

**What you need:**
- Cost-effective logging during normal operation
- Full visibility during incidents
- Errors never dropped, regardless of volume

## The Solution: high-volume Preset

The `high-volume` preset provides intelligent adaptive sampling out of the box:

```python
from fapilog import LoggerBuilder

logger = LoggerBuilder().with_preset("high-volume").build()

# During normal traffic: logs ~100 events/sec
# During spikes: automatically samples down, never below 1%
# Errors: always logged, never sampled out
```

### What the Preset Configures

```python
# Equivalent manual configuration:
logger = (
    LoggerBuilder()
    .with_adaptive_sampling(
        target_events_per_sec=100,  # Target throughput
        min_rate=0.01,              # Never below 1%
        max_rate=1.0,               # Full logging when quiet
        window_seconds=10.0,        # 10-second rolling window
        always_pass_levels=["ERROR", "CRITICAL", "FATAL"],
    )
    .with_workers(2)        # Throughput optimization
    .with_drop_on_full()    # Protect latency under pressure
    .add_stdout_json()
    .build()
)
```

## How Adaptive Sampling Works

Unlike fixed-rate sampling, adaptive sampling responds to actual throughput:

| Traffic | Sample Rate | Events Logged |
|---------|-------------|---------------|
| 50/sec  | 100% | 50/sec (full visibility) |
| 100/sec | 100% | 100/sec (at target) |
| 1,000/sec | 10% | ~100/sec (cost controlled) |
| 10,000/sec | 1% | ~100/sec (minimum rate) |

The algorithm uses exponential smoothing over a 10-second window to avoid thrashing.

## Errors Always Pass Through

The most important feature: **errors are never dropped**. The `always_pass_levels` setting ensures ERROR, CRITICAL, and FATAL messages bypass sampling entirely:

```python
# Even during a 10,000 req/sec spike with 1% sampling:
logger.info("request processed")   # 1% chance of logging
logger.error("database timeout")   # 100% logged, always
logger.critical("service down")    # 100% logged, always
```

This is production-safe because you'll always see:
- Unhandled exceptions
- Database failures
- Service degradations
- Security events logged at ERROR+

## Real-World Example: E-commerce Flash Sale

### Before: Fixed Sampling

```python
# Fixed 10% sampling - problematic
logger = LoggerBuilder().with_sampling(rate=0.1).add_stdout().build()

# Problem 1: During quiet periods, you're missing 90% of data
# Problem 2: During flash sale, you might still be over budget
# Problem 3: No automatic adjustment
```

### After: Adaptive Sampling with high-volume

```python
from fapilog import LoggerBuilder

# Adaptive sampling - responds to actual traffic
logger = LoggerBuilder().with_preset("high-volume").build()

# Quiet period (50 req/s): 100% sampled
# Normal load (500 req/s): ~20% sampled, hitting 100/sec target
# Flash sale (5000 req/s): ~2% sampled, hitting 100/sec target
# All errors: 100% captured regardless of load
```

### Cost Comparison

| Scenario | Fixed 10% | Adaptive (high-volume) |
|----------|-----------|------------------------|
| Quiet (50/sec) | 5/sec | 50/sec (full visibility) |
| Normal (500/sec) | 50/sec | 100/sec |
| Flash sale (5000/sec) | 500/sec | 100/sec |
| **Daily cost*** | ~$10 | ~$5 |

*Estimated at $0.50/GB, 1KB average log size

## Customizing the Preset

Override specific settings while keeping the preset's base configuration:

```python
from fapilog import LoggerBuilder

# Higher target for services that need more visibility
logger = (
    LoggerBuilder()
    .with_preset("high-volume")
    .with_adaptive_sampling(target_events_per_sec=500)  # Override target
    .build()
)

# Lower minimum rate for extremely high-volume services
logger = (
    LoggerBuilder()
    .with_preset("high-volume")
    .with_adaptive_sampling(min_rate=0.001)  # 0.1% minimum
    .build()
)

# Add a cloud sink while keeping preset configuration
logger = (
    LoggerBuilder()
    .with_preset("high-volume")
    .add_cloudwatch(log_group="/app/production")
    .build()
)
```

## When to Use high-volume vs Other Presets

| Preset | Use When |
|--------|----------|
| `high-volume` | Traffic varies widely, cost is a concern, errors must never be missed |
| `production` | Moderate traffic, durability matters more than cost |
| `production-latency` | Low latency critical, willing to drop logs under pressure |
| `serverless` | Lambda/Cloud Functions with short execution time |

### Decision Guide

**Choose `high-volume` when:**
- Your service handles 100+ requests/second regularly
- Traffic is spiky or unpredictable
- Log storage/ingestion costs are a concern
- You need errors to always be captured

**Choose `production` instead when:**
- You need every log for compliance/audit
- Traffic is predictable and moderate
- File-based logging is required

## Monitoring Adaptive Sampling

Track the current sample rate and dropped events:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("high-volume")
    .with_metrics(enabled=True)
    .build()
)

# Exposed metrics:
# - fapilog_adaptive_sample_rate: Current rate (0.0-1.0)
# - fapilog_events_filtered: Events dropped by sampling
# - fapilog_events_always_passed: High-priority events that bypassed sampling
```

## Going Deeper

- [Log Sampling and Rate Limiting](log-sampling-rate-limiting.md) - Fixed-rate sampling and token bucket rate limiting
- [Configuration Guide](../user-guide/configuration.md) - Complete settings reference
- [Performance Tuning](../user-guide/performance-tuning.md) - Optimization strategies
