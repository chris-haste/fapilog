# Configuration

Settings and environment configuration for fapilog.

## Overview

fapilog uses a hierarchical configuration system that prioritizes:

1. **Environment variables** (highest priority)
2. **Settings classes** (programmatic configuration)
3. **Default values** (lowest priority)

## FapilogSettings

```python
class FapilogSettings(BaseSettings):
    """Main configuration class for fapilog."""

    # Core settings
    level: str = "INFO"
    format: str = "json"
    enable_metrics: bool = False

    # File sink settings
    file__directory: str | None = None
    file__max_bytes: int = 10485760  # 10MB
    file__max_files: int = 0
    file__compress_rotated: bool = False

    # Performance settings
    max_queue_size: int = 8192
    batch_max_size: int = 100
    batch_timeout_seconds: float = 1.0
    worker_count: int = 2

    # Redaction settings
    enable_redaction: bool = True
    redaction__sensitive_fields: List[str] = ["password", "api_key", "secret"]
    redaction__enable_regex: bool = True
    redaction__patterns: List[str] = []
```

### Core Settings

| Setting          | Type   | Default  | Description                                               |
| ---------------- | ------ | -------- | --------------------------------------------------------- |
| `level`          | `str`  | `"INFO"` | Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `format`         | `str`  | `"json"` | Output format (json, pretty)                              |
| `enable_metrics` | `bool` | `False`  | Enable Prometheus metrics collection                      |

### File Sink Settings

| Setting                  | Type          | Default    | Description                                        |
| ------------------------ | ------------- | ---------- | -------------------------------------------------- |
| `file__directory`        | `str \| None` | `None`     | Directory for log files (enables file sink if set) |
| `file__max_bytes`        | `int`         | `10485760` | Maximum file size before rotation (10MB)           |
| `file__max_files`        | `int`         | `0`        | Maximum number of rotated files (0 = unlimited)    |
| `file__compress_rotated` | `bool`        | `False`    | Compress old log files                             |

### Performance Settings

| Setting                 | Type    | Default | Description                             |
| ----------------------- | ------- | ------- | --------------------------------------- |
| `max_queue_size`        | `int`   | `8192`  | Maximum queue capacity for log messages |
| `batch_max_size`        | `int`   | `100`   | Maximum batch size for processing       |
| `batch_timeout_seconds` | `float` | `1.0`   | Timeout for batch processing            |
| `worker_count`          | `int`   | `2`     | Number of background worker threads     |

### Redaction Settings

| Setting                       | Type        | Default                             | Description                       |
| ----------------------------- | ----------- | ----------------------------------- | --------------------------------- |
| `enable_redaction`            | `bool`      | `True`                              | Enable data redaction             |
| `redaction__sensitive_fields` | `List[str]` | `["password", "api_key", "secret"]` | Field names to mask               |
| `redaction__enable_regex`     | `bool`      | `True`                              | Enable regex pattern matching     |
| `redaction__patterns`         | `List[str]` | `[]`                                | Custom regex patterns for masking |

## Environment Variables

### Core Configuration

```bash
# Log level and format
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json
export FAPILOG_ENABLE_METRICS=true

# Performance tuning
export FAPILOG_MAX_QUEUE_SIZE=16384
export FAPILOG_BATCH_MAX_SIZE=200
export FAPILOG_BATCH_TIMEOUT_SECONDS=0.5
export FAPILOG_WORKER_COUNT=4
```

### File Sink Configuration

```bash
# Enable file logging
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

### Redaction Configuration

```bash
# Enable redaction
export FAPILOG_ENABLE_REDACTION=true
export FAPILOG_REDACTION__SENSITIVE_FIELDS=password,api_key,secret,token
export FAPILOG_REDACTION__ENABLE_REGEX=true
export FAPILOG_REDACTION__PATTERNS=sk-[a-zA-Z0-9]{24},pk_[a-zA-Z0-9]{24}
```

## Settings Hierarchy

### 1. Environment Variables (Highest Priority)

Environment variables override all other settings:

```bash
export FAPILOG_LEVEL=DEBUG
export FAPILOG_FORMAT=pretty
```

### 2. Settings Classes (Medium Priority)

Programmatic configuration overrides defaults:

```python
from fapilog import Settings

settings = Settings(
    level="WARNING",
    format="json",
    enable_metrics=True,
    max_queue_size=32768
)

logger = get_logger(settings=settings)
```

### 3. Default Values (Lowest Priority)

Built-in defaults when nothing else is specified:

```python
# These are the built-in defaults
DEFAULT_LEVEL = "INFO"
DEFAULT_FORMAT = "json"
DEFAULT_QUEUE_SIZE = 8192
```

## Configuration Examples

### Development Environment

```python
from fapilog import Settings

dev_settings = Settings(
    level="DEBUG",
    format="pretty",
    enable_metrics=False,
    max_queue_size=4096,
    batch_max_size=50
)

logger = get_logger(settings=dev_settings)
```

### Production Environment

```python
from fapilog import Settings

prod_settings = Settings(
    level="INFO",
    format="json",
    enable_metrics=True,
    file__directory="/var/log/myapp",
    file__max_bytes=104857600,  # 100MB
    file__max_files=10,
    file__compress_rotated=True,
    max_queue_size=65536,
    worker_count=8
)

logger = get_logger(settings=prod_settings)
```

### High-Performance Configuration

```python
from fapilog import Settings

perf_settings = Settings(
    level="WARNING",  # Reduce log volume
    format="json",
    max_queue_size=131072,  # 128KB
    batch_max_size=500,
    batch_timeout_seconds=0.1,
    worker_count=16,
    drop_on_full=True  # Drop messages when queue is full
)

logger = get_logger(settings=perf_settings)
```

## Environment-Specific Configuration

### Development

```bash
# Development - verbose and human-readable
export FAPILOG_LEVEL=DEBUG
export FAPILOG_FORMAT=pretty
export FAPILOG_ENABLE_METRICS=false
export FAPILOG_MAX_QUEUE_SIZE=4096
```

### Staging

```bash
# Staging - structured but detailed
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json
export FAPILOG_ENABLE_METRICS=true
export FAPILOG_FILE__DIRECTORY=/var/log/myapp-staging
```

### Production

```bash
# Production - efficient and monitored
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json
export FAPILOG_ENABLE_METRICS=true
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=104857600
export FAPILOG_FILE__MAX_FILES=10
export FAPILOG_FILE__COMPRESS_ROTATED=true
export FAPILOG_MAX_QUEUE_SIZE=65536
export FAPILOG_WORKER_COUNT=8
```

## Configuration Validation

fapilog automatically validates configuration:

```python
from fapilog import Settings

try:
    # This will raise ValidationError if invalid
    settings = Settings(
        level="INVALID_LEVEL",  # Error: not a valid log level
        max_queue_size=-1       # Error: must be positive
    )
except ValidationError as e:
    print(f"Configuration error: {e}")
```

### Validation Rules

- **Log level** - Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Queue size** - Must be positive integer
- **Batch size** - Must be positive integer
- **Worker count** - Must be positive integer
- **File directory** - Must be valid path if specified
- **Timeout values** - Must be positive numbers

## Hot Reloading

fapilog supports hot reloading of configuration:

```python
from fapilog import get_settings

# Get current settings
settings = get_settings()

# Update configuration
settings.level = "DEBUG"
settings.enable_metrics = True

# Changes take effect immediately
logger = get_logger()
await logger.debug("Debug logging now enabled")
```

## Async Logger Configuration

The async logger supports the same configuration options as the sync logger, with additional async-specific features:

### Async Logger Factory

```python
from fapilog import get_async_logger, Settings

# Basic async logger
logger = await get_async_logger()

# With custom name
logger = await get_async_logger("my_service")

# With custom settings
settings = Settings(core__enable_metrics=True)
logger = await get_async_logger("my_service", settings=settings)
```

### Async Context Manager

```python
from fapilog import runtime_async

# Automatic lifecycle management
async with runtime_async() as logger:
    await logger.info("Processing started")
    # ... your async code ...
    await logger.info("Processing completed")
# Logger automatically drained on exit
```

### Async Logger Methods

```python
# All logging methods are awaitable
await logger.debug("Debug message", debug_data="value")
await logger.info("Info message", info_data="value")
await logger.warning("Warning message", warning_data="value")
await logger.error("Error message", error_data="value")
await logger.exception("Exception message", exception_data="value")

# Flush current batches without stopping
await logger.flush()

# Gracefully stop and drain
result = await logger.drain()
print(f"Processed {result.processed} messages")
```

### FastAPI Integration Example

```python
from fastapi import Depends, FastAPI
from fapilog import get_async_logger

app = FastAPI()

async def get_logger():
    return await get_async_logger("request")

@app.get("/users/{user_id}")
async def get_user(user_id: int, logger = Depends(get_logger)):
    await logger.info("User lookup", user_id=user_id)
    # ... your code ...
    await logger.info("User found", user_id=user_id)
    return {"user_id": user_id}
```

## Best Practices

1. **Environment variables** - Use for deployment-specific configuration
2. **Settings classes** - Use for application-specific defaults
3. **Validation** - Always validate configuration before use
4. **Defaults** - Provide sensible defaults for all settings
5. **Documentation** - Document all configuration options
6. **Testing** - Test configuration validation and hot reloading

---

_Configuration management provides flexibility and control over fapilog's behavior._
