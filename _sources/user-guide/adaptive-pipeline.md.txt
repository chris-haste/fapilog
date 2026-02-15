# Adaptive Pipeline

The adaptive pipeline automatically scales workers, batch sizes, and queue capacity based on real-time queue pressure. Instead of manually tuning these parameters for peak load, the pipeline self-adjusts as traffic changes.

## Quick start

```python
from fapilog import get_logger

# One-line setup
logger = get_logger(preset="adaptive")
```

Or with the builder:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_adaptive(enabled=True)
    .with_circuit_breaker(enabled=True, fallback_sink="rotating_file")
    .build()
)
```

## How it works

The adaptive pipeline has three components:

1. **Pressure Monitor** — Samples queue fill ratio at regular intervals (default: every 0.25s)
2. **Escalation State Machine** — Computes the current pressure level based on fill ratio thresholds with hysteresis
3. **Actuators** — Respond to pressure level changes by adjusting pipeline parameters

### Pressure levels

| Level | Fill Ratio | Meaning |
|-------|-----------|---------|
| NORMAL | < 60% | Pipeline is healthy, no adjustments |
| ELEVATED | >= 60% | Queue filling up, begin scaling |
| HIGH | >= 80% | Significant pressure, aggressive scaling |
| CRITICAL | >= 92% | Near capacity, maximum response |

### Hysteresis

To prevent oscillation between levels, de-escalation thresholds are lower than escalation thresholds:

| Transition | Escalate At | De-escalate At |
|------------|------------|---------------|
| NORMAL / ELEVATED | 60% | 40% |
| ELEVATED / HIGH | 80% | 60% |
| HIGH / CRITICAL | 92% | 75% |

This means the queue must drop well below the escalation threshold before the pipeline scales back down.

### Actuators

| Actuator | What It Does | NORMAL | ELEVATED | HIGH | CRITICAL |
|----------|-------------|--------|----------|------|----------|
| Worker scaling | Adds worker tasks | Initial (2) | +1 | +2 | Max (8) |
| Batch sizing | Adjusts batch sizes (opt-in) | Base (100) | 1.5x | 2x | 4x |
| Queue growth | Expands queue capacity | Base | 1.5x | 2x | Up to 4x |
| Filter tightening | Raises effective log level | None | Soft | Medium | Aggressive |

## Configuration reference

All settings live under the `adaptive` key:

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `false` | Enable adaptive pipeline controller |
| `check_interval_seconds` | `0.25` | Seconds between queue pressure samples |
| `cooldown_seconds` | `2.0` | Minimum seconds between pressure level transitions |
| `escalate_to_elevated` | `0.60` | Fill ratio to escalate NORMAL to ELEVATED |
| `escalate_to_high` | `0.80` | Fill ratio to escalate ELEVATED to HIGH |
| `escalate_to_critical` | `0.92` | Fill ratio to escalate HIGH to CRITICAL |
| `deescalate_from_elevated` | `0.40` | Fill ratio to de-escalate ELEVATED to NORMAL |
| `deescalate_from_high` | `0.60` | Fill ratio to de-escalate HIGH to ELEVATED |
| `deescalate_from_critical` | `0.75` | Fill ratio to de-escalate CRITICAL to HIGH |
| `max_workers` | `8` | Maximum workers when dynamic scaling is active |
| `max_queue_growth` | `4.0` | Maximum queue capacity multiplier |
| `batch_sizing` | `false` | Enable adaptive batch sizing |
| `circuit_pressure_boost` | `0.20` | Pressure boost per open circuit breaker |
| `filter_tightening` | `true` | Enable adaptive filter tightening based on pressure level |
| `worker_scaling` | `true` | Enable dynamic worker scaling based on pressure level |
| `queue_growth` | `true` | Enable queue capacity growth based on pressure level |

### Environment variables

```bash
FAPILOG_ADAPTIVE__ENABLED=true
FAPILOG_ADAPTIVE__CHECK_INTERVAL_SECONDS=0.25
FAPILOG_ADAPTIVE__COOLDOWN_SECONDS=2.0
FAPILOG_ADAPTIVE__ESCALATE_TO_ELEVATED=0.60
FAPILOG_ADAPTIVE__ESCALATE_TO_HIGH=0.80
FAPILOG_ADAPTIVE__ESCALATE_TO_CRITICAL=0.92
FAPILOG_ADAPTIVE__MAX_WORKERS=8
FAPILOG_ADAPTIVE__MAX_QUEUE_GROWTH=4.0
FAPILOG_ADAPTIVE__BATCH_SIZING=true
FAPILOG_ADAPTIVE__CIRCUIT_PRESSURE_BOOST=0.20
FAPILOG_ADAPTIVE__FILTER_TIGHTENING=true
FAPILOG_ADAPTIVE__WORKER_SCALING=false
FAPILOG_ADAPTIVE__QUEUE_GROWTH=false
```

### Settings-based configuration

```python
from fapilog import Settings

settings = Settings(adaptive={
    "enabled": True,
    "max_workers": 6,
    "max_queue_growth": 2.0,
    "batch_sizing": True,
    "check_interval_seconds": 0.5,
    "cooldown_seconds": 3.0,
})
```

## Adaptive batch sizing

Adaptive batch sizing (`batch_sizing=True`) dynamically adjusts the worker drain batch size based on measured sink latency. It uses a proportional controller with EWMA smoothing — fast sinks get larger batches, slow sinks get smaller batches.

**This is disabled by default** because it operates globally across all sinks and only benefits sinks that accept batched writes.

### When to enable batch sizing

Enable `batch_sizing=True` when your pipeline includes **batch-aware sinks** that benefit from larger payloads:

- **CloudWatch Logs** — PutLogEvents accepts up to 10,000 events per call
- **Grafana Loki** — Push API accepts multiple log streams per request
- **PostgreSQL** — Bulk INSERT is significantly faster than individual rows
- **HTTP sinks** — Remote endpoints that accept batched payloads

### When to leave it disabled

Leave `batch_sizing=False` (the default) when you only use sinks that process events individually:

- **stdout** — Writes one JSON line per event
- **Rotating file** — Writes one line per event

For these sinks, growing the batch size just increases the time events sit in the worker buffer before being written, adding latency with no throughput benefit.

### Enabling batch sizing

```python
# Builder API
logger = (
    LoggerBuilder()
    .with_preset("adaptive")
    .with_adaptive(batch_sizing=True)
    .add_cloudwatch("/myapp/prod")
    .build()
)
```

```bash
# Environment variable
FAPILOG_ADAPTIVE__BATCH_SIZING=true
```

> **Note:** Adaptive batch sizing controls the worker-level drain batch size, not individual sink batch sizes. Cloud sinks have their own `batch_size` parameters (e.g., `add_cloudwatch(batch_size=200)`) that are configured independently.

## Threshold validation

Escalation thresholds must be strictly ascending, and each de-escalation threshold must be strictly below its corresponding escalation threshold:

```
escalate_to_elevated < escalate_to_high < escalate_to_critical
deescalate_from_elevated < escalate_to_elevated
deescalate_from_high < escalate_to_high
deescalate_from_critical < escalate_to_critical
```

Invalid threshold ordering raises a `ValidationError` at configuration time.

## Circuit breaker integration

When a sink's circuit breaker is open, the adaptive pipeline treats it as additional pressure. The `circuit_pressure_boost` setting (default: 0.20) is added to the effective fill ratio for each open circuit:

```
effective_fill_ratio = actual_fill_ratio + (open_circuits * circuit_pressure_boost)
```

This ensures the pipeline responds proactively when sinks are failing, even if the queue isn't physically full yet.

## Tuning guidelines

**For latency-sensitive services:**
```python
builder.with_adaptive(
    max_workers=4,          # Cap worker scaling
    max_queue_growth=1.5,   # Limit queue growth
    check_interval_seconds=0.1,  # Faster response
)
```

**For high-throughput batch processing:**
```python
builder.with_adaptive(
    max_workers=8,
    max_queue_growth=4.0,
    batch_sizing=True,
    cooldown_seconds=5.0,   # Slower transitions to avoid oscillation
)
```

**Conservative escalation (fewer false alarms):**
```python
Settings(adaptive={
    "enabled": True,
    "escalate_to_elevated": 0.70,
    "escalate_to_high": 0.85,
    "escalate_to_critical": 0.95,
    "cooldown_seconds": 5.0,
})
```

## Inspecting adaptive behavior

After draining, `DrainResult.adaptive` contains a summary of what the adaptive system did during the logger's lifetime. This is useful for monitoring, alerting, and tuning your configuration.

```python
result = await logger.drain()

if result.adaptive is not None:
    summary = result.adaptive
    print(f"Peak pressure: {summary.peak_pressure_level.value}")
    print(f"Escalations: {summary.escalation_count}")
    print(f"De-escalations: {summary.deescalation_count}")
    print(f"Filters swapped: {summary.filters_swapped}")
    print(f"Workers scaled: {summary.workers_scaled} (peak: {summary.peak_workers})")
    print(f"Batch resizes: {summary.batch_resize_count}")
    print(f"Queue growths: {summary.queue_growth_count} (peak: {summary.peak_queue_capacity})")

    # Time breakdown by pressure level
    for level, seconds in summary.time_at_level.items():
        print(f"  {level.value}: {seconds:.1f}s")
```

When the adaptive pipeline is not enabled, `result.adaptive` is `None` and existing `DrainResult` fields are unchanged.

See [Lifecycle & Results](../api-reference/lifecycle-results.md) for the full field reference.

## The adaptive preset

The `adaptive` preset (`get_logger(preset="adaptive")`) enables all adaptive features with sensible defaults:

- Production base settings (2 workers, batch size 100)
- Adaptive pipeline enabled (worker scaling, queue growth)
- Adaptive batch sizing disabled by default (enable with `with_adaptive(batch_sizing=True)` when using batch-aware sinks)
- Circuit breaker with rotating file fallback
- Protected levels: ERROR, CRITICAL, FATAL, AUDIT, SECURITY
- Credential redaction enabled

See [Presets](presets.md) for a comparison of all available presets.

## Related

- [Performance Tuning](performance-tuning.md) — Manual tuning options
- [Circuit Breaker](circuit-breaker.md) — Sink fault isolation and fallback routing
- [Presets](presets.md) — Preset comparison and selection guide
- [Builder API](../api-reference/builder.md) — `with_adaptive()` method reference
