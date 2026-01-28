# Sampling Strategies

Sampling reduces log volume by selectively keeping or dropping log events. Fapilog provides two sampling strategies optimized for different use cases.

## Quick Start (Recommended)

Use the builder API for the simplest setup:

```python
from fapilog import LoggerBuilder

# Probabilistic sampling - keep ~10% of logs
logger = LoggerBuilder().with_sampling(rate=0.1).build()

# Trace-based sampling - consistent per trace
logger = LoggerBuilder().with_trace_sampling(rate=0.1).build()
```

## When to Use Sampling

Sampling is useful when:

- **High-volume services** generate more logs than your storage/budget allows
- **Development/staging** environments don't need every log
- **Cost optimization** for cloud logging services that charge per volume

Sampling is **not recommended** when:

- **Compliance requirements** mandate complete audit trails
- **Debugging production issues** where you need full context
- **Low-volume services** where storage cost is minimal

## Probabilistic Sampling (`SamplingFilter`)

Randomly samples events at a configured rate. Each log event has an independent probability of being kept.

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1)  # Keep ~10% of logs
    .build()
)
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rate` | float | 1.0 | Probability of keeping each event (0.0-1.0) |
| `seed` | int | None | RNG seed for reproducible sampling |

### Characteristics

- **Independent decisions**: Each event is evaluated independently
- **Statistically representative**: Over time, sampled logs reflect the overall distribution
- **Simple and fast**: Minimal overhead per event
- **Non-deterministic**: The same trace may have some events kept and others dropped

### When to Use

- General log volume reduction
- Development/test environments
- When you don't need complete traces

### Seed Behavior and Determinism

When `seed` is provided, sampling becomes reproducible:

```python
# Two loggers with the same seed produce identical sampling decisions
logger1 = LoggerBuilder().with_sampling(rate=0.5, seed=42).build()
logger2 = LoggerBuilder().with_sampling(rate=0.5, seed=42).build()

# Same sequence of keep/drop decisions
```

Each `SamplingFilter` instance maintains its own RNG state. Creating multiple filters with the same seed produces identical sequences independently—they don't interfere with each other.

Without a seed, sampling uses system randomness and is non-reproducible across runs.

## Trace-Based Sampling (`TraceSamplingFilter`)

Samples consistently by trace ID, ensuring all events in a trace are either kept or dropped together.

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_trace_sampling(rate=0.1, trace_id_field="trace_id")
    .build()
)
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `rate` | float | 0.1 | Probability of keeping each trace (0.0-1.0) |
| `trace_id_field` | str | "trace_id" | Field name containing the trace identifier |
| `always_pass_levels` | list | ["ERROR", "CRITICAL"] | Levels that bypass sampling |

### Characteristics

- **Trace-consistent**: All events with the same trace ID get the same decision
- **Deterministic per trace**: Given the same trace ID, the decision is always the same
- **Error preservation**: ERROR and CRITICAL logs are always kept by default
- **Hash-based**: Uses MD5 hash of trace ID for consistent distribution

### When to Use

- Distributed tracing environments
- When you need complete request context
- Debugging scenarios where partial traces are useless

### Always-Pass Levels

By default, ERROR and CRITICAL logs bypass sampling entirely:

```python
# ERROR logs always pass, even if trace is sampled out
logger.error("Database connection failed", trace_id="abc123")

# Customize which levels always pass
logger = (
    LoggerBuilder()
    .with_trace_sampling(
        rate=0.1,
        always_pass_levels=["ERROR", "CRITICAL", "WARNING"]
    )
    .build()
)
```

### Events Without Trace ID

When an event lacks a trace ID, `TraceSamplingFilter` falls back to probabilistic sampling for that event.

## Comparison: Which Strategy to Use?

| Aspect | `SamplingFilter` | `TraceSamplingFilter` |
|--------|------------------|----------------------|
| Decision unit | Per event | Per trace |
| Determinism | Optional (with seed) | Always (by trace ID) |
| Trace completeness | No guarantee | All or nothing |
| Error handling | Sampled like other events | Always kept (configurable) |
| Use case | Volume reduction | Distributed tracing |
| Overhead | Minimal | Hash computation |

## Configuration via Settings

For Settings-based configuration instead of the builder:

```python
from fapilog import Settings
from fapilog.core import CoreSettings
from fapilog.core.filters import FilterConfigSettings, SamplingFilterSettings

settings = Settings(
    core=CoreSettings(filters=["sampling"]),
    filter_config=FilterConfigSettings(
        sampling=SamplingFilterSettings(rate=0.1)
    )
)
```

## Configuration via Environment Variables

```bash
# Enable sampling filter
export FAPILOG_CORE__FILTERS='["sampling"]'

# Set sampling rate
export FAPILOG_FILTER_CONFIG__SAMPLING__RATE=0.1

# For trace-based sampling
export FAPILOG_CORE__FILTERS='["trace_sampling"]'
export FAPILOG_FILTER_CONFIG__TRACE_SAMPLING__RATE=0.1
export FAPILOG_FILTER_CONFIG__TRACE_SAMPLING__TRACE_ID_FIELD="trace_id"
```

## Operational Considerations

### Monitoring Sampled Volume

Enable metrics to track sampling behavior:

```python
logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1)
    .with_metrics(enabled=True)
    .build()
)
```

Monitor `fapilog_events_filtered_total` to verify sampling is working as expected.

### Combining with Other Filters

Sampling filters can be combined with other filters in the pipeline:

```python
logger = (
    LoggerBuilder()
    .with_level("INFO")           # First: drop DEBUG
    .with_sampling(rate=0.5)      # Then: sample remaining
    .build()
)
```

Filter order matters—events are processed sequentially through the filter pipeline.

### Production Recommendations

1. **Start conservative**: Begin with higher sample rates (0.5+) and decrease based on observed volume
2. **Monitor dropped events**: Use metrics to track filter behavior
3. **Keep errors**: Use `TraceSamplingFilter` or configure level-based exceptions
4. **Document your rate**: Team members debugging production need to know sampling is active
5. **Consider per-service rates**: High-traffic services may need lower rates than low-traffic ones

## Deprecated: `observability.logging.sampling_rate`

> **Deprecated since v0.6.0**: The `observability.logging.sampling_rate` setting is deprecated. Use filter-based sampling instead.

The legacy `observability.logging.sampling_rate` setting still works but emits a deprecation warning at runtime. Migrate to filter-based sampling for the recommended approach.

### Migration Guide

**Before (deprecated):**

```python
from fapilog import Settings, get_logger
from fapilog.core.observability import ObservabilitySettings, LoggingSettings

# Deprecated - will emit warning
settings = Settings(
    observability=ObservabilitySettings(
        logging=LoggingSettings(sampling_rate=0.1)
    )
)
logger = get_logger(settings=settings)
```

**After (recommended):**

```python
from fapilog import LoggerBuilder

# Using builder API
logger = LoggerBuilder().with_sampling(rate=0.1).build()
```

Or via Settings:

```python
from fapilog import Settings
from fapilog.core import CoreSettings
from fapilog.core.filters import FilterConfigSettings, SamplingFilterSettings

settings = Settings(
    core=CoreSettings(filters=["sampling"]),
    filter_config=FilterConfigSettings(
        sampling=SamplingFilterSettings(rate=0.1)
    )
)
```

### Behavioral Differences

| Aspect | Legacy (`sampling_rate`) | Filter-based |
|--------|-------------------------|--------------|
| Application point | Inline during log call | In filter pipeline |
| Efficiency | Less efficient | More efficient |
| Level overrides | Not supported | Supported via `TraceSamplingFilter` |
| Configurability | Single rate only | Full filter options |
| Future support | Will be removed | Long-term supported |

### Why Migrate?

- **Performance**: Filter-based sampling is more efficient
- **Flexibility**: Access to trace-based sampling, level overrides, and seeds
- **Consistency**: Unified configuration with other filters
- **Future-proof**: Legacy setting will be removed in a future major version

## Related

- [Reliability Defaults](reliability-defaults.md) - Drop policies and backpressure
- [Performance Tuning](performance-tuning.md) - Optimizing high-throughput logging
- [Configuration](configuration.md) - Builder API reference
