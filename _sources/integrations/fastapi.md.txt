---
orphan: true
---

# FastAPI Integration

This guide shows the FastAPI integration and how to customize it
when you need more control.

## Install

```bash
pip install "fapilog[fastapi]"
```

## Quick Start

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import FastAPIBuilder, get_request_logger

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")  # Includes redaction by default
        .skip_paths(["/health"])
        .sample_rate(0.1)
        .log_errors_on_skip(True)  # Log crashes on skipped paths (default)
        .build()
)

@app.get("/")
async def root(logger=Depends(get_request_logger)):
    await logger.info("Request handled")  # request_id auto-included
    return {"message": "Hello World"}
```

## Automatic middleware registration

Automatic middleware registration is enabled by default:

```python
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder

app = FastAPI()
app.router.lifespan_context = FastAPIBuilder().with_preset("fastapi").build()
```

Middleware order is fixed for correctness:
1. `RequestContextMiddleware`
2. `LoggingMiddleware`

Disable automatic registration when you want manual control:

```python
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .auto_middleware(False)
        .build()
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

## Wrap existing lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder

@asynccontextmanager
async def my_lifespan(app: FastAPI):
    app.state.startup_marker = True
    yield
    app.state.startup_marker = False

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .wrap_lifespan(my_lifespan)
        .build()
)
```

Startup/shutdown order:
1. fapilog creates logger
2. user lifespan startup
3. app runs
4. user lifespan shutdown
5. fapilog drains logger

## Manual middleware (advanced)

If you prefer manual control:

```python
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .auto_middleware(False)
        .build()
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

## Before / After

Before: ~30-40 lines of boilerplate.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fapilog import get_async_logger
from fapilog.fastapi import LoggingMiddleware, RequestContextMiddleware

app_logger = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_logger
    app_logger = await get_async_logger("fastapi")
    yield
    if app_logger:
        await app_logger.drain()

app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

After: builder pattern.

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .build()
)
```

## Redaction

The `fastapi` preset enables automatic redaction of sensitive fields by default:
- `password`, `api_key`, `token`, `secret`, `authorization`
- `api_secret`, `private_key`, `ssn`, `credit_card`

This protects against accidental PII leakage in container logs that flow to centralized systems.

If you need to disable redaction for debugging (not recommended for production):

```python
from fapilog import Settings, get_async_logger

settings = Settings(
    core={"log_level": "INFO", "sinks": ["stdout_json"], "redactors": []},
)
logger = await get_async_logger(settings=settings)
```

For local development with full visibility, use the `dev` preset instead.
