# Pure Dependency Injection Architecture

## Overview

FastAPI Logger implements a pure dependency injection architecture that completely eliminates global state while providing superior testability, thread safety, and component isolation. This architecture supports multiple logging configurations within the same process with perfect isolation between containers.

## Architecture Components

### LoggingContainer

The `LoggingContainer` class is the central component that manages all logging dependencies using pure dependency injection:

- **Settings Management**: Stores and validates `LoggingSettings`
- **Queue Worker**: Manages async logging queue when enabled
- **Sinks**: Handles multiple output destinations (stdout, file, Loki)
- **HttpX Integration**: Manages trace propagation for outbound requests
- **Lifecycle Management**: Proper startup and shutdown procedures
- **Complete Isolation**: Zero global state or shared resources

### Key Benefits

1. **Perfect Thread Safety**: Each container operates independently without global locks
2. **Complete Isolation**: Different containers cannot interfere with each other
3. **Enhanced Testing**: Perfect isolation prevents any test interference
4. **Memory Efficiency**: No global registry prevents memory leaks
5. **Pure Architecture**: Clean dependency injection throughout system
6. **Backward Compatibility**: Existing code continues to work unchanged

## Usage Examples

### Basic Usage (Backward Compatible)

Existing code continues to work without changes:

```python
from fapilog import configure_logging

# This still works exactly as before
logger = configure_logging()
logger.info("Hello, world!")
```

### Pure Dependency Injection Patterns

For complete control and isolation, use explicit container management:

```python
from fapilog.container import LoggingContainer
from fapilog.settings import LoggingSettings

# Create container with explicit settings
settings = LoggingSettings(
    level="DEBUG",
    sinks=["stdout", "file:///var/log/admin.log"]
)
container = LoggingContainer.create_from_settings(settings)
logger = container.configure()

# Each container operates completely independently
logger.debug("Admin debug message")

# Explicit cleanup when done
container.reset()
```

### Multiple Isolated Containers

The pure DI architecture excels at multiple isolated configurations:

```python
from fapilog.container import LoggingContainer
from fapilog.settings import LoggingSettings

# Admin service container
admin_container = LoggingContainer.create_from_settings(
    LoggingSettings(
        level="DEBUG",
        sinks=["stdout", "file:///var/log/admin.log"]
    )
)
admin_logger = admin_container.configure()

# User service container (completely isolated)
user_container = LoggingContainer.create_from_settings(
    LoggingSettings(
        level="INFO",
        sinks=["stdout", "loki://localhost:3100"]
    )
)
user_logger = user_container.configure()

# Each logger operates independently with zero interference
admin_logger.debug("Admin debug message")  # Goes to stdout + file
user_logger.info("User activity")          # Goes to stdout + Loki

# Clean up each container independently
admin_container.reset()
user_container.reset()
```

### FastAPI Integration with Pure DI

Containers integrate seamlessly with FastAPI applications using pure dependency injection:

```python
from fastapi import FastAPI
from fapilog.bootstrap import configure_with_container
from fapilog.settings import LoggingSettings

app = FastAPI()

# Pure DI approach - get both logger and container
logger, container = configure_with_container(
    LoggingSettings(
        level="INFO",
        sinks=["stdout"],
        trace_id_header="X-Request-ID"
    ),
    app=app  # Automatic middleware registration
)

@app.get("/")
async def root():
    logger.info("Request received")
    return {"message": "Hello World"}

# Proper cleanup with explicit container access
@app.on_event("shutdown")
async def shutdown_event():
    await container.shutdown()
```

### Testing with Pure Dependency Injection

The pure DI architecture makes testing trivial with perfect isolation:

```python
import pytest
from fapilog.container import LoggingContainer
from fapilog.settings import LoggingSettings

@pytest.fixture
def isolated_logging():
    """Create a completely isolated logging container for tests."""
    container = LoggingContainer.create_from_settings(
        LoggingSettings(
            level="DEBUG",
            sinks=["stdout"],
            queue_enabled=False  # Synchronous for testing
        )
    )
    logger = container.configure()

    yield container, logger

    # Automatic cleanup - no global state to worry about
    container.reset()

def test_logging_functionality(isolated_logging):
    container, logger = isolated_logging

    # Test logging with perfect isolation
    logger.info("Test message")
    assert container.is_configured

    # No global state means no interference between tests
```

### Context Manager Pattern

The pure DI architecture supports clean context management:

```python
from fapilog.container import LoggingContainer
from fapilog.settings import LoggingSettings

# Context manager pattern for automatic cleanup
with LoggingContainer.create_from_settings(settings) as container:
    logger = container.configure()
    logger.info("Scoped logging")
    # Automatic cleanup on exit

# Scoped logger context for convenience
with container.scoped_logger("background_task") as scoped_logger:
    scoped_logger.info("Task processing")
    # Automatic context cleanup
```

## Configuration Options

### LoggingSettings

The `LoggingSettings` class provides comprehensive configuration for pure DI:

```python
from fapilog.settings import LoggingSettings

settings = LoggingSettings(
    # Basic settings
    level="INFO",                    # Logging level
    json_console="auto",            # Console output format

    # Queue settings (with pure DI)
    queue_enabled=True,             # Enable async logging
    queue_maxsize=1000,            # Queue size
    queue_batch_size=10,           # Batch processing size
    queue_batch_timeout=1.0,       # Batch timeout
    queue_overflow="drop",         # Overflow strategy

    # Sink configuration
    sinks=["stdout", "file:///var/log/app.log"],

    # Security settings
    redact_fields=["password", "token"],
    redact_patterns=["\\d{4}-\\d{4}-\\d{4}-\\d{4}"],  # Credit cards

    # Trace propagation
    enable_httpx_trace_propagation=True,
    trace_id_header="X-Request-ID",

    # Performance settings
    sampling_rate=1.0,             # Log sampling rate
    enable_resource_metrics=True,   # Include CPU/memory metrics
)
```

### Environment Variables

All settings can be configured via environment variables:

```bash
export FAPILOG_LEVEL=DEBUG
export FAPILOG_SINKS="stdout,file:///var/log/app.log"
export FAPILOG_QUEUE_ENABLED=true
export FAPILOG_REDACT_FIELDS="password,secret,token"
```

## Thread Safety

The pure DI architecture provides perfect thread safety without global locks:

```python
import threading
from fapilog.container import LoggingContainer

def worker_function(worker_id):
    # Each thread creates its own isolated container
    container = LoggingContainer.create_from_settings(
        LoggingSettings(level="INFO", sinks=["stdout"])
    )
    logger = container.configure()

    for i in range(100):
        logger.info(f"Worker {worker_id}, message {i}")

    # Clean up thread-local container
    container.reset()

# Start multiple threads safely - no global contention
threads = []
for i in range(5):
    thread = threading.Thread(target=worker_function, args=(i,))
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()
```

## Memory Management

Containers provide automatic memory management with explicit cleanup:

```python
from fapilog.container import LoggingContainer
from fapilog.bootstrap import get_active_containers, reset_logging

# Individual container cleanup
container = LoggingContainer()
logger = container.configure()
# ... use logger ...
container.reset()  # Explicit cleanup

# Bootstrap-level cleanup (for configure_logging() usage)
reset_logging()  # Cleans up bootstrap-managed containers

# Query active containers (bootstrap registry, not global state)
active = get_active_containers()
print(f"Active containers: {len(active)}")

# Context manager pattern (automatic cleanup)
with LoggingContainer() as container:
    logger = container.configure()
    # ... use logger ...
    # Automatic cleanup on exit
```

## Migration Guide

### From Old Architecture to Pure DI

The new pure dependency injection architecture eliminates all global state:

**Before (Global State - Now Removed):**

```python
# These functions no longer exist:
from fapilog.container import get_current_container  # ❌ REMOVED
from fapilog.container import set_current_container  # ❌ REMOVED
from fapilog.container import cleanup_all_containers # ❌ REMOVED

container = get_current_container()  # ❌ No longer available
```

**After (Pure Dependency Injection):**

```python
from fapilog.container import LoggingContainer
from fapilog.bootstrap import configure_with_container

# Explicit container creation
container = LoggingContainer.create_from_settings(settings)
logger = container.configure()

# Or with bootstrap integration
logger, container = configure_with_container(settings)
```

### From Queue Integration Global State

**Before (Global State Access - Now Removed):**

```python
# This pattern no longer works:
from fapilog._internal.queue_integration import queue_sink  # ❌ Legacy

# Global state access removed
```

**After (Pure Dependency Injection):**

```python
from fapilog._internal.queue_integration import create_queue_sink

# Explicit container passing
container = LoggingContainer.create_from_settings(settings)
queue_sink_processor = create_queue_sink(container)
```

### From Bootstrap Global Functions

**Before (Deprecated Functions - Some Removed):**

```python
from fapilog.bootstrap import _configure_standard_logging  # ❌ Deprecated
_configure_standard_logging("INFO")
```

**After (Pure Dependency Injection):**

```python
from fapilog.bootstrap import configure_with_container
from fapilog.settings import LoggingSettings

logger, container = configure_with_container(
    LoggingSettings(level="INFO")
)
```

## Performance Considerations

### Container Creation Performance

- Container creation is lightweight and fast
- Pure DI eliminates global lock contention
- Factory methods optimize common patterns
- No global registry lookup overhead

### Queue Worker Performance

- Async queues provide excellent throughput with pure DI
- Queue workers receive containers through explicit injection
- No global state lookup in hot paths
- Tune `queue_batch_size` and `queue_batch_timeout` for workload

### Memory Usage

- Each container maintains only its own resources
- No global registry prevents memory leaks
- Perfect isolation means predictable memory patterns
- Explicit cleanup provides deterministic resource management

## Troubleshooting

### Common Migration Issues

1. **Missing Global Functions**

   ```python
   # ❌ This will fail - function removed
   from fapilog.container import cleanup_all_containers

   # ✅ Use explicit container management instead
   container = LoggingContainer()
   logger = container.configure()
   # ... use logger ...
   container.reset()
   ```

2. **Queue Integration Changes**

   ```python
   # ❌ Legacy queue sink (transition compatibility only)
   from fapilog._internal.queue_integration import queue_sink

   # ✅ Pure DI queue sink creation
   from fapilog._internal.queue_integration import create_queue_sink
   queue_sink_processor = create_queue_sink(container)
   ```

3. **Container Isolation Expectations**

   ```python
   # Each container is completely isolated
   container1 = LoggingContainer.create_from_settings(settings)
   container2 = LoggingContainer.create_from_settings(settings)
   # These are completely separate instances with zero interaction
   ```

### Debugging Pure DI Containers

```python
from fapilog.container import LoggingContainer
from fapilog.bootstrap import get_active_containers

container = LoggingContainer()
logger = container.configure()

# Check container state
print(f"Configured: {container.is_configured}")
print(f"Settings: {container.settings}")
print(f"Queue Worker: {container.queue_worker}")

# Debug queue state (if enabled)
if container.queue_worker:
    print(f"Queue size: {container.queue_worker.queue.qsize()}")
    print(f"Running: {container.queue_worker._running}")

# Check bootstrap registry (not global state)
active_containers = get_active_containers()
print(f"Bootstrap-managed containers: {len(active_containers)}")
```

## Best Practices

1. **Use Factory Methods**: Prefer `LoggingContainer.create_from_settings()` for clarity
2. **Explicit Container Passing**: Pass containers explicitly rather than relying on implicit access
3. **Context Managers**: Use context managers for automatic cleanup
4. **Test Isolation**: Create dedicated containers for each test
5. **Thread Safety**: Create thread-local containers for concurrent scenarios
6. **Resource Management**: Always clean up containers explicitly in long-running applications
7. **Bootstrap Integration**: Use `configure_with_container()` when you need both logger and container access

## Architecture Validation

The pure dependency injection architecture provides:

### Zero Global State

- No global variables anywhere in the system
- No global functions for container access
- No shared state between containers
- Complete component isolation

### Perfect Isolation

- Containers operate independently
- No interference between instances
- Thread-safe without global locks
- Predictable resource management

### Enhanced Testing

- Complete test isolation
- No global state cleanup needed
- Independent container lifecycle
- Deterministic behavior

### Production Readiness

- Memory efficient with explicit cleanup
- Thread-safe concurrent operations
- Performance optimized dependency injection
- Clean architecture principles throughout

## Future Enhancements

The pure dependency injection architecture provides a foundation for:

- **Enhanced Context Managers**: More sophisticated resource management
- **Container Factories**: Optimized container creation patterns
- **Dynamic Configuration**: Runtime configuration updates with isolation
- **Performance Monitoring**: Built-in metrics with container-level granularity
- **Plugin Architecture**: Extensible components with pure DI patterns
