# Lifecycle & Results

Runtime management and results for fapilog.

## Overview

fapilog provides comprehensive lifecycle management to ensure your logging
system starts cleanly, runs efficiently, and shuts down gracefully. This
includes proper resource management, health monitoring, and result reporting.

## DrainResult

```python
@dataclass
class DrainResult:
    """Result of stopping and draining the logging system."""

    messages_drained: int
    duration_seconds: float
    timed_out: bool
    errors: List[str]
    sink_results: Dict[str, SinkDrainResult]
```

Result object returned by `stop_and_drain()` operations, containing
comprehensive information about the shutdown process.

### Fields

| Field              | Type                         | Description                                |
| ------------------ | ---------------------------- | ------------------------------------------ |
| `messages_drained` | `int`                        | Number of messages successfully written    |
| `duration_seconds` | `float`                      | Time taken to complete the drain operation |
| `timed_out`        | `bool`                       | Whether the operation timed out            |
| `errors`           | `List[str]`                  | Any errors encountered during drain        |
| `sink_results`     | `Dict[str, SinkDrainResult]` | Results from individual sinks              |

### SinkDrainResult

```python
@dataclass
class SinkDrainResult:
    """Result of draining a specific sink."""

    sink_name: str
    messages_written: int
    duration_seconds: float
    success: bool
    error_message: str | None
```

### Examples

```python
from fapilog import stop_and_drain

# Graceful shutdown with timeout
result = await stop_and_drain(timeout=30.0)

print(f"Shutdown completed in {result.duration_seconds:.2f}s")
print(f"Drained {result.messages_drained} messages")

if result.timed_out:
    print("⚠️  Shutdown timed out")
    print(f"Errors: {result.errors}")

# Check individual sink results
for sink_name, sink_result in result.sink_results.items():
    status = "✅" if sink_result.success else "❌"
    print(f"{status} {sink_name}: {sink_result.messages_written} messages")
```

## Runtime Lifecycle

### Initialization

The logging system initializes in a specific order:

```python
from fapilog import runtime

# Initialize and start the logging runtime
async with runtime() as logger:
    # Logging system is now ready
    await logger.info("Application started")

    # ... your application code ...

# Runtime automatically shuts down when exiting the context
```

### Startup Sequence

1. **Configuration loading** - Load settings from environment and config files
2. **Plugin discovery** - Discover and load available plugins
3. **Sink initialization** - Initialize output destinations
4. **Worker startup** - Start background worker threads
5. **Health checks** - Verify system health
6. **Ready state** - System is ready to accept log messages

### Runtime State

The logging system maintains several runtime states:

- **Initializing** - System is starting up
- **Ready** - System is ready to accept messages
- **Degraded** - System is running with reduced functionality
- **Stopping** - System is shutting down
- **Stopped** - System has completely shut down

## Resource Management

### Memory Management

fapilog uses efficient memory management:

- **Object pooling** - Reuse objects to reduce allocation
- **Memory mapping** - Use memory-mapped files for large operations
- **Garbage collection** - Automatic cleanup of unused resources
- **Memory limits** - Configurable memory usage limits

### Connection Management

Manage external connections efficiently:

- **Connection pooling** - Reuse connections to external systems
- **Connection health** - Monitor connection health
- **Automatic reconnection** - Handle connection failures gracefully
- **Connection limits** - Prevent connection exhaustion

## Graceful Shutdown

### Shutdown Sequence

When shutting down, fapilog follows a careful sequence:

1. **Stop accepting new messages** - Prevent new log entries
2. **Flush queued messages** - Process all pending messages
3. **Close sinks** - Gracefully close output destinations
4. **Stop workers** - Shut down background workers
5. **Release resources** - Clean up memory and connections
6. **Final cleanup** - Complete shutdown

### Shutdown Timeout

Configure shutdown behavior:

```python
from fapilog import Settings

settings = Settings(
    lifecycle__shutdown_timeout=30.0,  # 30 seconds to shutdown
    lifecycle__force_shutdown=True      # Force shutdown if timeout exceeded
)
```

### Environment Variables

```bash
export FAPILOG_LIFECYCLE__SHUTDOWN_TIMEOUT=30
export FAPILOG_LIFECYCLE__FORCE_SHUTDOWN=true
```

## Health Monitoring

### Runtime Health

Monitor the health of your logging system:

```python
from fapilog import get_runtime_health

# Get runtime health status
health = await get_runtime_health()
print(f"Runtime status: {health.status}")
print(f"Uptime: {health.uptime}")
print(f"Message count: {health.message_count}")
print(f"Error count: {health.error_count}")
```

### Health Checks

Built-in health checks monitor:

- **Queue health** - Queue utilization and overflow
- **Sink health** - Output destination status
- **Worker health** - Background worker status
- **Memory health** - Memory usage and limits
- **Connection health** - External connection status

## Error Handling

### Runtime Errors

Handle runtime errors gracefully:

```python
from fapilog import runtime
import asyncio

async def main():
    try:
        async with runtime() as logger:
            await logger.info("Application running")
            # ... your application code ...
    except Exception as e:
        # Handle runtime errors
        print(f"Runtime error: {e}")
        # Ensure graceful shutdown
        await asyncio.sleep(1)
```

### Recovery Mechanisms

fapilog includes automatic recovery:

- **Automatic restart** - Restart failed components
- **Circuit breakers** - Prevent cascading failures
- **Fallback modes** - Degraded operation when possible
- **Error reporting** - Detailed error information for debugging

## Performance Optimization

### Runtime Tuning

Optimize runtime performance:

```python
from fapilog import Settings

settings = Settings(
    lifecycle__worker_count=4,           # Number of worker threads
    lifecycle__queue_size=16384,         # Queue capacity
    lifecycle__batch_size=100,           # Batch processing size
    lifecycle__idle_timeout=60.0         # Idle worker timeout
)
```

### Resource Limits

Set appropriate resource limits:

```bash
export FAPILOG_LIFECYCLE__MAX_MEMORY_MB=512
export FAPILOG_LIFECYCLE__MAX_CONNECTIONS=100
export FAPILOG_LIFECYCLE__MAX_WORKERS=8
```

## Monitoring and Debugging

### Runtime Metrics

Monitor runtime performance:

- **Startup time** - Time to initialize the system
- **Shutdown time** - Time to gracefully shut down
- **Resource usage** - Memory and connection utilization
- **Error rates** - Runtime error frequency

### Debug Information

Get detailed runtime information:

```python
from fapilog import get_runtime_debug_info

# Get comprehensive debug information
debug_info = await get_runtime_debug_info()
print(f"Configuration: {debug_info.config}")
print(f"Active plugins: {debug_info.active_plugins}")
print(f"Resource usage: {debug_info.resource_usage}")
print(f"Performance metrics: {debug_info.performance_metrics}")
```

## Best Practices

### Lifecycle Management

1. **Use context managers** - Ensure proper cleanup with `async with`
2. **Monitor health** - Regular health checks for production systems
3. **Configure timeouts** - Set appropriate shutdown timeouts
4. **Handle errors** - Implement proper error handling and recovery
5. **Resource limits** - Set appropriate resource limits for your environment
6. **Graceful shutdown** - Always allow time for graceful shutdown

### Resource Management

1. **Connection pooling** - Reuse connections when possible
2. **Memory monitoring** - Track memory usage and set limits
3. **Worker scaling** - Scale workers based on load
4. **Queue management** - Monitor queue health and adjust sizes
5. **Plugin lifecycle** - Properly manage plugin start/stop cycles

### Error Handling

1. **Circuit breakers** - Prevent cascading failures
2. **Fallback modes** - Provide degraded operation when possible
3. **Error reporting** - Detailed error information for debugging
4. **Recovery strategies** - Automatic recovery when possible
5. **Monitoring** - Alert on critical errors

## Configuration Reference

### Lifecycle Settings

| Setting                       | Type    | Default | Description                        |
| ----------------------------- | ------- | ------- | ---------------------------------- |
| `lifecycle__shutdown_timeout` | `float` | `30.0`  | Shutdown timeout in seconds        |
| `lifecycle__force_shutdown`   | `bool`  | `False` | Force shutdown if timeout exceeded |
| `lifecycle__worker_count`     | `int`   | `2`     | Number of background workers       |
| `lifecycle__queue_size`       | `int`   | `8192`  | Queue capacity                     |
| `lifecycle__batch_size`       | `int`   | `100`   | Batch processing size              |
| `lifecycle__idle_timeout`     | `float` | `60.0`  | Idle worker timeout                |

### Environment Variables

```bash
# Lifecycle configuration
export FAPILOG_LIFECYCLE__SHUTDOWN_TIMEOUT=30
export FAPILOG_LIFECYCLE__FORCE_SHUTDOWN=true
export FAPILOG_LIFECYCLE__WORKER_COUNT=4
export FAPILOG_LIFECYCLE__QUEUE_SIZE=16384
export FAPILOG_LIFECYCLE__BATCH_SIZE=200
export FAPILOG_LIFECYCLE__IDLE_TIMEOUT=60

# Resource limits
export FAPILOG_LIFECYCLE__MAX_MEMORY_MB=512
export FAPILOG_LIFECYCLE__MAX_CONNECTIONS=100
export FAPILOG_LIFECYCLE__MAX_WORKERS=8
```

---

_Proper lifecycle management ensures your logging system runs reliably and shuts down cleanly._
