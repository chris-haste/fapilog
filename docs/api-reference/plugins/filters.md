# Filters

Plugins that drop or transform events before enrichment.

## Contract

Implement `BaseFilter` methods:

- `async filter(self, event: dict) -> dict | None`: required; return event to continue, `None` to drop.
- `async start(self) -> None`: optional initialization.
- `async stop(self) -> None`: optional teardown.

```python
from fapilog.plugins.filters import BaseFilter

class MyFilter:
    name = "my-filter"

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def filter(self, event: dict) -> dict | None:
        if event.get("level") == "DEBUG":
            return None  # Drop DEBUG events
        return event

    async def health_check(self) -> bool:
        return True
```

## Built-in Filters

| Filter | Name | Description |
|--------|------|-------------|
| `LevelFilter` | `level` | Drop events below configured minimum level |
| `SamplingFilter` | `sampling` | Keep a random percentage of events |
| `RateLimitFilter` | `rate_limit` | Token bucket rate limiter (per-key optional) |
| `AdaptiveSamplingFilter` | `adaptive_sampling` | Dynamic sampling based on volume |
| `TraceSamplingFilter` | `trace_sampling` | Sample based on trace/span context |
| `FirstOccurrenceFilter` | `first_occurrence` | Track first occurrence of message patterns |

## Configuration

### Level Filter

Automatically wired when `core.log_level` is set above DEBUG:

```bash
export FAPILOG_CORE__LOG_LEVEL=INFO  # Drops DEBUG events
```

Explicit configuration:

```python
from fapilog import Settings

settings = Settings(
    core__filters=["level"],
    filter_config__level={"config": {"min_level": "WARNING"}},
)
```

### Sampling Filter

Keep a percentage of events randomly:

```python
settings = Settings(
    core__filters=["sampling"],
    filter_config__sampling={"config": {"sample_rate": 0.25}},  # Keep 25%
)
```

Environment variable:

```bash
export FAPILOG_CORE__FILTERS='["sampling"]'
```

### Rate Limit Filter

Token bucket rate limiting:

```python
settings = Settings(
    core__filters=["rate_limit"],
    filter_config__rate_limit={
        "config": {
            "rate": 100,           # tokens per second
            "burst": 200,          # max burst capacity
            "key_field": "user_id" # optional per-key limiting
        }
    },
)
```

### Adaptive Sampling Filter

Dynamically adjusts sample rate based on event volume:

```python
settings = Settings(
    core__filters=["adaptive_sampling"],
    filter_config__adaptive_sampling={
        "config": {
            "target_rate": 100,    # target events/second
            "window_seconds": 60,  # measurement window
        }
    },
)
```

### Trace Sampling Filter

Sample events based on trace context (for distributed tracing integration):

```python
settings = Settings(
    core__filters=["trace_sampling"],
    filter_config__trace_sampling={
        "config": {
            "sample_rate": 0.1,         # base sample rate
            "honor_parent_decision": True,  # respect upstream sampling
        }
    },
)
```

### First Occurrence Filter

Track unique message patterns, optionally limiting repeats:

```python
settings = Settings(
    core__filters=["first_occurrence"],
    filter_config__first_occurrence={
        "config": {
            "max_occurrences": 1,      # only log first occurrence
            "window_seconds": 300,     # reset tracking after 5 minutes
        }
    },
)
```

## Filter Order

Filters run in the order specified in `core.filters`. Earlier filters can drop events before later filters see them:

```python
settings = Settings(
    core__filters=["level", "rate_limit", "sampling"],
)
```

In this example:
1. `level` drops events below threshold
2. `rate_limit` applies token bucket to remaining events
3. `sampling` randomly samples what's left

## Metrics

When `core.enable_metrics=True`, filter metrics are recorded:

- Events filtered (dropped) count
- Sample rate (for sampling filters)
- Rate limit keys tracked (for per-key rate limiting)

Filters run after the log call but before enrichment, redaction, and sinks.
