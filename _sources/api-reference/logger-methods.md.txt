# Logger Methods

Synchronous loggers come from `get_logger()` and expose synchronous methods. Async loggers come from `get_async_logger()` / `runtime_async()` and their logging methods are awaitable.

## debug {#debug}

```python
# Sync
logger.debug(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None

# Async
await logger.debug(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
```

Log diagnostic information.

### Example

```python
# sync
logger.debug("Processing user", user_id="123", stage="preflight")

# async
await async_logger.debug("Processing user", user_id="123", stage="preflight")
```

## info {#info}

```python
logger.info(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
await async_logger.info(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
```

Log application or business events.

### Example

```python
logger.info("User logged in", user_id="abc-123", ip="192.168.1.100")
await async_logger.info("Job completed", job_id="job-42", duration_ms=87)
```

## warning {#warning}

```python
logger.warning(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
await async_logger.warning(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
```

Log potentially problematic situations.

### Example

```python
logger.warning("Slow dependency", dependency="postgres", latency_ms=1200)
```

## error {#error}

```python
logger.error(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
await async_logger.error(message: str, *, exc: BaseException | None = None, exc_info: Any | None = None, **metadata) -> None
```

Log errors. Pass `exc_info=True` to include the current exception or `exc=<exception>` to serialize a specific one.

### Example

```python
try:
    do_work()
except Exception:
    logger.error("Work failed", exc_info=True)
```

## exception {#exception}

```python
logger.exception(message: str = "", **metadata) -> None
await async_logger.exception(message: str = "", **metadata) -> None
```

Convenience for `error(..., exc_info=True)` inside an exception handler.

### Example

```python
try:
    await process()
except Exception:
    await async_logger.exception("Process crashed", request_id="req-1")
```

## Context binding

```python
logger.bind(**context) -> Logger
logger.unbind(*keys) -> None
logger.clear_context() -> None
```

Context is stored per task/thread and merged into every log call until cleared.

### Example

```python
logger.bind(request_id="req-123", user_id="user-7")
logger.info("Request started")
logger.unbind("user_id")
logger.info("Still has request_id")
logger.clear_context()
```

## Async-only lifecycle helpers

```python
await async_logger.drain()  # graceful shutdown; returns DrainResult
```

Sync loggers expose `stop_and_drain()` as an async method. Use `asyncio.run(logger.stop_and_drain())` if you need to stop outside of `runtime()`.

---

_These methods cover the supported public surface for both sync and async loggers._
