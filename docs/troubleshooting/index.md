# Troubleshooting

Common issues and solutions for fapilog.

```{toctree}
:maxdepth: 2
:caption: Troubleshooting

logs-dropped-under-load
context-values-missing
file-sink-not-rotating
serialization-errors
pii-showing-despite-redaction
```

## Overview

This section helps you diagnose and fix common issues with fapilog:

- **Logs dropped under load** - Queue overflow and backpressure issues
- **Context values missing** - Context binding and inheritance problems
- **File sink not rotating** - File rotation and retention issues
- **Serialization errors** - JSON and format problems
- **PII showing despite redaction** - Data masking configuration issues

## Quick Diagnosis

### Check System Health

```python
from fapilog import get_system_health

health = await get_system_health()
print(f"System status: {health.status}")
print(f"Queue utilization: {health.queue_utilization}%")
print(f"Active sinks: {health.active_sinks}")
print(f"Worker status: {health.worker_status}")
```

### Check Configuration

```python
from fapilog import get_current_config

config = get_current_config()
print(f"Log level: {config.level}")
print(f"Format: {config.format}")
print(f"Sinks: {config.sinks}")
print(f"Queue size: {config.max_queue_size}")
```

### Check Metrics

```python
from fapilog import get_metrics

metrics = await get_metrics()
print(f"Messages processed: {metrics.messages_processed}")
print(f"Messages dropped: {metrics.messages_dropped}")
print(f"Error rate: {metrics.error_rate}%")
```

## Common Issues

### 1. Logs Are Dropped Under Load

**Symptoms:**

- Log messages disappear during high traffic
- Queue utilization shows 100%
- Error messages about queue overflow

**Causes:**

- Queue size too small for your load
- Sinks can't keep up with message volume
- Backpressure handling not configured

**Solutions:**

```bash
# Increase queue size
export FAPILOG_MAX_QUEUE_SIZE=32768

# Increase batch size for better throughput
export FAPILOG_BATCH_MAX_SIZE=200

# Configure backpressure behavior
export FAPILOG_DROP_ON_FULL=false
export FAPILOG_BACKPRESSURE_WAIT_MS=50
```

### 2. Context Values Missing

**Symptoms:**

- Request ID not appearing in logs
- User context lost between operations
- Correlation broken across async calls

**Causes:**

- Context not properly bound
- Context cleared too early
- Async context inheritance issues

**Solutions:**

```python
from fapilog import bind, unbind

# Ensure context is bound for each request
async def handle_request(request_id: str, user_id: str):
    bind(request_id=request_id, user_id=user_id)

    try:
        logger = get_logger()
        await logger.info("Request started")
        # ... process request ...
    finally:
        unbind()  # Clean up context
```

### 3. File Sink Not Rotating

**Symptoms:**

- Log files grow indefinitely
- Old log files not compressed
- Disk space filling up

**Causes:**

- File rotation not configured
- Directory permissions issues
- Rotation thresholds too high

**Solutions:**

```bash
# Enable file rotation
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760  # 10MB
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true

# Check directory permissions
sudo chown -R myapp:myapp /var/log/myapp
sudo chmod 755 /var/log/myapp
```

### 4. Serialization Errors

**Symptoms:**

- JSON encoding errors in logs
- Non-serializable objects causing crashes
- Malformed log output

**Causes:**

- Complex objects in extra fields
- Circular references
- Non-JSON-serializable types

**Solutions:**

```python
from fapilog import get_logger

logger = get_logger()

# Convert complex objects to simple types
user_data = {
    "user_id": user.id,  # Simple types only
    "username": user.username,
    "created_at": user.created_at.isoformat(),  # Convert datetime
    "preferences": dict(user.preferences)  # Convert to dict
}

await logger.info("User data", extra=user_data)
```

### 5. PII Showing Despite Redaction

**Symptoms:**

- Passwords visible in logs
- API keys not masked
- Personal information exposed

**Causes:**

- Redactors not enabled
- Field patterns not configured
- Redaction order issues

**Solutions:**

```bash
# Enable redaction
export FAPILOG_ENABLE_REDACTION=true

# Configure sensitive fields
export FAPILOG_REDACTION__SENSITIVE_FIELDS=password,api_key,secret,token

# Enable regex patterns
export FAPILOG_REDACTION__ENABLE_REGEX=true
export FAPILOG_REDACTION__PATTERNS=sk-[a-zA-Z0-9]{24},pk_[a-zA-Z0-9]{24}
```

## Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
# Enable debug logging
export FAPILOG_LEVEL=DEBUG
export FAPILOG_ENABLE_DEBUG=true

# Enable verbose sink output
export FAPILOG_DEBUG__VERBOSE_SINKS=true
export FAPILOG_DEBUG__LOG_PIPELINE=true
```

## Performance Issues

### High Memory Usage

```bash
# Reduce queue size
export FAPILOG_MAX_QUEUE_SIZE=4096

# Enable aggressive batching
export FAPILOG_BATCH_MAX_SIZE=500
export FAPILOG_BATCH_TIMEOUT_SECONDS=0.5

# Monitor memory usage
export FAPILOG_ENABLE_METRICS=true
```

### Slow Logging

```bash
# Increase worker count
export FAPILOG_WORKER_COUNT=8

# Optimize batch processing
export FAPILOG_BATCH_MAX_SIZE=200
export FAPILOG_BATCH_TIMEOUT_SECONDS=1

# Use faster sinks
export FAPILOG_SINKS=stdout  # Fastest option
```

## Getting Help

### Self-Service

1. **Check the logs** - Look for error messages and warnings
2. **Verify configuration** - Ensure environment variables are set correctly
3. **Test with minimal setup** - Start with basic configuration and add complexity
4. **Check system resources** - Monitor CPU, memory, and disk usage

### Community Support

- **GitHub Issues** - Report bugs and request features
- **Discussions** - Ask questions and share solutions
- **Documentation** - Check this troubleshooting guide

### Professional Support

For enterprise users:

- **Priority support** - Direct access to the development team
- **Custom solutions** - Tailored configurations for your environment
- **Performance tuning** - Expert optimization for your use case

## Next Steps

- **[Examples](../examples/index.md)** - See working examples
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[User Guide](../user-guide/index.md)** - Learn best practices

---

_This troubleshooting guide helps you resolve common issues and get fapilog working smoothly._
