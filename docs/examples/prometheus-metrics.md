# Prometheus Metrics


Enable internal metrics; export them from your app.

```bash
export FAPILOG_CORE__ENABLE_METRICS=true
```

```python
from fapilog import Settings, get_logger

settings = Settings(core__enable_metrics=True)
logger = get_logger(settings=settings)
logger.info("metrics on")
```

What’s recorded:
- Events submitted/dropped
- Queue high-watermark
- Backpressure waits
- Flush latency
- Sink errors

Expose metrics via your own HTTP endpoint/registry; fapilog does not start a Prometheus server by itself.
