# FastAPI / ASGI Integration

## Request/response logging middleware

Add the built-in middleware for automatic request/response logs with latency and status codes:

```python
from fastapi import FastAPI
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI()
app.add_middleware(RequestContextMiddleware)  # sets correlation IDs from headers or UUIDs
app.add_middleware(LoggingMiddleware)        # emits request_completed / request_failed
```

Key fields emitted: `method`, `path`, `status_code`, `latency_ms`, `correlation_id`, `client_ip`, `user_agent`. Uncaught exceptions log `request_failed` and re-raise so FastAPI can render the error.

Skip specific paths via `skip_paths=["/health"]`, or inject your own logger instance: `LoggingMiddleware(logger=my_async_logger)`.

Marketplace router (plugin discovery) remains available via `from fapilog.fastapi import get_router`, but it is optional and separate from request logging.

### Middleware options

- `sample_rate` (default 1.0): apply probabilistic sampling to successful `request_completed` logs; errors are always logged.
- `include_headers` (default False) + `redact_headers`: when enabled, include headers in the log metadata, masking any header names listed in `redact_headers` with `***`.
- `skip_paths`: list of paths to skip logging (e.g., health checks).

Example with options:

```python
app.add_middleware(
    LoggingMiddleware,
    sample_rate=0.1,
    include_headers=True,
    redact_headers=["authorization", "cookie"],
    skip_paths=["/healthz"],
)
```

## Dependency-based logging

Prefer the async factory for request-scoped logging with dependency injection:

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
