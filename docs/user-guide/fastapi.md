# FastAPI / ASGI Integration

Use the async factory for request-scoped logging with dependency injection:

```python
from fastapi import Depends, FastAPI
from fapilog import get_async_logger

app = FastAPI()

async def get_logger():
    return await get_async_logger("request")

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger = Depends(get_logger)):
    await logger.info("User lookup", user_id=user_id)
    return {"user_id": user_id}
```

## Choosing sync vs async
- **Async apps (FastAPI/ASGI, asyncio workers)**: prefer `get_async_logger` or `runtime_async`.
- **Sync apps/scripts**: `get_logger` or `runtime`.
- Migration from sync to async: replace `get_logger` with `await get_async_logger`, and ensure log calls are awaited.
