# FastAPI Logging

Request-scoped logging with dependency injection and automatic correlation.

## Basic Setup with Middleware

```python
from fastapi import FastAPI
from fapilog.fastapi import RequestContextMiddleware, LoggingMiddleware

app = FastAPI()

# Sets request_id for correlation (from X-Request-ID header or UUID)
app.add_middleware(RequestContextMiddleware)

# Logs request completion with method, path, status, latency_ms
app.add_middleware(LoggingMiddleware)
```

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
logger = await get_async_logger("api")

@app.middleware("http")
async def bind_http_context(request: Request, call_next):
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
