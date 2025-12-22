# FastAPI Logging

Request-scoped logging with dependency injection.

```python
from fastapi import FastAPI, Depends
from fapilog import get_async_logger

app = FastAPI()

async def logger_dep():
    return await get_async_logger("request")

@app.get("/users/{user_id}")
async def get_user(user_id: str, logger = Depends(logger_dep)):
    await logger.info("User lookup", user_id=user_id)
    return {"user_id": user_id}
```

Notes:
- Use the async logger in FastAPI apps.
- Bind additional context (request_id/user_id) per request if needed.
- Logger methods are awaitable; drain is handled when the app shuts down if you keep a long-lived logger.
