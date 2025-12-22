# Sampling Debug Logs

Reduce debug/info volume with sampling.

```bash
# Keep 20% of DEBUG/INFO logs; WARN/ERROR unaffected
export FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE=0.2
```

```python
from fapilog import get_async_logger

logger = await get_async_logger()
await logger.debug("expensive debug payload", detail="...")
await logger.info("high-volume event")
# Sampling applies only to DEBUG/INFO
```