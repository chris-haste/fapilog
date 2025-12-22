# Troubleshooting

Common issues and solutions for fapilog.

```{toctree}
:maxdepth: 2
:titlesonly:
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

Use the built-in settings and logging output to validate your setup:

- Confirm key env vars (e.g., `FAPILOG_CORE__LOG_LEVEL`, `FAPILOG_CORE__MAX_QUEUE_SIZE`, `FAPILOG_FILE__DIRECTORY`) are set as expected.
- Enable internal diagnostics temporarily:
  ```bash
  export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
  ```
  This emits WARN/DEBUG diagnostics from the worker/sink paths without crashing the app.

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
export FAPILOG_CORE__MAX_QUEUE_SIZE=32768

# Increase batch size for better throughput
export FAPILOG_CORE__BATCH_MAX_SIZE=200

# Configure backpressure behavior
export FAPILOG_CORE__DROP_ON_FULL=false
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=50
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
from fapilog import get_async_logger

# Ensure context is bound for each request
async def handle_request(request_id: str, user_id: str):
    logger = await get_async_logger()
    logger.bind(request_id=request_id, user_id=user_id)

    try:
        await logger.info("Request started")
        # ... process request ...
    finally:
        logger.clear_context()  # Clean up context
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
from fapilog import get_async_logger

logger = await get_async_logger()

# Convert complex objects to simple types
user_data = {
    "user_id": user.id,  # Simple types only
    "username": user.username,
    "created_at": user.created_at.isoformat(),  # Convert datetime
    "preferences": dict(user.preferences)  # Convert to dict
}

await logger.info("User data", **user_data)
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
export FAPILOG_CORE__ENABLE_REDACTORS=true

# Configure sensitive fields
export FAPILOG_CORE__SENSITIVE_FIELDS_POLICY=password,api_key,secret,token
```

## Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
# Enable debug logging
export FAPILOG_CORE__LOG_LEVEL=DEBUG
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true

# Enable verbose sink output
export FAPILOG_DEBUG__VERBOSE_SINKS=true
export FAPILOG_DEBUG__LOG_PIPELINE=true
```

## Performance Issues

### High Memory Usage

```bash
# Reduce queue size
export FAPILOG_CORE__MAX_QUEUE_SIZE=4096

# Enable aggressive batching
export FAPILOG_CORE__BATCH_MAX_SIZE=500
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.5

# Monitor memory usage
export FAPILOG_CORE__ENABLE_METRICS=true
```

### Slow Logging

```bash
# Optimize queue/batching
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=200
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=1
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=10

# Keep stdout sink (default) instead of slow file sinks
unset FAPILOG_FILE__DIRECTORY
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
