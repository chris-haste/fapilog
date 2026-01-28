# Sampling Debug Logs

Use filter-based sampling to trim DEBUG/INFO noise while keeping critical signals intact.

## Probabilistic sampling (20%)

```bash
export FAPILOG_CORE__FILTERS='["sampling"]'
export FAPILOG_FILTER_CONFIG__SAMPLING__CONFIG__SAMPLE_RATE=0.2
```

```python
from fapilog import get_async_logger

async def log_with_sampling():
    logger = await get_async_logger()
    await logger.debug("expensive debug payload", detail="...")
    await logger.info("high-volume event")
    # Sampling applies only to DEBUG/INFO; WARN/ERROR always pass.
```

## Adaptive sampling (target EPS)

Keep a representative sample at high volume, ramp up sampling during quiet periods.

```bash
export FAPILOG_CORE__FILTERS='["adaptive_sampling"]'
export FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__CONFIG__TARGET_EPS=150
export FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__CONFIG__MIN_SAMPLE_RATE=0.01
export FAPILOG_FILTER_CONFIG__ADAPTIVE_SAMPLING__CONFIG__MAX_SAMPLE_RATE=1.0
```

## Trace-aware sampling

Ensure whole traces stay together:

```bash
export FAPILOG_CORE__FILTERS='["trace_sampling"]'
export FAPILOG_FILTER_CONFIG__TRACE_SAMPLING__CONFIG__SAMPLE_RATE=0.15
export FAPILOG_FILTER_CONFIG__TRACE_SAMPLING__CONFIG__TRACE_ID_FIELD=trace_id
```

## Migration note

The legacy `observability.logging.sampling_rate` setting now emits a `DeprecationWarning`. Switch to `core.filters=["sampling"]` (or `adaptive_sampling` / `trace_sampling`) with the corresponding `filter_config.*` block to avoid double-sampling and to expose sampling metrics.
