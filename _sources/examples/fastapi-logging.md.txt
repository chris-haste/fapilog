# FastAPI Logging

Request-scoped logging with dependency injection and automatic correlation.

## Basic Setup

```python
from fastapi import FastAPI, Depends
from fapilog.fastapi import FastAPIBuilder, get_request_logger

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .build()
)

@app.get("/users/{user_id}")
async def get_user(user_id: str, logger=Depends(get_request_logger)):
    await logger.info("User lookup", user_id=user_id)
    return {"user_id": user_id}
```

This automatically:
- Initializes the logger in app.state
- Adds `RequestContextMiddleware` for correlation IDs
- Adds `LoggingMiddleware` for request/response logging
- Sets up graceful shutdown with log flushing

## Request-Scoped Logger

```python
from fastapi import FastAPI, Depends
from fapilog import get_async_logger

app = FastAPI()

async def logger_dep():
    return await get_async_logger("request")

@app.get("/users/{user_id}")
async def get_user(user_id: str, logger = Depends(logger_dep)):
    await logger.info("User lookup", user_id=user_id)
    # Log includes request_id automatically via ContextVarsEnricher
    return {"user_id": user_id}
```

## Binding HTTP Context to All Logs

If you need HTTP method/path in every log (not just the completion log):

```python
from fastapi import FastAPI, Request
from fapilog import get_async_logger

app = FastAPI()

@app.middleware("http")
async def bind_http_context(request: Request, call_next):
    logger = await get_async_logger("api")
    with logger.bind(http_method=request.method, http_path=request.url.path):
        return await call_next(request)
```

## Log Correlation

All logs during a request share the same `request_id`:

```json
{"message": "User lookup", "request_id": "abc-123", "user_id": "42"}
{"message": "request_completed", "request_id": "abc-123", "method": "GET", "path": "/users/42", "status": 200}
```

Query by `request_id` to see all logs for a request, including the HTTP context from the completion log.

## Notes

- Use the async logger in FastAPI apps
- `request_id` flows automatically when using `RequestContextMiddleware` + `ContextVarsEnricher`
- The completion log has method/path/status—use `request_id` to correlate
- Use `logger.bind()` only if you specifically need HTTP context in every log entry

## See Also

- [FastAPI request_id Logging (Cookbook)](../cookbook/fastapi-request-id-logging.md) - Deep dive into concurrency-safe correlation IDs
