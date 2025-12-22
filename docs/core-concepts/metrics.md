# Metrics



Optional internal metrics for observability.

## Enabling

Set `core.enable_metrics=True` (env: `FAPILOG_CORE__ENABLE_METRICS=true`). Metrics are recorded asynchronously; exporting is left to the application.

## What is recorded

- Events submitted/dropped
- Queue high-watermark
- Backpressure waits
- Flush latency (per batch)
- Sink errors

## Usage

```python
from fapilog import Settings, get_logger

settings = Settings(core__enable_metrics=True)
logger = get_logger(settings=settings)
logger.info("metrics enabled")
```

Expose or scrape metrics from your application using your preferred exporter; fapilog does not start an HTTP metrics server itself.
