# Django Structured JSON Logging with Correlation IDs

Django's default logging produces unstructured text that's difficult to parse in production environments. This guide shows how to add structured JSON logging with correlation IDs to your Django application using fapilog.

## The Problem

Django applications typically produce logs like:

```
INFO 2026-01-21 10:30:00,123 views Processing order 12345
WARNING 2026-01-21 10:30:00,456 views Order 12345 has low stock
ERROR 2026-01-21 10:30:01,789 views Payment failed for order 12345
```

This format causes several issues:

1. **No correlation** - Can't link related log entries across a request lifecycle
2. **Unstructured data** - Log aggregators can't filter by order ID, user ID, or other fields
3. **Blocking writes** - File-based logging can slow down request handling
4. **No PII protection** - Sensitive data logged without redaction

## The Solution

fapilog provides structured JSON logging that works with Django's synchronous request model:

```python
# settings.py
from fapilog import get_logger

# get_logger() returns a SyncLoggerFacade - designed for Django's sync model
# The async queue ensures non-blocking writes even in sync code
FAPILOG_LOGGER = get_logger(format="json")
```

```python
# views.py
from django.conf import settings
from django.http import JsonResponse

def order_detail(request, order_id):
    settings.FAPILOG_LOGGER.info(
        "Processing order",
        order_id=order_id,
        user_id=request.user.id,
    )
    return JsonResponse({"order_id": order_id, "status": "shipped"})
```

**Output:**
```json
{"timestamp": "2026-01-21T10:30:00.123Z", "level": "INFO", "message": "Processing order", "order_id": "12345", "user_id": 42}
```

> **Note:** This guide demonstrates manual wiring for Django. fapilog provides first-class FastAPI integration with automatic middleware and dependency injection. If there's interest in a dedicated `fapilog-django` plugin, [open a discussion](https://github.com/fapilog/fapilog/discussions).

## Adding Correlation IDs

Correlation IDs let you trace all log entries for a single request. Django uses one thread per request (in WSGI deployments), so thread-local storage works well:

```python
# middleware/correlation.py
import threading
import uuid

_correlation_id = threading.local()


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return getattr(_correlation_id, "value", "unknown")


class CorrelationIdMiddleware:
    """Middleware that assigns a correlation ID to each request.

    Accepts X-Correlation-ID from upstream services (load balancers, API gateways)
    or generates a new UUID if not present.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Accept from upstream or generate new
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        _correlation_id.value = correlation_id
        request.correlation_id = correlation_id

        response = self.get_response(request)

        # Include in response for client-side debugging
        response["X-Correlation-ID"] = correlation_id
        return response
```

Register in settings:

```python
# settings.py
MIDDLEWARE = [
    "middleware.correlation.CorrelationIdMiddleware",  # First, so ID is available early
    "django.middleware.security.SecurityMiddleware",
    # ... other middleware
]
```

Now include the correlation ID in your logs:

```python
# views.py
from middleware.correlation import get_correlation_id

def order_detail(request, order_id):
    settings.FAPILOG_LOGGER.info(
        "Processing order",
        order_id=order_id,
        correlation_id=get_correlation_id(),
    )
    # ...
```

## Request/Response Logging Middleware

Log every HTTP request with timing and status:

```python
# middleware/request_logging.py
import time
from django.conf import settings
from middleware.correlation import get_correlation_id


class RequestLoggingMiddleware:
    """Log HTTP requests with method, path, status, and duration."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = settings.FAPILOG_LOGGER

    def __call__(self, request):
        start = time.perf_counter()

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start) * 1000

        self.logger.info(
            "HTTP request",
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            correlation_id=get_correlation_id(),
            user_id=getattr(request.user, "id", None),
        )

        return response
```

```python
# settings.py
MIDDLEWARE = [
    "middleware.correlation.CorrelationIdMiddleware",
    "middleware.request_logging.RequestLoggingMiddleware",  # After correlation
    "django.middleware.security.SecurityMiddleware",
    # ...
]
```

**Output:**
```json
{"timestamp": "2026-01-21T10:30:00.456Z", "level": "INFO", "message": "HTTP request", "method": "GET", "path": "/api/orders/12345", "status_code": 200, "duration_ms": 15.23, "correlation_id": "550e8400-e29b-41d4-a716-446655440000", "user_id": 42}
```

## Exception Logging with Request Context

Capture unhandled exceptions with full request context using Django's `got_request_exception` signal:

```python
# middleware/exception_logging.py
from django.conf import settings
from django.core.signals import got_request_exception
from middleware.correlation import get_correlation_id


def log_exception(sender, request, **kwargs):
    """Log unhandled exceptions with request context."""
    import sys

    exc_info = sys.exc_info()
    if exc_info[0] is None:
        return

    settings.FAPILOG_LOGGER.error(
        "Unhandled exception",
        exc_info=exc_info,
        correlation_id=get_correlation_id(),
        method=request.method,
        path=request.path,
        user_id=getattr(request.user, "id", None),
    )


# Connect the signal handler
got_request_exception.connect(log_exception)
```

Import in your app's `apps.py` to ensure the signal is connected:

```python
# your_app/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "your_app"

    def ready(self):
        import middleware.exception_logging  # noqa: F401
```

## Async Views (Django 4.1+)

Django's async views use a different concurrency model. For async views, use `contextvars` instead of thread-locals:

```python
# middleware/correlation_async.py
import contextvars
import uuid

_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="unknown"
)


def get_correlation_id() -> str:
    """Get correlation ID (works in both sync and async contexts)."""
    return _correlation_id_var.get()


class CorrelationIdMiddleware:
    """Async-compatible correlation ID middleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        _correlation_id_var.set(correlation_id)
        request.correlation_id = correlation_id

        response = self.get_response(request)

        response["X-Correlation-ID"] = correlation_id
        return response

    async def __acall__(self, request):
        """Handle async requests."""
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        _correlation_id_var.set(correlation_id)
        request.correlation_id = correlation_id

        response = await self.get_response(request)

        response["X-Correlation-ID"] = correlation_id
        return response
```

> **Tip:** If you're using Django with ASGI (Daphne, Uvicorn), the `contextvars` approach handles both sync and async views correctly.

## Production Configuration

### WSGI Deployment (Gunicorn)

```python
# settings.py
from fapilog import get_logger

# JSON format for log aggregators
FAPILOG_LOGGER = get_logger(format="json")

# Optional: Configure via environment variables
# FAPILOG_CORE__LOG_LEVEL=INFO
# FAPILOG_CORE__FORMAT=json
```

```bash
# gunicorn.conf.py or command line
gunicorn myproject.wsgi:application \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --access-logfile -  # stdout for container logging
```

### ASGI Deployment (Uvicorn/Daphne)

For async Django with ASGI:

```bash
uvicorn myproject.asgi:application \
    --workers 4 \
    --host 0.0.0.0 \
    --port 8000
```

Use the `contextvars`-based middleware shown above for proper correlation ID handling in async contexts.

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

## Bypassing Django's LOGGING Setting

fapilog operates independently of Django's `LOGGING` configuration. This is intentional:

- **Simpler setup** - No complex `LOGGING` dict to maintain
- **Consistent behavior** - Same logging across Django and non-Django code
- **Non-blocking writes** - fapilog's async queue handles I/O

If you need to capture logs from Django internals or third-party libraries that use stdlib `logging`, you can add a bridge handler:

```python
# settings.py
import logging
from fapilog import get_logger

FAPILOG_LOGGER = get_logger(format="json")


class FapilogHandler(logging.Handler):
    """Bridge stdlib logging to fapilog."""

    def emit(self, record):
        FAPILOG_LOGGER.log(
            record.levelname.lower(),
            record.getMessage(),
            logger_name=record.name,
        )


# Add to Django's logging config if needed
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "fapilog": {
            "()": FapilogHandler,
        },
    },
    "root": {
        "handlers": ["fapilog"],
        "level": "WARNING",  # Only capture warnings and above from Django internals
    },
}
```

## Celery Task Correlation

To propagate correlation IDs to Celery tasks:

```python
# tasks.py
from celery import shared_task
from middleware.correlation import get_correlation_id
from django.conf import settings


@shared_task(bind=True)
def process_order(self, order_id, correlation_id=None):
    settings.FAPILOG_LOGGER.info(
        "Processing order in background",
        order_id=order_id,
        correlation_id=correlation_id or "unknown",
        celery_task_id=self.request.id,
    )
    # ... task logic


# When calling the task, pass the correlation ID
def order_view(request, order_id):
    process_order.delay(order_id, correlation_id=get_correlation_id())
    return JsonResponse({"status": "queued"})
```

## Going Deeper

- [Non-blocking Async Logging](non-blocking-async-logging.md) - How fapilog's async queue protects request latency
- [Redacting Secrets and PII](redacting-secrets-pii.md) - Automatic PII redaction for compliance
- [Exception Logging with Request Context](exception-logging-request-context.md) - More patterns for error logging
- [FastAPI JSON Logging](fastapi-json-logging.md) - First-class FastAPI integration for comparison
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
