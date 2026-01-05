# Datadog Logs

HTTP-based Datadog integration using `examples/sinks/datadog_sink.py`.

## Quick start (code)

```python
from fapilog import Settings, get_logger
from examples.sinks.datadog_sink import DatadogSink, DatadogSinkConfig

sink = DatadogSink(
    DatadogSinkConfig(
        api_key="your-api-key",
        site="datadoghq.eu",
        service="my-api",
        env="production",
        batch_size=50,
    )
)
logger = get_logger(settings=Settings(), sinks=[sink])
logger.info("hello datadog", user_id=123)
```

## Environment setup (recommended)

```bash
export DD_API_KEY=your-api-key
export DD_SITE=datadoghq.com  # or datadoghq.eu
export DD_SERVICE=my-api
export DD_ENV=production
```

```python
from fapilog import get_logger
from examples.sinks.datadog_sink import DatadogSink

logger = get_logger(sinks=[DatadogSink()])
logger.error("payment failed", order_id="ord-1")
```

## Entry-point registration

```toml
[project.entry-points."fapilog.sinks"]
datadog = "myapp.sinks.datadog_sink:DatadogSink"
```

```yaml
core:
  sinks: ["datadog"]
sink_config:
  datadog:
    service: "my-api"
    env: "production"
    batch_size: 25
```

## Operational notes

- Sends JSON arrays to `http-intake.logs.<site>/api/v2/logs`.
- Uses API key header; keep it in env variables or secret stores.
- Tags propagated via `ddtags` (defaults to `env:<env>`); add custom tags upstream if needed.
- Batch size controls network overhead and Datadog ingestion quotas.

## Troubleshooting

- 403/401 errors: verify `DD_API_KEY` and `DD_SITE`.
- Throttling: reduce batch size or add `rate_limit` filter before sinks.
