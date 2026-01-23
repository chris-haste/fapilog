# Logging request/response bodies without hanging (safe patterns)

Want to log request bodies for debugging API issues? Here's how to do it without breaking your app.

## The Problem: Why Body Logging Breaks

Reading request bodies in middleware seems straightforward—but it has hidden pitfalls that cause hangs, broken routes, and streaming failures.

### Don't Do This

```python
from fastapi import FastAPI

app = FastAPI()


@app.middleware("http")
async def log_body(request, call_next):
    # This will break your app
    body = await request.body()
    print(f"Request body: {body}")
    response = await call_next(request)
    return response
```

This pattern causes several problems:

1. **Body consumed twice** — `request.body()` reads the stream. Your route handler tries to read it again and gets empty bytes or hangs waiting for data that already arrived.

2. **Memory exhaustion** — Large file uploads or payloads get loaded entirely into memory before your route even runs.

3. **Event loop blocking** — Synchronous `print()` blocks the event loop. With high traffic, your app becomes unresponsive.

### Common Symptoms

If you've added body logging and see these issues, this is likely the cause:

- Routes hang indefinitely
- `422 Unprocessable Entity` on valid JSON
- Empty `request.json()` in route handlers
- Streaming uploads fail or timeout
- Memory usage spikes under load

## The Solution: Cache the Body

The key is reading the body once and making it available to both your middleware and route handler. Starlette provides `receive` caching for this.

### Safe Body Logging Middleware

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from fapilog.fastapi import setup_logging

app = FastAPI(lifespan=setup_logging(preset="fastapi"))


class BodyLoggingMiddleware(BaseHTTPMiddleware):
    """Safely log request bodies without consuming them."""

    MAX_BODY_LOG = 10_000  # Truncate bodies larger than 10KB

    async def dispatch(self, request: Request, call_next):
        # Cache the body so it can be read multiple times
        body = await request.body()

        # Access the logger from app state
        logger = request.app.state.fapilog_logger

        # Log truncated body
        body_preview = body[: self.MAX_BODY_LOG]
        if len(body) > self.MAX_BODY_LOG:
            body_preview = body_preview + b"...[truncated]"

        await logger.debug(
            "request_body",
            path=request.url.path,
            method=request.method,
            body=body_preview.decode("utf-8", errors="replace"),
            body_size=len(body),
            truncated=len(body) > self.MAX_BODY_LOG,
        )

        response = await call_next(request)
        return response


# Add after setup_logging configures the app
app.add_middleware(BodyLoggingMiddleware)
```

This works because:
- `BaseHTTPMiddleware` automatically caches the body when you call `request.body()`
- Subsequent calls (including in your route) return the cached bytes
- We truncate before logging to avoid memory issues
- fapilog's async logger doesn't block the event loop

### Response Body Logging

Logging response bodies is trickier—you need to intercept the streaming response. Here's a safe pattern:

```python
from starlette.responses import Response
from starlette.types import Message


class ResponseBodyMiddleware(BaseHTTPMiddleware):
    """Log response bodies with size limits."""

    MAX_RESPONSE_LOG = 10_000

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only log for JSON responses under size limit
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Collect response body chunks
        body_chunks = []
        total_size = 0

        async def receive_body(message: Message):
            nonlocal total_size
            if message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if total_size < self.MAX_RESPONSE_LOG:
                    body_chunks.append(chunk)
                total_size += len(chunk)

        # This requires a custom response wrapper—see full example below
        # For simplicity, log from route handlers instead

        return response
```

For most use cases, logging response bodies from route handlers is simpler and safer than middleware interception.

## Truncation for Large Bodies

Always limit how much body data you log. The examples above use a fixed byte limit, but fapilog's `size_guard` processor provides automatic truncation for all log payloads:

```python
from fapilog import LoggerBuilder

logger = await (
    LoggerBuilder()
    .with_size_guard(max_bytes="100 KB", action="truncate")
    .build_async()
)
```

With `size_guard` enabled:
- Payloads exceeding `max_bytes` are automatically truncated
- A `_truncated: true` field marks truncated entries
- Critical fields like `message` are preserved

### What Truncated Output Looks Like

```json
{
  "message": "request_body",
  "body": "{ \"user\": \"alice\", \"data\": \"...[truncated]",
  "body_size": 150000,
  "_truncated": true,
  "path": "/api/upload"
}
```

### Adjusting Truncation Limits

```python
# More aggressive truncation for high-volume endpoints
logger = await (
    LoggerBuilder()
    .with_size_guard(
        max_bytes="10 KB",
        action="truncate",
        preserve_fields=["correlation_id", "path", "method"],
    )
    .build_async()
)
```

## Bodies Are Redacted Too

Request and response bodies pass through the same redaction pipeline as all log fields. Sensitive data in JSON bodies is automatically masked.

### Redacted Body Example

With field-based redaction enabled:

```python
from fapilog import LoggerBuilder

logger = await (
    LoggerBuilder()
    .with_field_mask(fields=["password", "credit_card", "ssn"])
    .build_async()
)

# Request body: {"username": "alice", "password": "hunter2"}
await logger.info(
    "login_request",
    body={"username": "alice", "password": "hunter2"},
)

# Log output: password is masked
# {"message": "login_request", "body": {"username": "alice", "password": "***"}}
```

### JSON Body Redaction

When logging parsed JSON bodies, pass them as dictionaries rather than strings to enable deep redaction:

```python
# Good: Dict enables field-level redaction
body_dict = await request.json()
await logger.debug("request_body", body=body_dict)

# Less effective: String only gets pattern matching
body_str = (await request.body()).decode()
await logger.debug("request_body", body=body_str)
```

## Summary

| Problem | Solution |
|---------|----------|
| Body consumed twice | Use `BaseHTTPMiddleware` (caches automatically) |
| Memory exhaustion | Truncate before logging |
| Event loop blocking | Use fapilog's async logger |
| Sensitive data in bodies | Enable redaction, pass dicts not strings |

## Going Deeper

- [Redacting Secrets and PII](redacting-secrets-pii.md) - Complete redaction configuration
- [Non-blocking Async Logging](non-blocking-async-logging.md) - Backpressure and queue management
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
