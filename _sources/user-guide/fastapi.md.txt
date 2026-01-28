# FastAPI / ASGI Integration

For a complete, production-ready example with health checks, metrics, and graceful shutdown, see the [FastAPI Production Template](https://github.com/chris-haste/fapilog/tree/main/examples/fastapi_production).

## One-liner setup

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import get_request_logger, setup_logging

app = FastAPI(
    lifespan=setup_logging(
        preset="fastapi",
        skip_paths=["/health"],
        sample_rate=1.0,
        include_headers=True,  # Sensitive headers redacted by default
    )
)

@app.get("/")
async def root(logger=Depends(get_request_logger)):
    await logger.info("Request handled")  # request_id auto-included
    return {"message": "Hello World"}
```

Automatic middleware registration is enabled by default. Disable it for manual control:

```python
from fapilog.fastapi import setup_logging
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI(lifespan=setup_logging(preset="fastapi", auto_middleware=False))
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

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

### Middleware options

- `sample_rate` (default 1.0): apply probabilistic sampling to successful `request_completed` logs; errors are always logged.
- `include_headers` (default False): include headers in log metadata. **Security:** Sensitive headers are redacted by default (see below).
- `skip_paths`: list of paths to skip logging (e.g., health checks). See [Skipping Health/Metrics Endpoints](../cookbook/skip-noisy-endpoints.md) for patterns and best practices.
- `log_errors_on_skip` (default True): when True, unhandled exceptions on skipped paths are logged at ERROR level. Set to False for complete silence on skipped paths.

#### Header redaction (security)

When `include_headers=True`, the following headers are **redacted by default** to prevent accidental credential leakage:

- `authorization`, `proxy-authorization`, `www-authenticate`
- `cookie`, `set-cookie`
- `x-api-key`, `x-auth-token`, `x-csrf-token`, `x-forwarded-authorization`

**Extending defaults** — add custom headers to the redaction list:

```python
app.add_middleware(
    LoggingMiddleware,
    include_headers=True,
    additional_redact_headers=["x-internal-token", "x-secret-key"],
)
```

**Allowlist mode** — only log specific headers (all others excluded):

```python
app.add_middleware(
    LoggingMiddleware,
    include_headers=True,
    allow_headers=["content-type", "accept", "user-agent"],
)
```

**Disabling defaults** (not recommended):

```python
app.add_middleware(
    LoggingMiddleware,
    include_headers=True,
    disable_default_redactions=True,  # Emits a warning
)
```

Example with options:

```python
app.add_middleware(
    LoggingMiddleware,
    sample_rate=0.1,
    include_headers=True,
    additional_redact_headers=["x-custom-secret"],
    skip_paths=["/healthz"],
    log_errors_on_skip=True,  # Still log crashes on health endpoints
)
```

## Dependency-based logging

Prefer the async dependency helper for request-scoped logging with dependency injection:

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import get_request_logger

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_request_logger)):
    await logger.info("User lookup", user_id=user_id)
    return {"user_id": user_id}
```

## Choosing sync vs async
- **Async apps (FastAPI/ASGI, asyncio workers)**: prefer `get_async_logger` or `runtime_async`.
- **Sync apps/scripts**: `get_logger` or `runtime`.
- Migration from sync to async: replace `get_logger` with `await get_async_logger`, and ensure log calls are awaited.

## HTTP Context Correlation

### How request_id Works

When using `RequestContextMiddleware`, every request gets a `request_id` that automatically flows through to all logs:

```
Request starts → RequestContextMiddleware sets request_id="abc-123"
  ↓
Your code logs: {"message": "Fetching user", "request_id": "abc-123", "user_id": 42}
  ↓
Request ends → LoggingMiddleware logs: {"method": "GET", "path": "/users/42", "status": 200, "request_id": "abc-123"}
```

The `request_id` correlates all logs to the request. Use it to:
- Find all logs for a specific request
- Link errors to their HTTP context (method, path, status in the completion log)
- Trace requests across services (pass `X-Request-ID` header)

### Binding HTTP Context Explicitly

If you need HTTP method/path in every log entry (not just the completion log), use `logger.bind()`:

```python
from fastapi import FastAPI, Request
from fapilog import get_async_logger

app = FastAPI()
logger = await get_async_logger("api")

@app.middleware("http")
async def bind_http_context(request: Request, call_next):
    # Bind HTTP context for all logs during this request
    with logger.bind(http_method=request.method, http_path=request.url.path):
        return await call_next(request)

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    await logger.info("Fetching user", user_id=user_id)
    # Log includes: http_method="GET", http_path="/users/42"
    return {"user_id": user_id}
```

### Querying Correlated Logs

In your log aggregator (Loki, Elasticsearch, CloudWatch):

```
# Find all logs for a specific request
request_id="abc-123"

# Find requests to a specific endpoint (completion logs)
message="request_completed" AND path="/api/users/*"

# Then drill into a specific request
request_id="<id from above>"
```

### When to Use Each Pattern

| Use Case | Recommended Approach |
|----------|---------------------|
| Debugging a specific error | Query by `request_id` from error log |
| Finding slow endpoints | Query completion logs by `latency_ms > 1000` |
| Security audit by IP | Query completion logs (include `client_ip`) |
| Adding HTTP context to every log | Use `logger.bind()` in middleware |

**Note:** The `request_id` correlation pattern is usually sufficient. Adding method/path to every log increases log size without significant benefit—the completion log already has this data with the same `request_id`.
