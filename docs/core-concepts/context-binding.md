# Context Binding

Add request_id, user_id, or any context once—it automatically appears in every log from that request. No need to pass context through your entire call stack.

## How it works

When you call `logger.bind(request_id="123", user_id="abc")`, that context automatically appears in every subsequent log from that request:

- **Bind once at the request boundary** - typically in middleware or at the start of a handler
- **Every log includes it** - no need to pass request_id as a parameter through 10 function calls
- **Each request gets its own context** - one user's logs won't leak into another's
- **Clear when done** - `logger.clear_context()` removes bound values (optional, automatic with `runtime()`)

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

## Tips

- **Bind at the start of each request** - In FastAPI, this happens automatically with `setup_logging()`. In other frameworks, bind in your middleware.
- **Use `runtime()` or `runtime_async()`** - These context managers automatically clear context when the request ends, preventing leakage.
- **Common fields to bind**: `request_id`, `user_id`, `tenant_id`, `trace_id`, `correlation_id`
