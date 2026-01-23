# Exception logging in FastAPI with request_id + structured context

When your FastAPI app crashes, you need to know which request caused it. Without proper context, exception logs become a pile of stack traces with no way to trace them back to specific user actions.

## The Problem: Lost Context in Errors

Default FastAPI exception handling logs the stack trace but loses the request context:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # This exception loses all request context
    raise ValueError(f"User {user_id} not found")
```

When this crashes, you see:

```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "...", line 42, in __call__
    ...
ValueError: User 123 not found
```

**What's missing:**

- Which request triggered this error?
- What was the URL path?
- Who made the request?
- How do I correlate this with other logs from the same request?

## The Solution: Automatic Context Preservation

fapilog's middleware automatically preserves request context in error logs:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

lifespan = setup_logging()
app = FastAPI(lifespan=lifespan)

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    raise ValueError(f"User {user_id} not found")
```

Now when the same exception occurs, fapilog logs:

```json
{
  "timestamp": "2026-01-21T10:30:00.123Z",
  "level": "ERROR",
  "message": "request_failed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "path": "/users/123",
  "method": "GET",
  "status_code": 500,
  "error_type": "ValueError",
  "error": "User 123 not found",
  "latency_ms": 12.5
}
```

Every field you need to debug the issue is right there.

## Custom Exception Handlers

For custom exception handling, use `get_request_logger` to maintain context:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fapilog.fastapi import setup_logging, get_request_logger

lifespan = setup_logging()
app = FastAPI(lifespan=lifespan)

class UserNotFoundError(Exception):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")

@app.exception_handler(UserNotFoundError)
async def handle_user_not_found(request: Request, exc: UserNotFoundError):
    logger = await get_request_logger(request)
    await logger.warning(
        "user_not_found",
        user_id=exc.user_id,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=404,
        content={"error": "User not found", "user_id": exc.user_id},
    )
```

The logger automatically includes the `request_id` from the current request context.

## Structured Error Fields

When fapilog captures an exception, it includes these structured fields:

| Field | Description |
|-------|-------------|
| `error_type` | Exception class name (e.g., `ValueError`) |
| `error` | Exception message (`str(exception)`) |
| `request_id` | Correlation ID for the request |
| `path` | Request URL path |
| `method` | HTTP method (GET, POST, etc.) |
| `status_code` | HTTP response status |
| `latency_ms` | Request duration in milliseconds |

For full stack trace capture, pass `exc_info=True`:

```python
try:
    process_payment(order)
except PaymentError as e:
    await logger.error(
        "payment_failed",
        order_id=order.id,
        exc_info=True,  # Captures full traceback
    )
    raise
```

This adds the `exception` field with detailed traceback info:

```json
{
  "level": "ERROR",
  "message": "payment_failed",
  "request_id": "abc-123",
  "order_id": "order-456",
  "exception": {
    "error.type": "PaymentError",
    "error.message": "Card declined",
    "error.stack": "Traceback (most recent call last):\n  ...",
    "error.frames": [
      {"file": "payment.py", "line": 42, "function": "charge", "code": "..."}
    ]
  }
}
```

## Going Deeper

- [FastAPI request_id Logging](fastapi-request-id-logging.md) - How request context propagates
- [Context Binding Reference](../api-reference/context-binding.md) - Manual context management
- [Context Enrichment](../user-guide/context-enrichment.md) - How enrichers work
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
