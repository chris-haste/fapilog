# Context Values Missing



## Symptoms
- `request_id`/`user_id` not present in logs
- Context appears on some entries but not others
- Async tasks lose correlation

## Causes
- Context not bound for each request/task
- Context cleared too early
- Logger reused across loops without rebinding

## Fixes
```python
from fapilog import runtime_async

async def handle_request(request_id: str, user_id: str):
    async with runtime_async() as logger:
        logger.bind(request_id=request_id, user_id=user_id)
        await logger.info("started")
        # ... work ...
        logger.clear_context()  # end-of-request cleanup
```

Tips:
- Bind per request/task; don’t rely on global context.
- For child asyncio tasks, create them after binding to inherit the ContextVar.
- Avoid clearing context before the request/task is done.
