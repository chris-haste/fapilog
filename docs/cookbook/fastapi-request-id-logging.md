# FastAPI request_id logging (correlation ID middleware, concurrency-safe)

Every HTTP request needs a unique identifier for tracing. Without proper request ID propagation, debugging distributed systems becomes nearly impossible—you can't correlate logs from a single user action across services.

## The Problem: Overlapping Request IDs

A common approach is using `threading.local()` to store the request ID:

```python
import threading
import uuid
from fastapi import FastAPI, Request

# DON'T DO THIS - breaks with async
_local = threading.local()

app = FastAPI()

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    _local.request_id = str(uuid.uuid4())  # Set ID
    response = await call_next(request)
    return response

def get_request_id():
    return getattr(_local, "request_id", None)
```

This breaks under concurrency. When you `await` in async code, Python can switch to another coroutine running on the same thread. That coroutine might overwrite `_local.request_id`, and when your original request resumes, it sees the wrong ID.

**Symptoms:**

- Request IDs appear in logs for the wrong requests
- The same request_id shows up in multiple unrelated requests
- Debug sessions become impossible because logs don't correlate

This is a [frequently asked question on Stack Overflow](https://stackoverflow.com/questions/tagged/fastapi+logging+async) and catches many developers off guard.

## The Solution

fapilog uses Python's `contextvars` module, which correctly isolates context per async task:

```python
from fastapi import FastAPI, Depends
from fapilog.fastapi import setup_logging, get_request_logger

lifespan = setup_logging()
app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root(logger=Depends(get_request_logger)):
    logger.info("request_id is automatically included")
    return {"status": "ok"}
```

That's it. Every log entry automatically includes the `request_id`, and it never leaks between concurrent requests.

**Output:**

```json
{"timestamp": "2026-01-21T10:30:00.123Z", "level": "INFO", "message": "request_id is automatically included", "request_id": "550e8400-e29b-41d4-a716-446655440000"}
```

## Accessing request_id in Deeper Layers

The request ID is available anywhere in your async call stack without passing it explicitly:

```python
from fapilog.core.errors import request_id_var

async def my_service_function():
    """Called deep in the application - no logger passed in."""
    current_request_id = request_id_var.get(None)
    # Use for external API calls, database queries, etc.
    return current_request_id
```

For logging in service layers, get a logger directly:

```python
from fapilog import get_async_logger

async def process_order(order_id: str):
    """Service layer - request_id flows automatically."""
    logger = await get_async_logger("orders")
    await logger.info("Processing order", order_id=order_id)
    # request_id is automatically included via ContextVarsEnricher
```

### Passing Context to Sync Code

If you have synchronous code that runs within an async request (e.g., a sync database driver), the context variable is still accessible:

```python
from fapilog.core.errors import request_id_var

def sync_database_call(query: str):
    """Sync function called from async context."""
    request_id = request_id_var.get(None)
    # request_id is available because contextvars work across sync/async boundaries
    execute_query(query, correlation_id=request_id)
```

## Why This Works (Technical Detail)

Python's `contextvars` module (PEP 567) provides task-local storage that correctly handles async context switches:

1. **Per-task isolation**: Each asyncio Task gets its own copy of context variables
2. **Automatic propagation**: When you `await`, the context follows your execution
3. **No thread confusion**: Unlike `threading.local()`, context doesn't leak between concurrent tasks on the same thread

fapilog's `RequestContextMiddleware` sets `request_id_var` at the start of each request:

```python
# Simplified view of what happens internally
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id")

# In middleware:
token = request_id_var.set(str(uuid.uuid4()))
try:
    response = await call_next(request)
finally:
    request_id_var.reset(token)  # Clean up
```

The `ContextVarsEnricher` (enabled by default) reads this value and adds it to every log entry.

## Going Deeper

- [Exception Logging with Request Context](exception-logging-request-context.md) - Correlate errors with requests
- [FastAPI Logging Example](../examples/fastapi-logging.md) - More middleware options
- [Context Binding Reference](../api-reference/context-binding.md) - Manual context management
- [Context Enrichment](../user-guide/context-enrichment.md) - How enrichers work
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
