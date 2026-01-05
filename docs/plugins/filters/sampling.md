# Sampling Filters

Plugin-based sampling replaces the legacy `observability.logging.sampling_rate` knob with explicit, composable filters. Sampling now plugs into the filter stage, so you can combine probabilistic, adaptive, and trace-aware strategies without touching core logger code.

## Quick start

```python
from fapilog import Settings, get_logger

settings = Settings()
settings.core.filters = ["sampling"]
settings.filter_config.sampling = {"config": {"sample_rate": 0.2}}

logger = get_logger(settings=settings)
logger.debug("kept with 20% probability")
```

### Adaptive sampling (`adaptive_sampling`)

Target a steady events-per-second rate and let the filter adjust up or down inside configured bounds.

```yaml
core:
  filters: ["adaptive_sampling"]
filter_config:
  adaptive_sampling:
    config:
      target_eps: 100        # desired events/sec
      min_sample_rate: 0.01  # never drop more than 99%
      max_sample_rate: 1.0   # never oversample
      window_seconds: 10
      smoothing_factor: 0.3  # how quickly to react
      always_pass_levels: ["ERROR", "CRITICAL"]
```

### Trace-aware sampling (`trace_sampling`)

Deterministically include or drop entire traces based on `trace_id`, with a random fallback when no trace context is present.

```yaml
core:
  filters: ["trace_sampling"]
filter_config:
  trace_sampling:
    config:
      sample_rate: 0.15
      trace_id_field: trace_id
      always_pass_levels: ["ERROR", "CRITICAL"]
```

### First-occurrence sampling (`first_occurrence`)

Ensure the first occurrence of a message (or custom key) always lands, then sample subsequent duplicates.

```yaml
core:
  filters: ["first_occurrence"]
filter_config:
  first_occurrence:
    config:
      key_fields: ["message"]    # fields that define uniqueness
      window_seconds: 60         # eviction window
      max_keys: 10000            # bounded memory (LRU)
      subsequent_sample_rate: 0  # drop later duplicates; >0 to sample
```

## Metrics

- `fapilog_filter_sample_rate` (gauge, labeled by `filter`) tracks the current sampling rate reported by sampling filters.
- Sampling filters run before enrichers and redactors; drops increment `fapilog_events_filtered_total`.

## Migration from legacy sampling

The legacy `observability.logging.sampling_rate` setting is deprecated and now emits a `DeprecationWarning` when used. Move to filter-based sampling to avoid double-sampling and gain observability.

**Before (deprecated):**

```yaml
observability:
  logging:
    sampling_rate: 0.25
```

**After (recommended):**

```yaml
core:
  filters: ["sampling"]
filter_config:
  sampling:
    config:
      sample_rate: 0.25
```

If you need adaptive behavior, swap the filter name and config:

```yaml
core:
  filters: ["adaptive_sampling"]
filter_config:
  adaptive_sampling:
    config:
      target_eps: 100
      min_sample_rate: 0.01
      max_sample_rate: 1.0
```
