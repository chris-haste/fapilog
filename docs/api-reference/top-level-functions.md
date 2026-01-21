# Top-Level Functions

Main entry points and utilities for fapilog.

## get_logger (sync) {#get_logger}

```python
def get_logger(
    name: str | None = None,
    *,
    preset: str | None = None,
    format: Literal["json", "pretty", "auto"] | None = None,
    settings: _Settings | None = None,
    reuse: bool = True,
) -> _SyncLoggerFacade
```

Return a ready-to-use **synchronous** logger facade wired to a container-scoped pipeline. Methods like `info()` and `error()` are synchronous (no `await`).

### Parameters

| Parameter  | Type                | Default | Description                                                    |
| ---------- | ------------------- | ------- | -------------------------------------------------------------- |
| `name`     | `str \| None`       | `None`  | Logger name for identification. If None, uses the module name. |
| `preset`   | `str \| None`       | `None`  | Built-in preset (`dev`, `production`, `fastapi`, `minimal`).   |
| `format`   | `Literal[...]`      | `None`  | Output format: `json`, `pretty`, `auto` (pretty in TTY).        |
| `settings` | `_Settings \| None` | `None`  | Custom settings. If None, uses environment variables.          |
| `reuse`    | `bool`              | `True`  | If True, return cached instance for the same name. If False, create a new independent instance. |

### Returns

`_SyncLoggerFacade` - A logger instance ready for use (cached by name when `reuse=True`).

### Examples

```python
from fapilog import get_logger
import asyncio

# Zero-config usage (uses environment variables)
logger = get_logger()
logger.info("Application started")

# With custom name for better identification
service_logger = get_logger("user_service")
service_logger.info("User authentication successful")

# With custom settings
from fapilog import Settings
settings = Settings(core__enable_metrics=True)
logger = get_logger(settings=settings)
logger.info("Metrics-enabled logger ready")

# Force pretty output
logger = get_logger(format="pretty")
logger.info("Readable output", request_id="abc-123")

# Manual cleanup if you are not using runtime()
asyncio.run(logger.stop_and_drain())
```

### Environment Variables

The following environment variables are automatically read:

- `FAPILOG_CORE__LOG_LEVEL` - Log level hint (default: INFO)
- `FAPILOG_FILE__DIRECTORY` - File sink directory (if set, enables file logging)
- `FAPILOG_CORE__ENABLE_METRICS` - Enable metrics collection (default: false)

### Notes

- Sync API surface: `debug`, `info`, `warning`, `error`, `exception`, `bind`, `unbind`, `clear_context`
- Worker lifecycle is managed automatically; call `logger.stop_and_drain()` if you need explicit shutdown.
- Automatic sink selection: pretty in TTY, JSON when piped; file/http sink when configured via settings/env.
- `preset` and `settings` are mutually exclusive; `format` and `settings` are mutually exclusive.
- When `settings` is omitted, the default `format` behavior is `auto`.
- **Caching**: By default, loggers are cached by name. Calling `get_logger("foo")` multiple times returns the same instance. Use `reuse=False` for independent instances (e.g., in tests).

## get_async_logger (async) {#get_async_logger}

```python
async def get_async_logger(
    name: str | None = None,
    *,
    preset: str | None = None,
    format: Literal["json", "pretty", "auto"] | None = None,
    settings: _Settings | None = None,
    reuse: bool = True,
) -> _AsyncLoggerFacade
```

Return a ready-to-use **async** logger facade with awaitable methods.

### Parameters

| Parameter  | Type                | Default | Description                                                    |
| ---------- | ------------------- | ------- | -------------------------------------------------------------- |
| `name`     | `str \| None`       | `None`  | Logger name for identification. If None, uses the module name. |
| `preset`   | `str \| None`       | `None`  | Built-in preset (`dev`, `production`, `fastapi`, `minimal`).   |
| `format`   | `Literal[...]`      | `None`  | Output format: `json`, `pretty`, `auto` (pretty in TTY).        |
| `settings` | `_Settings \| None` | `None`  | Custom settings. If None, uses environment variables.          |
| `reuse`    | `bool`              | `True`  | If True, return cached instance for the same name. If False, create a new independent instance. |

### Returns

`_AsyncLoggerFacade` - A logger instance with awaitable methods (cached by name when `reuse=True`).

### Examples

```python
from fapilog import get_async_logger

logger = await get_async_logger("request")
await logger.info("Application started")
await logger.debug("Detailed event", request_id="req-1")
await logger.error("Something went wrong", exc_info=True)
await logger.drain()  # graceful shutdown
```

### Notes

- Async API surface: `debug`, `info`, `warning`, `error`, `exception`, `drain`, `bind`, `unbind`, `clear_context`
- Uses the same settings/env vars as `get_logger`
- Prefer `runtime_async()` for automatic lifecycle management
- **Caching**: By default, loggers are cached by name. Calling `get_async_logger("foo")` multiple times returns the same instance. Use `reuse=False` for independent instances (e.g., in tests).

## runtime {#runtime}

```python
@contextmanager
def runtime(*, settings: _Settings | None = None) -> Iterator[_SyncLoggerFacade]
```

Context manager that initializes and drains a sync logger.

### Examples

```python
from fapilog import runtime

with runtime() as logger:
    logger.info("Processing started")
    # ... do work ...
    logger.info("Processing completed")
# Logger automatically drained on exit
```

## runtime_async {#runtime_async}

```python
@asynccontextmanager
async def runtime_async(
    *,
    settings: _Settings | None = None
) -> AsyncIterator[_AsyncLoggerFacade]
```

Async context manager that initializes and drains an async logger.

### Examples

```python
from fapilog import runtime_async

async with runtime_async() as logger:
    await logger.info("Batch processing started")
    await logger.debug("Item", index=1)
# Logger automatically drained on exit
```

## get_cached_loggers {#get_cached_loggers}

```python
def get_cached_loggers() -> dict[str, str]
```

Return a snapshot of currently cached logger names and their types.

### Returns

`dict[str, str]` - Mapping of logger names to their type (`"async"` or `"sync"`).

### Examples

```python
from fapilog import get_logger, get_async_logger, get_cached_loggers

get_logger("service-a")
await get_async_logger("service-b")

cached = get_cached_loggers()
# {"service-a": "sync", "service-b": "async"}
```

## clear_logger_cache {#clear_logger_cache}

```python
async def clear_logger_cache() -> None
```

Drain all cached loggers and clear the cache. Useful for test cleanup.

### Examples

```python
from fapilog import clear_logger_cache

# Clear all cached loggers (drains them first)
await clear_logger_cache()
```

### Notes

- Drains all cached loggers before removing them from the cache
- Thread-safe; can be called from any thread
- Commonly used in test fixtures for isolation between tests

---

_These top-level functions provide the main entry points for using fapilog._
