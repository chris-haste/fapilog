# Structured Error Logging


Capture exceptions with structured stack data.

```python
from fapilog import get_async_logger

logger = await get_async_logger("worker")

try:
    raise ValueError("bad input")
except Exception:
    await logger.error("Processing failed", exc_info=True, job_id="job-1")
```

Output includes exception fields (type/message/stack/frames) merged into the log entry for easier parsing in aggregators.

Notes:
- `exc_info=True` serializes the current exception; you can also pass `exc=<Exception>`.
- Stack depth/size respects settings (`exceptions_max_frames`, `exceptions_max_stack_chars`).
