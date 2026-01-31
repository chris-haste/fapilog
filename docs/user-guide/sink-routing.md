# Sink routing by level

Route different log levels to different sinks for cost control, compliance, and targeted alerting.

## Quick start (settings)

```bash
export FAPILOG_SINK_ROUTING__ENABLED=true
export FAPILOG_SINK_ROUTING__RULES='[
  {"levels": ["ERROR", "CRITICAL"], "sinks": ["postgres"]},
  {"levels": ["DEBUG", "INFO", "WARNING"], "sinks": ["stdout_json"]}
]'
export FAPILOG_SINK_ROUTING__FALLBACK_SINKS='["rotating_file"]'
```

```python
from fapilog import runtime

with runtime() as log:
    log.error("Stored in postgres")
    log.info("Goes to stdout")
```

## Configuration schema

- `enabled`: turn routing on (defaults to fanout when false)
- `rules`: list of `{levels: [...], sinks: [...]}`; levels are case-insensitive
- `overlap`: when true, multiple rules can apply; when false, first match wins
- `fallback_sinks`: used when no rule matches (empty drops unmatched events)

### YAML configuration

If loading settings from a YAML file:

```yaml
sink_routing:
  enabled: true
  overlap: true
  rules:
    - levels: [ERROR, CRITICAL]
      sinks: [postgres, webhook]
    - levels: [INFO, WARNING]
      sinks: [stdout_json]
    - levels: [DEBUG]
      sinks: [rotating_file]
  fallback_sinks:
    - rotating_file
```

### Programmatic example

```python
from fapilog import Settings, get_logger
from fapilog.core.settings import RoutingRule

settings = Settings()
settings.sink_routing.enabled = True
settings.sink_routing.rules = [
    RoutingRule(levels=["ERROR", "CRITICAL"], sinks=["postgres", "webhook"]),
    RoutingRule(levels=["INFO", "WARNING"], sinks=["stdout_json"]),
]
settings.sink_routing.fallback_sinks = ["rotating_file"]

logger = get_logger(settings=settings)
```

### Builder API with custom sink names

Use the `name` parameter to create multiple sinks of the same type with unique names for routing:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .add_file("/logs/errors", name="error_file")
    .add_file("/logs/info", name="info_file")
    .with_routing([
        {"levels": ["ERROR", "CRITICAL"], "sinks": ["error_file"]},
        {"levels": ["DEBUG", "INFO", "WARNING"], "sinks": ["info_file"]},
    ])
    .build()
)

logger.error("Goes to /logs/errors")
logger.info("Goes to /logs/info")
```

All `add_*` sink methods support the `name` parameter:

- `add_file(directory, name="rotating_file")`
- `add_stdout(name="stdout_json")`
- `add_http(endpoint, name="http")`
- `add_webhook(endpoint, name="webhook")`
- `add_cloudwatch(log_group, name="cloudwatch")`
- `add_loki(url, name="loki")`
- `add_postgres(dsn, name="postgres")`

Duplicate sink names raise `ValueError` at build time.

## RoutingSink plugin

For manual composition without touching global settings:

```python
from fapilog.plugins.sinks.routing import RoutingSink, RoutingSinkConfig

routing_sink = RoutingSink(
    RoutingSinkConfig(
        routes={
            "ERROR": ["postgres"],
            "CRITICAL": ["postgres", "webhook"],
            "INFO": ["stdout_json"],
            "*": ["rotating_file"],  # fallback
        },
        sink_configs={"postgres": {"table_name": "errors_only"}},
        parallel=True,
    )
)
```

## Tips

- Keep rule lists small; routing is O(1) per event.
- Use overlap=true to send errors to multiple sinks (e.g., DB + webhook).
- Provide fallback_sinks to avoid accidental drops when rules change.
- Routing respects sink circuit breakers; open circuits are skipped automatically.
