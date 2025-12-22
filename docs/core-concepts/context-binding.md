# Context Binding



Attach request/task metadata to every log entry via a `ContextVar`.

## How it works

- `logger.bind(key=value, ...)` stores context in a `ContextVar` scoped to the current task/thread.
- Bound context is merged into each log call’s metadata.
- Child asyncio tasks inherit the parent context at creation time; each request should bind explicitly.
- `logger.clear_context()` removes all bound values for the current task.

## Sync example

```python
from fapilog import runtime

with runtime() as logger:
    logger.bind(request_id="req-123", user_id="u-1")
    logger.info("Request started")
    logger.clear_context()
```

## Async example

```python
import asyncio
from fapilog import runtime_async

async def worker(name, logger):
    await logger.info(f"{name} started")

async def main():
    async with runtime_async() as logger:
        logger.bind(request_id="req-123")
        await asyncio.gather(worker("t1", logger), worker("t2", logger))
        logger.clear_context()

asyncio.run(main())
```

## Notes

- Context is per-task; reuse the same logger instance within a request, and bind per request.
- Clearing context at request end prevents leakage across requests.
- You can toggle the built-in `context-vars` enricher if you need to disable automatic ContextVar capture.
