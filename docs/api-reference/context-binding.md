# Context Binding

Attach request- or task-scoped metadata to every log entry via the logger's context API.

## bind {#bind}

```python
logger.bind(**kwargs) -> Logger
await async_logger.bind(**kwargs)  # returns the same logger
```

Adds key/value pairs to the bound context for the current task/thread. Bound fields are merged into all subsequent log calls until removed.

### Example (sync)

```python
logger = get_logger()
logger.bind(request_id="req-123", user_id="user-456")
logger.info("Request started")
# Output will include request_id and user_id
```

### Example (async)

```python
async with runtime_async() as logger:
    logger.bind(job_id="job-9")
    await logger.info("Job queued")
```

## unbind {#unbind}

```python
logger.unbind(*keys) -> None
```

Remove specific keys from the bound context for the current task/thread.

### Example

```python
logger.bind(request_id="req-123", user_id="user-456", temp_flag=True)
logger.unbind("temp_flag", "user_id")
logger.info("Context now only has request_id")
```

## clear_context {#clear_context}

```python
logger.clear_context() -> None
```

Remove all bound context values for the current task/thread.

### Example

```python
logger.bind(request_id="req-123")
logger.info("With context")
logger.clear_context()
logger.info("Context cleared")
```

## Inheritance across tasks

Context is stored in a `ContextVar`, so it flows into asyncio tasks spawned from the same parent context:

```python
import asyncio
from fapilog import runtime_async

async def child(name, logger):
    await logger.info(f"{name} started")

async def main():
    async with runtime_async() as logger:
        logger.bind(request_id="req-123")
        await asyncio.gather(child("task1", logger), child("task2", logger))

asyncio.run(main())
```

---

_Use context binding to keep correlation IDs and user/request data attached to every log call._
