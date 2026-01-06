# Filters

Filters run first in the pipeline. They can drop an event (return `None`) or mutate it before enrichers run.

```{toctree}
:maxdepth: 1
:caption: Filter Guides

filters/sampling
filters/rate-limiting
```

## Implementing a filter

```python
from fapilog.plugins import BaseFilter

class MyFilter(BaseFilter):
    name = "my_filter"

    async def filter(self, event: dict) -> dict | None:
        # Return None to drop, or return (possibly modified) event
        if event.get("level") == "DEBUG":
            return None  # drop debug events
        return event
```

## Registering a filter

- Declare an entry point under `fapilog.filters` in `pyproject.toml`.
- Add a `PLUGIN_METADATA` dict with `plugin_type: "filter"` and an API version compatible with `fapilog.plugins.versioning.PLUGIN_API_VERSION`.

## Contract

- `name: str` — **required**
- `async filter(event: dict) -> dict | None` — **required** (return `None` to drop)
- `async start()/stop()` — optional lifecycle hooks
- `async health_check() -> bool` — optional (defaults to healthy when absent)

## Built-in filters

- `level`: drop events below a minimum level.
- `sampling`: probabilistic sampling with optional seed.
- `adaptive_sampling`: adjust sampling to hit a target events-per-second window.
- `trace_sampling`: deterministic sampling keyed by `trace_id`.
- `first_occurrence`: always pass the first occurrence of a unique key, then sample duplicates.
- `rate_limit`: token-bucket rate limiting with optional key partitioning and max bucket guardrails.

## Configuration

Configure filters via `core.filters` and `filter_config.*`. When `core.log_level` is set (and no explicit `core.filters` are provided), fapilog automatically prepends a `level` filter using that threshold.

Execution order is the list order: filters run before enrichers, redactors, processors, and sinks.
