# Context Enrichment


Attach business/request metadata to every log entry.

## Binding context

```python
from fapilog import runtime

with runtime() as logger:
    logger.bind(request_id="req-1", user_id="u-123")
    logger.info("Request started")
    logger.clear_context()
```

## Async pattern

```python
import asyncio
from fapilog import runtime_async

async def handle(user_id: str):
    async with runtime_async() as logger:
        logger.bind(user_id=user_id)
        await logger.info("Handling user")
        logger.clear_context()

asyncio.run(handle("u-1"))
```

## Built-in enrichers

- `runtime-info`: service/env/version/host/pid/python.
- `context-vars`: request/user IDs from ContextVar when present.

Toggle at runtime:

```python
from fapilog.plugins.enrichers.runtime_info import RuntimeInfoEnricher

logger.disable_enricher("context_vars")
logger.enable_enricher(RuntimeInfoEnricher())
```

## Tips

- Bind per request/task; clear when done.
- Avoid deeply nested objects for better performance; use simple dicts/strings/numbers.
