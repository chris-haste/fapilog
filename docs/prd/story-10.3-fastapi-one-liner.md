# Story 10.3: One-Liner FastAPI Integration

## Context / Background

Currently, integrating fapilog with FastAPI requires 60+ lines of boilerplate code across multiple files:

**Current experience** (from `examples/fastapi_async_logging/main.py`):
```python
# 1. Manual lifespan manager (~20 lines)
app_logger = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_logger
    app_logger = await get_async_logger("fastapi_app")
    await app_logger.info("Application starting up")
    yield
    if app_logger:
        await app_logger.info("Application shutting down")
        await app_logger.drain()

# 2. Manual middleware addition (~6 lines)
from fapilog.fastapi import RequestContextMiddleware, LoggingMiddleware
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware, skip_paths=["/health"])

# 3. Manual logger dependency (~15 lines)
async def get_request_logger(request: Request) -> Any:
    logger = await get_async_logger("request")
    bound_logger = logger.bind(
        request_id=request.headers.get("X-Request-ID", "unknown"),
        user_agent=request.headers.get("User-Agent", "unknown"),
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
    )
    return bound_logger

# 4. Use in routes (~3 lines each)
@app.get("/")
async def root(logger: Any = Depends(get_request_logger)):
    await logger.info("Root endpoint accessed")
    return {"message": "Hello World"}
```

**Total: ~60+ lines of boilerplate**

**Target experience** (one-liner):
```python
from fapilog.fastapi import setup_logging, get_request_logger
from fastapi import FastAPI, Depends

# One line to configure everything
app = FastAPI(lifespan=setup_logging(preset="production"))

# Routes get automatic request context
@app.get("/")
async def root(logger = Depends(get_request_logger)):
    await logger.info("Request handled")  # request_id auto-included
    return {"message": "Hello World"}
```

**Total: ~2 lines of setup, automatic context propagation**

This story implements the `setup_logging()` helper and `get_request_logger` dependency to reduce FastAPI integration from 60+ lines to 2 lines.

## Scope (In / Out)

### In Scope

- `setup_logging()` function that returns configured lifespan
- Lifespan wrapper approach (can wrap user's existing lifespan)
- `get_request_logger` dependency for routes
- Automatic middleware registration (RequestContext + Logging)
- Preset integration (use Story 10.1 presets)
- Automatic logger cleanup on shutdown
- Configuration pass-through to middleware (skip_paths, sample_rate, etc.)
- Comprehensive tests and documentation
- Before/after examples showing line reduction

### Out of Scope

- Request body logging (defer to Story 10.4+)
- Response body logging (defer to Story 10.4+)
- Custom logger naming (use default "fastapi")
- Middleware ordering customization (fixed order for correctness)
- Lifespan events exposure (users wrap their own lifespan if needed)
- Breaking changes to existing middleware classes

## Acceptance Criteria

### AC1: setup_logging() Returns Lifespan

**Function signature:**
```python
def setup_logging(
    app: FastAPI | None = None,
    *,
    preset: str | None = None,
    skip_paths: list[str] | None = None,
    sample_rate: float = 1.0,
    redact_headers: list[str] | None = None,
    wrap_lifespan: Callable | None = None,
) -> AsyncContextManager:
    """One-liner FastAPI logging setup.

    Returns an async context manager (lifespan) that:
    - Creates async logger on startup
    - Adds middleware if app provided
    - Drains logger on shutdown
    - Wraps user's lifespan if provided

    Args:
        app: FastAPI app instance (optional, for middleware configuration)
        preset: Logger preset (dev, production, fastapi, minimal)
        skip_paths: Paths to skip logging (e.g., ["/health", "/metrics"])
        sample_rate: Sample rate for successful requests (0.0-1.0, default 1.0)
        redact_headers: Headers to redact (e.g., ["authorization", "cookie"])
        wrap_lifespan: Existing lifespan context manager to wrap

    Returns:
        Async context manager for FastAPI lifespan parameter
    """
```

**Usage examples:**
```python
# Example 1: Simplest usage
from fapilog.fastapi import setup_logging

app = FastAPI(lifespan=setup_logging(preset="production"))

# Example 2: With middleware config
app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        skip_paths=["/health", "/metrics"],
        sample_rate=0.1,  # 10% sampling
        redact_headers=["authorization", "cookie"]
    )
)

# Example 3: Wrap existing lifespan
@asynccontextmanager
async def my_lifespan(app: FastAPI):
    # User's startup code
    print("Starting my services")
    yield
    # User's shutdown code
    print("Stopping my services")

app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        wrap_lifespan=my_lifespan  # Wraps user's lifespan
    )
)

# Example 4: Pass app for middleware auto-configuration
app = FastAPI()
lifespan = setup_logging(app, preset="production")  # Adds middleware to app
app.lifespan = lifespan  # Note: Must set before startup

# Example 5: No app, just lifespan (user adds middleware manually)
app = FastAPI(lifespan=setup_logging(preset="dev"))
app.add_middleware(RequestContextMiddleware)  # Manual
app.add_middleware(LoggingMiddleware)  # Manual
```

**Behavior:**
- Creates global async logger on startup using preset
- Stores logger in `app.state.fapilog_logger` for access
- If `app` provided, automatically adds middleware in correct order
- Drains logger on shutdown (waits for queue to flush)
- If `wrap_lifespan` provided, wraps user's lifespan (startup/shutdown)
- Propagates exceptions from user's lifespan

### AC2: get_request_logger Dependency

**Function signature:**
```python
async def get_request_logger(request: Request | None = None) -> AsyncLoggerFacade:
    """FastAPI dependency that provides request-scoped logger.

    Returns async logger with request context automatically bound from
    RequestContextMiddleware (request_id, user_id, trace_id, etc.).

    Context variables are set by RequestContextMiddleware and automatically
    included in all log entries.

    Args:
        request: FastAPI Request object (injected by Depends)

    Returns:
        AsyncLoggerFacade with request context bound

    Usage:
        from fapilog.fastapi import get_request_logger
        from fastapi import Depends

        @app.get("/users/{user_id}")
        async def get_user(
            user_id: int,
            logger = Depends(get_request_logger)
        ):
            await logger.info("Fetching user", user_id=user_id)
            # Logs: {
            #   "message": "Fetching user",
            #   "user_id": 123,
            #   "request_id": "abc-123",  # Auto-added by middleware
            #   "method": "GET",  # Auto-added
            #   "path": "/users/123"  # Auto-added
            # }
            return {"user_id": user_id}
    """
```

**Behavior:**
- Returns async logger (uses `get_async_logger("fastapi")` internally)
- Context (request_id, user_id, trace_id, span_id) automatically included via contextvars
- No manual binding needed (RequestContextMiddleware sets context)
- Can be used in routes, dependencies, background tasks
- Thread-safe and async-safe

**Auto-included context fields** (from RequestContextMiddleware):
- `request_id`: Generated UUID or from X-Request-ID header
- `user_id`: From X-User-ID header (if present)
- `tenant_id`: From X-Tenant-ID header (if present)
- `trace_id`: From traceparent header (if present)
- `span_id`: From traceparent header (if present)

### AC3: Automatic Middleware Registration

**When app is provided** to `setup_logging()`:

```python
app = FastAPI()
lifespan = setup_logging(app, preset="production")
# Middleware automatically added in correct order:
# 1. RequestContextMiddleware (sets request_id, etc.)
# 2. LoggingMiddleware (logs requests/responses)
```

**Middleware order is fixed** (for correctness):
1. `RequestContextMiddleware` - Sets context variables FIRST
2. `LoggingMiddleware` - Reads context variables SECOND

**Configuration pass-through:**
```python
lifespan = setup_logging(
    app,
    skip_paths=["/health"],      # → LoggingMiddleware.skip_paths
    sample_rate=0.1,              # → LoggingMiddleware.sample_rate
    redact_headers=["authorization"],  # → LoggingMiddleware.redact_headers
)
```

**If app is NOT provided**, user must add middleware manually:
```python
app = FastAPI(lifespan=setup_logging())  # No app = no middleware
# User adds middleware manually:
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

### AC4: Lifespan Wrapping

**User's existing lifespan is preserved and wrapped:**

```python
@asynccontextmanager
async def my_lifespan(app: FastAPI):
    # User's startup code runs FIRST
    db = await connect_database()
    app.state.db = db

    yield  # App runs

    # User's shutdown code runs LAST
    await db.close()

# Execution order:
# 1. fapilog startup (create logger)
# 2. my_lifespan startup (connect db)
# 3. App runs
# 4. my_lifespan shutdown (close db)
# 5. fapilog shutdown (drain logger)

app = FastAPI(
    lifespan=setup_logging(wrap_lifespan=my_lifespan)
)
```

**Execution order:**
1. Fapilog creates logger
2. User's lifespan startup code
3. Application runs
4. User's lifespan shutdown code
5. Fapilog drains logger

**Exception handling:**
- Exceptions in user's lifespan startup propagate (app won't start)
- Exceptions in user's lifespan shutdown propagate after logger drain
- Logger always drains even if user's shutdown fails

### AC5: Integration with Story 10.1 Presets

**Preset parameter uses Story 10.1 presets:**

```python
# Dev preset: DEBUG logging, pretty output (Story 10.2)
app = FastAPI(lifespan=setup_logging(preset="dev"))

# Production preset: INFO logging, file rotation, redaction
app = FastAPI(lifespan=setup_logging(preset="production"))

# FastAPI preset: Optimized for async, context propagation
app = FastAPI(lifespan=setup_logging(preset="fastapi"))

# Minimal preset: Stdout JSON only
app = FastAPI(lifespan=setup_logging(preset="minimal"))
```

**Preset configures the logger**, middleware config is separate:
```python
# Preset affects logger, middleware config is independent
app = FastAPI(
    lifespan=setup_logging(
        preset="production",     # Logger: INFO, file rotation, redaction
        sample_rate=0.1,          # Middleware: 10% sampling
        skip_paths=["/health"]    # Middleware: skip health checks
    )
)
```

### AC6: Logger Cleanup on Shutdown

**Logger automatically drained on shutdown:**

```python
# Startup:
# - Logger created
# - Logger stored in app.state.fapilog_logger

# Shutdown:
# - await logger.drain() called automatically
# - Waits for queue to flush (max 5 seconds)
# - Ensures no logs lost

# User doesn't need to handle cleanup
app = FastAPI(lifespan=setup_logging())
# Cleanup is automatic
```

**Drain timeout: 5 seconds** (configurable via Settings if needed)

**If drain times out:**
- Warning logged to stderr
- Shutdown continues (doesn't block app shutdown indefinitely)

### AC7: Before/After Code Reduction

**Before (current):**
```python
# 60+ lines of boilerplate

# 1. Lifespan manager
app_logger = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_logger
    app_logger = await get_async_logger("fastapi_app")
    await app_logger.info("Application starting up")
    yield
    if app_logger:
        await app_logger.info("Application shutting down")
        await app_logger.drain()

# 2. Middleware
from fapilog.fastapi import RequestContextMiddleware, LoggingMiddleware

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    LoggingMiddleware,
    skip_paths=["/health"],
    sample_rate=1.0,
    redact_headers=["authorization"]
)

# 3. Logger dependency
async def get_request_logger(request: Request) -> Any:
    logger = await get_async_logger("request")
    bound_logger = logger.bind(
        request_id=request.headers.get("X-Request-ID", "unknown"),
        user_agent=request.headers.get("User-Agent", "unknown"),
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "unknown",
    )
    return bound_logger

# 4. Routes
@app.get("/")
async def root(logger: Any = Depends(get_request_logger)):
    await logger.info("Root endpoint accessed")
    return {"message": "Hello World"}
```

**After (with Story 10.3):**
```python
# 2 lines of setup

from fapilog.fastapi import setup_logging, get_request_logger
from fastapi import FastAPI, Depends

app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        skip_paths=["/health"],
        sample_rate=1.0,
        redact_headers=["authorization"]
    )
)

@app.get("/")
async def root(logger = Depends(get_request_logger)):
    await logger.info("Root endpoint accessed")
    return {"message": "Hello World"}
```

**Line reduction: 60+ lines → 2 lines setup (97% reduction)**

### AC8: Documentation & Examples

**Documentation updated:**
- `README.md`: Add FastAPI one-liner example in Quick Start
- `docs/integrations/fastapi.md`: Comprehensive FastAPI guide
- `docs/user-guide/configuration.md`: Document setup_logging()
- `examples/fastapi_one_liner/`: New example showing minimal setup

**Examples include:**
- Basic setup with preset
- Setup with middleware config
- Wrapping existing lifespan
- Using logger dependency in routes
- Error handling and exceptions
- Background tasks with logger

## API Design Decision

### Problem Statement

How should `setup_logging()` integrate with FastAPI's lifespan manager, given that:
1. Lifespan is set at `FastAPI()` construction time
2. User may have existing lifespan code
3. Logger needs startup (create) and shutdown (drain) hooks
4. Middleware needs to be added in correct order

### Options Considered

**Option A: setup_logging() modifies app post-construction** ❌
```python
app = FastAPI()
setup_logging(app)  # Tries to set lifespan after construction
```

**Pros:**
- Simple API

**Cons:**
- ❌ Can't modify lifespan after FastAPI construction
- ❌ Would require monkey-patching
- ❌ Fragile, breaks with FastAPI updates

---

**Option B: setup_logging() returns lifespan (CHOSEN)** ✅
```python
app = FastAPI(lifespan=setup_logging(preset="production"))
```

**Pros:**
- ✅ Works with FastAPI's design (lifespan at construction)
- ✅ Explicit and clear
- ✅ Can wrap user's lifespan
- ✅ Type-safe
- ✅ Composable

**Cons:**
- ❌ Slightly less "magical" (user sees lifespan parameter)

---

**Option C: Decorator pattern** ❌
```python
@setup_logging(preset="production")
class MyApp(FastAPI):
    pass

app = MyApp()
```

**Pros:**
- ✅ Looks clean

**Cons:**
- ❌ Non-standard for FastAPI
- ❌ Harder to understand
- ❌ Can't wrap existing lifespan easily
- ❌ Breaks FastAPI's app = FastAPI() idiom

---

### Decision: Option B (Return Lifespan)

**Rationale:**
1. **Works with FastAPI's design**: Lifespan must be set at construction
2. **Explicit > Implicit**: Clear what's happening (not magic)
3. **Composable**: Can wrap user's lifespan with `wrap_lifespan` parameter
4. **Type-safe**: Returns proper async context manager type
5. **Flexible**: Can optionally configure app middleware too
6. **Precedent**: Similar to Starlette lifespan pattern

**Implementation pattern:**
```python
@asynccontextmanager
async def setup_logging(...):
    # Startup
    logger = await get_async_logger(...)
    app.state.fapilog_logger = logger

    # Wrap user's lifespan if provided
    if wrap_lifespan:
        async with wrap_lifespan(app):
            yield
    else:
        yield

    # Shutdown
    await logger.drain(timeout=5.0)
```

**User experience:**
```python
# Simple: One line
app = FastAPI(lifespan=setup_logging())

# With config: Still one line (multi-line for readability)
app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        skip_paths=["/health"]
    )
)

# With user's lifespan: Explicit wrapping
app = FastAPI(
    lifespan=setup_logging(wrap_lifespan=my_lifespan)
)
```

### Middleware Configuration Strategy

**Decision: Pass app optionally, auto-configure middleware**

```python
# If app provided, configure middleware
app = FastAPI()
lifespan = setup_logging(app, preset="production")  # Adds middleware

# If app NOT provided, user adds middleware manually
app = FastAPI(lifespan=setup_logging())  # No middleware
app.add_middleware(RequestContextMiddleware)
app.add_middleware(LoggingMiddleware)
```

**Rationale:**
- Flexible: User can control middleware if needed
- Simple: One-liner still possible
- Explicit: Clear when middleware is configured

### Logger Dependency Strategy

**Decision: Simple async function, uses contextvars**

```python
async def get_request_logger(request: Request | None = None):
    """Get logger with auto-bound request context."""
    # Get global logger from app state
    # Context already set by RequestContextMiddleware via contextvars
    logger = await get_async_logger("fastapi")
    return logger
```

**Rationale:**
- **Simple**: No classes, no complex dependency injection
- **Automatic**: Context from middleware via contextvars (no manual binding)
- **Familiar**: Standard FastAPI dependency pattern
- **Efficient**: No per-request logger creation overhead

## Implementation Notes

### File Structure

```
src/fapilog/fastapi/setup.py (NEW)
src/fapilog/fastapi/dependencies.py (NEW)
src/fapilog/fastapi/__init__.py (MODIFIED - export new functions)
tests/integration/test_fastapi_setup.py (NEW)
examples/fastapi_one_liner/ (NEW)
docs/integrations/fastapi.md (NEW)
```

### Implementation Steps

#### Step 1: Create `setup_logging()` Function

**File**: `src/fapilog/fastapi/setup.py`

```python
"""FastAPI integration helpers for one-liner setup."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore


@asynccontextmanager
async def setup_logging(
    app: FastAPI | None = None,
    *,
    preset: str | None = None,
    skip_paths: list[str] | None = None,
    sample_rate: float = 1.0,
    redact_headers: list[str] | None = None,
    wrap_lifespan: Callable[[FastAPI], AsyncIterator[None]] | None = None,
) -> AsyncIterator[None]:
    """One-liner FastAPI logging setup.

    Returns async context manager (lifespan) that:
    - Creates async logger on startup
    - Optionally adds middleware if app provided
    - Drains logger on shutdown
    - Wraps user's lifespan if provided

    Args:
        app: FastAPI app instance (optional, for middleware configuration)
        preset: Logger preset (dev, production, fastapi, minimal)
        skip_paths: Paths to skip logging (e.g., ["/health", "/metrics"])
        sample_rate: Sample rate for successful requests (0.0-1.0)
        redact_headers: Headers to redact (e.g., ["authorization"])
        wrap_lifespan: Existing lifespan context manager to wrap

    Returns:
        Async context manager for FastAPI lifespan parameter

    Example:
        from fapilog.fastapi import setup_logging
        from fastapi import FastAPI

        # Simple usage
        app = FastAPI(lifespan=setup_logging(preset="production"))

        # With middleware config
        app = FastAPI(
            lifespan=setup_logging(
                preset="production",
                skip_paths=["/health"],
                sample_rate=0.1
            )
        )

        # Wrap existing lifespan
        @asynccontextmanager
        async def my_lifespan(app):
            print("Starting")
            yield
            print("Stopping")

        app = FastAPI(
            lifespan=setup_logging(wrap_lifespan=my_lifespan)
        )
    """
    from .. import get_async_logger

    # Startup: Create logger
    logger = await get_async_logger("fastapi", preset=preset)

    # Store logger in app state if app provided
    if app is not None:
        app.state.fapilog_logger = logger

        # Configure middleware if app provided
        _configure_middleware(
            app,
            skip_paths=skip_paths,
            sample_rate=sample_rate,
            redact_headers=redact_headers,
        )

    # Wrap user's lifespan if provided
    if wrap_lifespan is not None:
        try:
            async with wrap_lifespan(app):
                yield
        finally:
            # Shutdown: Drain logger
            await _drain_logger(logger)
    else:
        try:
            yield
        finally:
            # Shutdown: Drain logger
            await _drain_logger(logger)


def _configure_middleware(
    app: FastAPI,
    *,
    skip_paths: list[str] | None = None,
    sample_rate: float = 1.0,
    redact_headers: list[str] | None = None,
) -> None:
    """Configure middleware on FastAPI app.

    Adds middleware in correct order:
    1. RequestContextMiddleware (sets context vars)
    2. LoggingMiddleware (reads context vars)
    """
    from .context import RequestContextMiddleware
    from .logging import LoggingMiddleware

    # Get logger from app state (set by setup_logging)
    logger = getattr(app.state, "fapilog_logger", None)

    # Order matters: Context BEFORE Logging
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        LoggingMiddleware,
        logger=logger,
        skip_paths=skip_paths,
        sample_rate=sample_rate,
        redact_headers=redact_headers,
    )


async def _drain_logger(logger, timeout: float = 5.0) -> None:
    """Drain logger with timeout.

    Args:
        logger: Logger instance to drain
        timeout: Max seconds to wait for drain
    """
    import asyncio

    try:
        await asyncio.wait_for(logger.drain(), timeout=timeout)
    except asyncio.TimeoutError:
        import sys

        sys.stderr.write(
            f"[fapilog] Warning: Logger drain timed out after {timeout}s\n"
        )
    except Exception as e:
        import sys

        sys.stderr.write(f"[fapilog] Warning: Logger drain error: {e}\n")
```

#### Step 2: Create `get_request_logger` Dependency

**File**: `src/fapilog/fastapi/dependencies.py`

```python
"""FastAPI dependencies for logging."""

from __future__ import annotations

try:
    from starlette.requests import Request
except ImportError:  # pragma: no cover
    Request = None  # type: ignore


async def get_request_logger(request: Request | None = None):
    """FastAPI dependency that provides request-scoped logger.

    Returns async logger with request context automatically bound from
    RequestContextMiddleware (request_id, user_id, trace_id, etc.).

    Context variables are set by RequestContextMiddleware and automatically
    included in all log entries via the context_vars enricher.

    Args:
        request: FastAPI Request object (injected by Depends, optional)

    Returns:
        AsyncLoggerFacade with request context bound

    Example:
        from fapilog.fastapi import get_request_logger
        from fastapi import Depends

        @app.get("/users/{user_id}")
        async def get_user(
            user_id: int,
            logger = Depends(get_request_logger)
        ):
            await logger.info("Fetching user", user_id=user_id)
            # Auto-includes: request_id, method, path, etc.
            return {"user_id": user_id}

    Auto-included context fields (from RequestContextMiddleware):
        - request_id: Generated UUID or from X-Request-ID header
        - user_id: From X-User-ID header (if present)
        - tenant_id: From X-Tenant-ID header (if present)
        - trace_id: From traceparent header (if present)
        - span_id: From traceparent header (if present)
    """
    from .. import get_async_logger

    # Get logger (context already set by RequestContextMiddleware)
    logger = await get_async_logger("fastapi")

    return logger
```

#### Step 3: Update Exports

**File**: `src/fapilog/fastapi/__init__.py`

```python
"""FastAPI integration for fapilog."""

from __future__ import annotations

AVAILABLE: bool
_IMPORT_ERROR: Exception | None

try:
    from .context import RequestContextMiddleware
    from .dependencies import get_request_logger  # NEW
    from .integration import get_router
    from .logging import LoggingMiddleware
    from .setup import setup_logging  # NEW

    AVAILABLE = True
    _IMPORT_ERROR = None
except Exception as e:  # pragma: no cover
    AVAILABLE = False
    _IMPORT_ERROR = e
    # Stub exports for type checkers
    RequestContextMiddleware = None  # type: ignore
    LoggingMiddleware = None  # type: ignore
    get_router = None  # type: ignore
    setup_logging = None  # type: ignore
    get_request_logger = None  # type: ignore

__all__ = [
    "AVAILABLE",
    "RequestContextMiddleware",
    "LoggingMiddleware",
    "get_router",
    "setup_logging",  # NEW
    "get_request_logger",  # NEW
]
```

#### Step 4: Integration with Story 10.1 Presets

**Modify**: `src/fapilog/__init__.py`

```python
# Update get_async_logger to accept preset parameter
async def get_async_logger(
    name: str | None = None,
    *,
    preset: str | None = None,  # NEW - forward from setup_logging
    format: Literal["json", "pretty", "auto"] | None = "auto",
    settings: _Settings | None = None,
    sinks: list[object] | None = None,
) -> _AsyncLoggerFacade:
    """Get async logger.

    Args:
        name: Logger name
        preset: Configuration preset (passed through from setup_logging)
        format: Output format
        settings: Full Settings object
        sinks: Custom sink instances
    """
    # Apply preset if provided
    if preset is not None:
        from .core.presets import get_preset
        preset_config = get_preset(preset)
        settings = _Settings(**preset_config)

    # ... rest of function unchanged
```

### Middleware Ordering

**Critical: Order matters for context propagation**

```python
# Correct order:
app.add_middleware(RequestContextMiddleware)  # Sets request_id FIRST
app.add_middleware(LoggingMiddleware)         # Reads request_id SECOND

# Wrong order would break context propagation:
# LoggingMiddleware wouldn't see request_id set by RequestContextMiddleware
```

**Enforced in `_configure_middleware()`** - users can't get order wrong.

### Exception Handling

```python
@asynccontextmanager
async def setup_logging(...):
    logger = await get_async_logger(...)

    try:
        # Wrap user's lifespan
        if wrap_lifespan:
            async with wrap_lifespan(app):
                yield
        else:
            yield
    finally:
        # ALWAYS drain logger, even if user's lifespan fails
        await _drain_logger(logger, timeout=5.0)
```

**Behavior**:
- User's lifespan exceptions propagate (app won't start/stop)
- Logger always drained (no lost logs)
- Drain timeout prevents hanging shutdown

## Tasks

### Phase 1: Core Implementation

- [ ] Create `src/fapilog/fastapi/setup.py` module
- [ ] Implement `setup_logging()` async context manager
- [ ] Implement lifespan wrapping logic
- [ ] Implement `_configure_middleware()` helper
- [ ] Implement `_drain_logger()` with timeout
- [ ] Create `src/fapilog/fastapi/dependencies.py` module
- [ ] Implement `get_request_logger()` dependency
- [ ] Update `src/fapilog/fastapi/__init__.py` exports
- [ ] Add `preset` parameter to `get_async_logger()` (integration with Story 10.1)

### Phase 2: Testing

- [ ] Create `tests/integration/test_fastapi_setup.py`
- [ ] Test: `setup_logging()` creates logger on startup
- [ ] Test: `setup_logging()` drains logger on shutdown
- [ ] Test: `setup_logging()` wraps user's lifespan correctly
- [ ] Test: `setup_logging()` with app configures middleware
- [ ] Test: `setup_logging()` without app does NOT configure middleware
- [ ] Test: Middleware ordering is correct (RequestContext before Logging)
- [ ] Test: `get_request_logger()` returns logger with context
- [ ] Test: Request context auto-included (request_id, etc.)
- [ ] Test: Preset integration works (dev, production, fastapi, minimal)
- [ ] Test: Configuration pass-through (skip_paths, sample_rate, redact_headers)
- [ ] Test: Drain timeout works (doesn't hang shutdown)
- [ ] Test: Exceptions in user's lifespan propagate
- [ ] Test: Logger drains even if user's lifespan fails

### Phase 3: Documentation & Examples

- [ ] Update `README.md` - add FastAPI one-liner to Quick Start
- [ ] Create `docs/integrations/fastapi.md` - comprehensive guide
- [ ] Update `docs/user-guide/configuration.md` - document setup_logging()
- [ ] Create `examples/fastapi_one_liner/main.py` - basic example
- [ ] Create `examples/fastapi_one_liner/with_lifespan.py` - wrapping example
- [ ] Create `examples/fastapi_one_liner/with_config.py` - configuration example
- [ ] Add before/after comparison to docs
- [ ] Update `CHANGELOG.md`

### Phase 4: Integration with Stories 10.1 & 10.2

- [ ] Test: `preset="dev"` uses pretty output (Story 10.2)
- [ ] Test: `preset="production"` uses JSON with file rotation (Story 10.1)
- [ ] Test: `preset="fastapi"` optimized for async (Story 10.1)
- [ ] Verify: Dev preset with setup_logging shows colored output in terminal
- [ ] Verify: Production preset with setup_logging creates log files

## Tests

### Integration Tests (`tests/integration/test_fastapi_setup.py`)

```python
"""Integration tests for FastAPI one-liner setup."""

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from fapilog.fastapi import get_request_logger, setup_logging


class TestSetupLoggingBasic:
    """Test basic setup_logging functionality."""

    def test_setup_logging_creates_logger_on_startup(self):
        """setup_logging creates logger on app startup."""
        startup_called = False
        shutdown_called = False

        app = FastAPI(lifespan=setup_logging())

        with TestClient(app) as client:
            # Logger should be created
            assert hasattr(app.state, "fapilog_logger")
            assert app.state.fapilog_logger is not None

        # After shutdown, logger should be drained

    def test_setup_logging_with_preset(self):
        """setup_logging accepts preset parameter."""
        app = FastAPI(lifespan=setup_logging(preset="dev"))

        with TestClient(app):
            logger = app.state.fapilog_logger
            assert logger is not None
            # TODO: Verify logger uses dev preset config

    def test_setup_logging_without_app(self):
        """setup_logging without app works but doesn't add middleware."""
        app = FastAPI(lifespan=setup_logging())

        # Middleware count should be 0 (none auto-added)
        middleware_count = len(app.user_middleware)
        assert middleware_count == 0


class TestLifespanWrapping:
    """Test wrapping user's existing lifespan."""

    def test_wraps_user_lifespan(self):
        """setup_logging wraps user's lifespan correctly."""
        events = []

        @asynccontextmanager
        async def my_lifespan(app):
            events.append("user_startup")
            yield
            events.append("user_shutdown")

        app = FastAPI(
            lifespan=setup_logging(wrap_lifespan=my_lifespan)
        )

        with TestClient(app):
            # During app run
            assert "user_startup" in events
            assert "user_shutdown" not in events

        # After shutdown
        assert "user_startup" in events
        assert "user_shutdown" in events

    def test_execution_order_with_wrapped_lifespan(self):
        """Execution order: fapilog startup, user startup, user shutdown, fapilog shutdown."""
        events = []

        @asynccontextmanager
        async def my_lifespan(app):
            # Check logger exists (fapilog startup ran first)
            assert hasattr(app.state, "fapilog_logger")
            events.append("user_startup")
            yield
            events.append("user_shutdown")
            # Logger still exists (fapilog shutdown runs after)
            assert hasattr(app.state, "fapilog_logger")

        app = FastAPI(lifespan=setup_logging(wrap_lifespan=my_lifespan))

        with TestClient(app):
            pass

        assert events == ["user_startup", "user_shutdown"]

    def test_user_lifespan_exception_propagates(self):
        """Exceptions in user's lifespan startup propagate."""

        @asynccontextmanager
        async def failing_lifespan(app):
            raise ValueError("Startup failed")
            yield

        app = FastAPI(
            lifespan=setup_logging(wrap_lifespan=failing_lifespan)
        )

        # Should raise during client creation (startup)
        with pytest.raises(ValueError, match="Startup failed"):
            with TestClient(app):
                pass


class TestMiddlewareConfiguration:
    """Test automatic middleware configuration."""

    def test_middleware_added_when_app_provided(self):
        """Middleware automatically added when app provided."""
        app = FastAPI()
        lifespan = setup_logging(app, preset="production")
        app.lifespan_context = lifespan

        # Check middleware was added
        # Note: Middleware stack inspection is tricky, this is simplified
        middleware_names = [m.__class__.__name__ for m in app.user_middleware]

        assert "RequestContextMiddleware" in str(middleware_names)
        assert "LoggingMiddleware" in str(middleware_names)

    def test_middleware_ordering(self):
        """RequestContextMiddleware added before LoggingMiddleware."""
        app = FastAPI()
        setup_logging(app)

        # Get middleware stack
        middleware_stack = [m.__class__.__name__ for m in app.user_middleware]

        # Find indices
        context_idx = next(
            i for i, name in enumerate(middleware_stack)
            if "RequestContext" in name
        )
        logging_idx = next(
            i for i, name in enumerate(middleware_stack)
            if "Logging" in name
        )

        # RequestContext should come before Logging
        assert context_idx < logging_idx

    def test_middleware_config_passthrough(self):
        """Configuration passed through to middleware."""
        app = FastAPI()

        setup_logging(
            app,
            skip_paths=["/health", "/metrics"],
            sample_rate=0.5,
            redact_headers=["authorization", "cookie"],
        )

        # Find LoggingMiddleware instance
        logging_middleware = next(
            m for m in app.user_middleware
            if "Logging" in m.__class__.__name__
        )

        # Verify config
        assert logging_middleware._skip_paths == {"/health", "/metrics"}
        assert logging_middleware._sample_rate == 0.5
        assert "authorization" in logging_middleware._redact_headers


class TestGetRequestLogger:
    """Test get_request_logger dependency."""

    @pytest.mark.asyncio
    async def test_get_request_logger_returns_logger(self):
        """get_request_logger returns AsyncLoggerFacade."""
        app = FastAPI(lifespan=setup_logging())

        @app.get("/")
        async def root(logger=Depends(get_request_logger)):
            assert logger is not None
            await logger.info("Test")
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_context_auto_included(self):
        """Request context automatically included from middleware."""
        app = FastAPI(lifespan=setup_logging(app))

        captured_logs = []

        @app.get("/test")
        async def test_endpoint(logger=Depends(get_request_logger)):
            # Log should auto-include request_id from middleware
            await logger.info("Test message")
            # TODO: Capture log output and verify request_id present
            return {"status": "ok"}

        with TestClient(app) as client:
            response = client.get(
                "/test",
                headers={"X-Request-ID": "test-123"}
            )
            assert response.status_code == 200
            # TODO: Verify request_id="test-123" in logs


class TestPresetIntegration:
    """Test integration with Story 10.1 presets."""

    def test_dev_preset(self):
        """Dev preset configures logger for development."""
        app = FastAPI(lifespan=setup_logging(preset="dev"))

        with TestClient(app):
            logger = app.state.fapilog_logger
            # TODO: Verify logger uses dev preset (DEBUG level, pretty output)

    def test_production_preset(self):
        """Production preset configures logger for production."""
        app = FastAPI(lifespan=setup_logging(preset="production"))

        with TestClient(app):
            logger = app.state.fapilog_logger
            # TODO: Verify logger uses production preset (INFO, file rotation)

    def test_fastapi_preset(self):
        """FastAPI preset optimized for async operations."""
        app = FastAPI(lifespan=setup_logging(preset="fastapi"))

        with TestClient(app):
            logger = app.state.fapilog_logger
            # TODO: Verify logger uses fastapi preset


class TestLoggerDrain:
    """Test logger cleanup on shutdown."""

    @pytest.mark.asyncio
    async def test_logger_drained_on_shutdown(self):
        """Logger drained on app shutdown."""
        app = FastAPI(lifespan=setup_logging())

        with TestClient(app) as client:
            # Log something
            await app.state.fapilog_logger.info("Test")

        # After shutdown, queue should be drained
        # TODO: Verify drain was called

    @pytest.mark.asyncio
    async def test_drain_timeout(self):
        """Drain timeout prevents hanging shutdown."""
        # TODO: Test drain timeout behavior
        # Mock a slow drain and verify timeout works


class TestBeforeAfterComparison:
    """Test demonstrating line reduction."""

    def test_before_requires_60_plus_lines(self):
        """Before Story 10.3: 60+ lines of boilerplate."""
        # This test documents the old way (for comparison)

        # 1. Manual lifespan (20 lines)
        app_logger = None

        @asynccontextmanager
        async def lifespan(app):
            nonlocal app_logger
            from fapilog import get_async_logger

            app_logger = await get_async_logger("fastapi_app")
            await app_logger.info("Starting")
            yield
            if app_logger:
                await app_logger.info("Stopping")
                await app_logger.drain()

        # 2. Manual middleware (6 lines)
        from fapilog.fastapi import LoggingMiddleware, RequestContextMiddleware

        app = FastAPI(lifespan=lifespan)
        app.add_middleware(RequestContextMiddleware)
        app.add_middleware(LoggingMiddleware, skip_paths=["/health"])

        # 3. Manual logger dependency (15 lines)
        from starlette.requests import Request

        async def get_logger_dep(request: Request):
            from fapilog import get_async_logger

            logger = await get_async_logger("request")
            return logger.bind(
                request_id=request.headers.get("X-Request-ID", "unknown"),
                method=request.method,
                path=request.url.path,
            )

        # 4. Route (3 lines)
        @app.get("/")
        async def root(logger=Depends(get_logger_dep)):
            await logger.info("Request")
            return {"status": "ok"}

        # Total: ~60+ lines

    def test_after_requires_2_lines(self):
        """After Story 10.3: 2 lines of setup."""
        from fapilog.fastapi import get_request_logger, setup_logging

        # 1 line setup
        app = FastAPI(lifespan=setup_logging(preset="production"))

        # Route (3 lines - same as before)
        @app.get("/")
        async def root(logger=Depends(get_request_logger)):
            await logger.info("Request")
            return {"status": "ok"}

        # Total: 2 lines setup + routes (97% reduction)
```

### Unit Tests

```python
"""Unit tests for setup helpers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fapilog.fastapi.setup import _configure_middleware, _drain_logger


class TestConfigureMiddleware:
    """Test _configure_middleware helper."""

    def test_adds_middleware_in_correct_order(self):
        """Middleware added in correct order."""
        app = MagicMock()
        app.state.fapilog_logger = MagicMock()

        _configure_middleware(app)

        # Verify add_middleware called twice
        assert app.add_middleware.call_count == 2

        # Verify RequestContextMiddleware added first
        first_call = app.add_middleware.call_args_list[0]
        assert "RequestContextMiddleware" in str(first_call)

    def test_passes_config_to_logging_middleware(self):
        """Config passed to LoggingMiddleware."""
        app = MagicMock()
        app.state.fapilog_logger = MagicMock()

        _configure_middleware(
            app,
            skip_paths=["/health"],
            sample_rate=0.5,
            redact_headers=["auth"],
        )

        # Find LoggingMiddleware call
        calls = app.add_middleware.call_args_list
        logging_call = calls[1]  # Second call

        # Verify kwargs passed
        assert logging_call.kwargs["skip_paths"] == ["/health"]
        assert logging_call.kwargs["sample_rate"] == 0.5
        assert logging_call.kwargs["redact_headers"] == ["auth"]


class TestDrainLogger:
    """Test _drain_logger helper."""

    @pytest.mark.asyncio
    async def test_drains_logger(self):
        """Calls logger.drain()."""
        logger = AsyncMock()
        logger.drain = AsyncMock()

        await _drain_logger(logger)

        logger.drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_on_slow_drain(self):
        """Timeout if drain takes too long."""
        import asyncio

        logger = AsyncMock()

        async def slow_drain():
            await asyncio.sleep(10)  # Simulate slow drain

        logger.drain = slow_drain

        # Should timeout after 0.1 seconds
        await _drain_logger(logger, timeout=0.1)

        # Should not raise, just warn to stderr

    @pytest.mark.asyncio
    async def test_handles_drain_errors(self):
        """Handles errors during drain gracefully."""
        logger = AsyncMock()
        logger.drain = AsyncMock(side_effect=Exception("Drain failed"))

        # Should not raise, just warn
        await _drain_logger(logger)
```

## Definition of Done

### Code Complete
- [ ] `setup_logging()` function implemented in `setup.py`
- [ ] Lifespan wrapping logic working
- [ ] `_configure_middleware()` helper implemented
- [ ] `_drain_logger()` with timeout implemented
- [ ] `get_request_logger()` dependency implemented in `dependencies.py`
- [ ] Exports updated in `__init__.py`
- [ ] `preset` parameter added to `get_async_logger()`
- [ ] Middleware ordering enforced (RequestContext before Logging)

### Quality Assurance
- [ ] Integration tests: >95% coverage of new code
- [ ] Test: setup_logging creates logger on startup
- [ ] Test: setup_logging drains logger on shutdown
- [ ] Test: Lifespan wrapping works correctly
- [ ] Test: Middleware auto-configured when app provided
- [ ] Test: Middleware NOT configured when app not provided
- [ ] Test: Middleware ordering correct
- [ ] Test: get_request_logger returns logger with context
- [ ] Test: Request context auto-included
- [ ] Test: All 4 presets work (dev, production, fastapi, minimal)
- [ ] Test: Configuration pass-through works
- [ ] Test: Drain timeout works
- [ ] Test: Exceptions in user's lifespan propagate
- [ ] Test: Logger drains even if user's lifespan fails
- [ ] No regression in existing FastAPI tests

### Documentation
- [ ] `README.md` updated with one-liner example
- [ ] `docs/integrations/fastapi.md` created (comprehensive guide)
- [ ] `docs/user-guide/configuration.md` updated
- [ ] Before/after comparison in docs
- [ ] `examples/fastapi_one_liner/main.py` created
- [ ] `examples/fastapi_one_liner/with_lifespan.py` created
- [ ] `examples/fastapi_one_liner/with_config.py` created
- [ ] `CHANGELOG.md` updated
- [ ] API docstrings complete

### Integration with Other Stories
- [ ] Story 10.1: Presets work with setup_logging
- [ ] Story 10.2: Dev preset shows pretty output
- [ ] Verify: `preset="dev"` + terminal = colored output
- [ ] Verify: `preset="production"` = JSON + file rotation
- [ ] Verify: `preset="fastapi"` optimized for async

### Review & Release
- [ ] Code review approved
- [ ] Documentation reviewed
- [ ] CI/CD pipeline passing
- [ ] No performance regression
- [ ] Ready for merge

## Risks / Rollback / Monitoring

### Risks

1. **Risk**: Users have complex existing lifespans that can't be wrapped
   - **Mitigation**: `wrap_lifespan` parameter handles most cases
   - **Mitigation**: Users can still use old manual approach
   - **Mitigation**: Documentation shows how to integrate both

2. **Risk**: Middleware ordering breaks with user's custom middleware
   - **Mitigation**: Document middleware order requirements
   - **Mitigation**: Fixed order enforced (can't be wrong)
   - **Mitigation**: If conflicts, user can add middleware manually

3. **Risk**: Logger drain timeout causes issues
   - **Mitigation**: 5 second timeout is generous
   - **Mitigation**: Timeout configurable via Settings if needed
   - **Mitigation**: Warning logged but shutdown continues

4. **Risk**: Breaking changes to existing manual setup users
   - **Mitigation**: Zero breaking changes - old approach still works
   - **Mitigation**: New approach is purely additive
   - **Mitigation**: Migration is optional

5. **Risk**: Preset integration doesn't work as expected
   - **Mitigation**: Comprehensive preset integration tests
   - **Mitigation**: Clear documentation on preset + middleware config

### Rollback Plan

If one-liner setup causes issues:

1. **Easy rollback**: Remove from docs, mark as experimental
   ```python
   # Old manual approach still works
   app = FastAPI(lifespan=my_lifespan)
   app.add_middleware(RequestContextMiddleware)
   app.add_middleware(LoggingMiddleware)
   ```

2. **Keep feature available**: Document limitations clearly
   - Works for 90% of use cases
   - Complex lifespans may need manual approach

3. **Full removal**: Delete `setup.py` and `dependencies.py`
   - Minimal code churn (2 new files)
   - No impact on existing middleware classes

### Success Metrics

**Quantitative:**
- [ ] Line reduction: 60+ → 2 lines (97% reduction)
- [ ] Adoption: >50% of new FastAPI integrations use setup_logging
- [ ] Error rate: No increase in FastAPI integration errors

**Qualitative:**
- [ ] Developer feedback: "Much easier to set up than before"
- [ ] GitHub issues: No complaints about setup_logging
- [ ] Documentation: Clear examples reduce questions

### Monitoring

- Track setup_logging adoption (if telemetry added)
- Monitor GitHub issues for FastAPI integration problems
- Collect user feedback on one-liner setup
- Watch for lifespan wrapping edge cases

## Dependencies

- **Depends on**: Story 10.1 (Configuration Presets) - preset parameter
- **Related to**: Story 10.2 (Pretty Console) - dev preset uses pretty output
- **Blocks**: None
- **Enhances**: Existing FastAPI middleware (RequestContext, Logging)

## Estimated Effort

- **Implementation**: 8 hours
  - setup_logging() function: 3 hours
  - get_request_logger dependency: 1 hour
  - Lifespan wrapping: 2 hours
  - Middleware configuration: 2 hours

- **Testing**: 4 hours
  - Integration tests: 3 hours
  - Unit tests: 1 hour

- **Documentation**: 2 hours
  - Docs updates: 1 hour
  - Examples: 1 hour

- **Total**: 12-14 hours for one developer

## Related Stories

- **Story 10.1**: Configuration Presets (preset parameter integration)
- **Story 10.2**: Pretty Console Output (dev preset enhancement)
- **Story 10.4+**: Request/Response Body Logging (future enhancement)
- **Future**: Background task logging helper
- **Future**: WebSocket connection logging

## Change Log

| Date       | Change                                    | Author |
| ---------- | ----------------------------------------- | ------ |
| 2025-01-11 | Initial story creation (implementation-ready) | Claude |
