# FastAPI Logging

Request-scoped logging with dependency injection and automatic correlation.

## Basic Setup with Middleware

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging, RequestContextMiddleware, LoggingMiddleware

app = FastAPI()

# Initialize logger in app.state (recommended)
setup_logging(app)

# Sets request_id for correlation (from X-Request-ID header or UUID)
app.add_middleware(RequestContextMiddleware)

# Logs request completion with method, path, status, latency_ms
# Use require_logger=True to fail fast if logger not initialized
app.add_middleware(LoggingMiddleware, require_logger=True)
```

## Production Pattern

For production, use `require_logger=True` to catch initialization issues early:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging, LoggingMiddleware

app = FastAPI()
setup_logging(app)  # Sets app.state.fapilog_logger
app.add_middleware(LoggingMiddleware, require_logger=True)
```

This avoids latency spikes from lazy logger creation on cold-start requests. If you forget to call `setup_logging()`, the middleware raises a clear error:

```
RuntimeError: LoggingMiddleware requires logger in app.state.
Call setup_logging(app) before adding middleware, or pass logger= parameter.
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
