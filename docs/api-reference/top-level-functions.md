# Top-Level Functions

Main entry points and utilities for fapilog.

## get_logger

```python
def get_logger(
    name: str | None = None,
    *,
    settings: _Settings | None = None,
) -> _SyncLoggerFacade
```

Return a ready-to-use sync logger facade wired to a container-scoped pipeline.

This function provides a zero-config, container-scoped logger that automatically
configures sinks, enrichers, and metrics based on environment variables or
custom settings. Each logger instance is completely isolated with no global state.

### Parameters

| Parameter  | Type                | Default | Description                                                    |
| ---------- | ------------------- | ------- | -------------------------------------------------------------- |
| `name`     | `str \| None`       | `None`  | Logger name for identification. If None, uses the module name. |
| `settings` | `_Settings \| None` | `None`  | Custom settings. If None, uses environment variables.          |

### Returns

`_SyncLoggerFacade` - A logger instance ready for use.

### Examples

```python
from fapilog import get_logger

# Zero-config usage (uses environment variables)
logger = get_logger()
logger.info("Application started")

# With custom name for better identification
logger = get_logger("user_service")
logger.info("User authentication successful")

# With custom settings
from fapilog import Settings
settings = Settings(core__enable_metrics=True)
logger = get_logger(settings=settings)
logger.info("Metrics-enabled logger ready")

# Cleanup when done
logger.close()
```

### Environment Variables

The following environment variables are automatically read:

- `FAPILOG_LEVEL` - Log level (default: INFO)
- `FAPILOG_FORMAT` - Output format (default: json)
- `FAPILOG_FILE__DIRECTORY` - File sink directory (if set, enables file logging)
- `FAPILOG_ENABLE_METRICS` - Enable metrics collection (default: false)

### Notes

- **Zero-config by default** - automatically reads environment variables
- **Container-scoped isolation** - no global mutable state between instances
- **Automatic sink selection** - chooses file or stdout based on FAPILOG_FILE\_\_DIRECTORY
- **Built-in enrichers** - automatically includes runtime info and context variables
- **Thread-safe** - can be used across multiple threads safely
- **Async-aware** - works seamlessly with asyncio applications

## runtime

```python
@contextmanager
def runtime(*, settings: _Settings | None = None) -> Iterator[_SyncLoggerFacade]
```

Context manager that initializes and drains the default runtime.

This function provides a context manager that automatically handles logger
lifecycle including initialization, usage, and cleanup. It's perfect for
applications that need guaranteed cleanup of logging resources.

### Parameters

| Parameter  | Type                | Default | Description                      |
| ---------- | ------------------- | ------- | -------------------------------- |
| `settings` | `_Settings \| None` | `None`  | Custom settings for the runtime. |

### Returns

`Iterator[_SyncLoggerFacade]` - A logger instance within the context.

### Examples

```python
from fapilog import runtime

# Basic usage with automatic cleanup
with runtime() as logger:
    logger.info("Processing started")
    # ... do work ...
    logger.info("Processing completed")
# Logger automatically cleaned up here

# With custom settings
from fapilog import Settings
settings = Settings(core__enable_metrics=True)

with runtime(settings=settings) as logger:
    logger.info("Metrics-enabled processing")
    # ... do work ...
```

### Notes

- **Automatic cleanup** - logger resources are guaranteed to be cleaned up
- **Exception safe** - cleanup happens even if exceptions occur
- **Context manager** - use with Python's `with` statement
- **Settings support** - can pass custom settings for configuration
- **Drain result** - advanced users can access drain results via StopIteration.value
- **Thread-safe** - can be used across multiple threads safely

## stop_and_drain

```python
async def stop_and_drain(
    *,
    timeout: float | None = None,
    force: bool = False
) -> DrainResult
```

Stop the default runtime and drain all pending log messages.

This function gracefully shuts down the logging system, ensuring all buffered
messages are written before returning. It's useful for applications that need
explicit control over shutdown timing.

### Parameters

| Parameter | Type            | Default | Description                                           |
| --------- | --------------- | ------- | ----------------------------------------------------- |
| `timeout` | `float \| None` | `None`  | Maximum time to wait for drain completion in seconds. |
| `force`   | `bool`          | `False` | If True, force shutdown even if timeout is exceeded.  |

### Returns

`DrainResult` - Result containing statistics about the drain operation.

### Examples

```python
from fapilog import stop_and_drain

# Graceful shutdown with timeout
result = await stop_and_drain(timeout=30.0)
print(f"Drained {result.messages_drained} messages in {result.duration_seconds}s")

# Force shutdown if needed
result = await stop_and_drain(timeout=10.0, force=True)
if result.timed_out:
    print("Shutdown timed out, forced completion")
```

### DrainResult

The `DrainResult` contains information about the drain operation:

| Field              | Type        | Description                             |
| ------------------ | ----------- | --------------------------------------- |
| `messages_drained` | `int`       | Number of messages successfully written |
| `duration_seconds` | `float`     | Time taken to complete the drain        |
| `timed_out`        | `bool`      | Whether the operation timed out         |
| `errors`           | `List[str]` | Any errors encountered during drain     |

### Notes

- **Graceful shutdown** - waits for pending messages to be written
- **Configurable timeout** - prevents indefinite waiting
- **Force option** - allows immediate shutdown if needed
- **Error reporting** - provides details about any issues during drain
- **Async operation** - must be awaited

---

_These top-level functions provide the main entry points for using fapilog._
