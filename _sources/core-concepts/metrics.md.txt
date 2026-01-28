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

## System Metrics

System metrics (CPU usage, memory, disk I/O) are provided by the `runtime_info` enricher when the `system` extra is installed.

> **Platform Note:** System metrics require `psutil`, which is only installed on Linux and macOS. On Windows, system metrics fields will not be populated.
>
> ```bash
> # Linux/macOS - psutil installed, system metrics available
> pip install fapilog[system]
>
> # Windows - psutil not installed, system metrics unavailable
> pip install fapilog[system]  # Installs fapilog but not psutil
> ```

## Usage

```python
from fapilog import Settings, get_logger

settings = Settings(core__enable_metrics=True)
logger = get_logger(settings=settings)
logger.info("metrics enabled")
```

Expose or scrape metrics from your application using your preferred exporter; fapilog does not start an HTTP metrics server itself.
