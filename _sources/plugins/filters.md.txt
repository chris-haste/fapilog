# Filters

Filters run first in the pipeline. They can drop an event (return `None`) or mutate it before enrichers run.

## Contract

- `name: str`
- `async start()/stop()` optional lifecycle hooks
- `async filter(event: dict) -> dict | None` (return `None` to drop)
- `async health_check() -> bool` (optional)

## Built-in filters

- `level`: drop events below a minimum level.
- `sampling`: probabilistic sampling with optional seed.
- `rate_limit`: token-bucket rate limiting with optional key partitioning.

## Configuration

Configure filters via `core.filters` and `filter_config.*`. When `core.log_level` is set (and no explicit `core.filters` are provided), fapilog automatically prepends a `level` filter using that threshold.

Execution order is the list order: filters run before enrichers, redactors, processors, and sinks.
