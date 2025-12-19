# Frequently Asked Questions

Common questions and answers about fapilog.

## General Questions

### Why JSON lines by default?

fapilog uses JSON lines by default because:

- **Machine-readable** - Easy to parse and analyze with log aggregation tools
- **Structured data** - Preserves field types and relationships
- **Industry standard** - Compatible with ELK, Splunk, and other tools
- **Performance** - Fast serialization and parsing

You can still use pretty formatting for development:

```bash
export FAPILOG_FORMAT=pretty
```

### How to add custom fields globally?

Use context binding to add fields to all log messages:

```python
from fapilog import bind

# Add fields that appear in all logs
bind(
    service_name="user-service",
    environment="production",
    version="1.2.3"
)

# All subsequent logs include these fields
logger = get_logger()
logger.info("Application started")
```

### Do I still need log levels?

Yes, log levels are still important for:

- **Filtering** - Show only relevant logs in production
- **Prioritization** - Focus on errors and warnings
- **Compliance** - Meet audit and regulatory requirements
- **Debugging** - Enable detailed logging when needed

```python
# Set appropriate levels for different environments
export FAPILOG_LEVEL=DEBUG    # Development
export FAPILOG_LEVEL=INFO     # Production
export FAPILOG_LEVEL=WARNING  # Testing
```

### How does fapilog compare to logging/structlog?

| Feature         | stdlib logging | structlog | fapilog     |
| --------------- | -------------- | --------- | ----------- |
| **Async**       | ❌ No          | ❌ No     | ✅ Yes      |
| **Performance** | ⚠️ Medium      | ⚠️ Medium | ✅ High     |
| **Structured**  | ❌ No          | ✅ Yes    | ✅ Yes      |
| **Context**     | ❌ Manual      | ⚠️ Basic  | ✅ Advanced |
| **Redaction**   | ❌ No          | ❌ No     | ✅ Yes      |
| **Metrics**     | ❌ No          | ❌ No     | ✅ Yes      |

## Technical Questions

### Can I use it with Celery/async jobs?

Yes! fapilog works great with async job systems:

```python
from fapilog import get_async_logger
from celery import Celery

app = Celery('tasks')

@app.task
async def process_data(data):
    logger = await get_async_logger()

    # Context is preserved across async boundaries
    await logger.info("Processing started", extra={"data_id": data.id})

    try:
        result = await process(data)
        await logger.info("Processing completed", extra={"result": result})
        return result
    except Exception as e:
        await logger.error("Processing failed", exc_info=True)
        raise
```

### How does context inheritance work?

fapilog uses Python's `contextvars` for automatic context inheritance:

```python
from fapilog import bind, get_async_logger

async def main():
    bind(request_id="req-123")

    # Spawn child tasks
    task1 = asyncio.create_task(child_task("task1"))
    task2 = asyncio.create_task(child_task("task2"))

    await asyncio.gather(task1, task2)

async def child_task(name):
    # Automatically inherits request_id from parent
    logger = await get_async_logger()
    await logger.info(f"{name} started")
```

### What happens if a sink fails?

fapilog handles sink failures gracefully:

- **Retry logic** - Automatic retries for transient failures
- **Circuit breakers** - Prevent cascading failures
- **Fallback behavior** - Continue logging to other sinks
- **Error reporting** - Log sink failures for debugging

```bash
# Configure retry behavior
export FAPILOG_SINK__RETRY_ATTEMPTS=3
export FAPILOG_SINK__RETRY_DELAY_MS=1000
export FAPILOG_SINK__CIRCUIT_BREAKER_THRESHOLD=5
```

## Performance Questions

### How does fapilog handle high throughput?

fapilog is designed for high-performance logging:

- **Async processing** - Non-blocking operations
- **Lock-free queues** - Maximum concurrency
- **Batching** - Group messages for efficiency
- **Zero-copy** - Minimal memory allocation

```bash
# Optimize for high throughput
export FAPILOG_MAX_QUEUE_SIZE=65536
export FAPILOG_BATCH_MAX_SIZE=500
export FAPILOG_WORKER_COUNT=8
export FAPILOG_BATCH_TIMEOUT_SECONDS=0.1
```

### What's the memory overhead?

fapilog has minimal memory overhead:

- **Queue size** - Configurable (default: 8KB)
- **Batch processing** - Reduces memory pressure
- **Object pooling** - Reuses objects
- **Garbage collection** - Minimal impact

```bash
# Monitor memory usage
export FAPILOG_ENABLE_METRICS=true
export FAPILOG_METRICS__MEMORY_TRACKING=true
```

### How fast is it?

fapilog is designed for speed:

- **Microsecond latency** - Sub-millisecond logging
- **High throughput** - 100K+ messages/second
- **Async I/O** - Non-blocking operations
- **Optimized serialization** - Fast JSON encoding

## Configuration Questions

### Can I use configuration files?

Yes, fapilog supports multiple configuration methods:

```python
from fapilog import Settings

# From Python code
settings = Settings(
    level="INFO",
    format="json",
    sinks=["stdout", "file"]
)

# From environment variables
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json
export FAPILOG_SINKS=stdout,file

# From YAML/JSON files (coming soon)
```

### How do I configure different environments?

Use environment-specific configuration:

```bash
# Development
export FAPILOG_LEVEL=DEBUG
export FAPILOG_FORMAT=pretty
export FAPILOG_SINKS=stdout

# Production
export FAPILOG_LEVEL=INFO
export FAPILOG_FORMAT=json
export FAPILOG_SINKS=file
export FAPILOG_FILE__DIRECTORY=/var/log/myapp

# Testing
export FAPILOG_LEVEL=WARNING
export FAPILOG_SINKS=stdout
export FAPILOG_DROP_ON_FULL=true
```

### Can I change configuration at runtime?

Yes, fapilog supports hot reloading:

```python
from fapilog import get_settings

# Get current settings
settings = get_settings()

# Update configuration
settings.level = "DEBUG"
settings.enable_metrics = True

# Changes take effect immediately
```

## Integration Questions

### How do I integrate with FastAPI?

fapilog has built-in FastAPI integration:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

app = FastAPI()

# Setup automatic logging
setup_logging(app)

@app.get("/users/{user_id}")
async def get_user(user_id: str):
    # Logger automatically includes request context
    logger = await get_logger()
    await logger.info("Fetching user", extra={"user_id": user_id})
    return {"user_id": user_id}
```

### Can I use it with Docker/Kubernetes?

Yes! fapilog works great in containers:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install fapilog
RUN pip install fapilog

# Configure logging
ENV FAPILOG_LEVEL=INFO
ENV FAPILOG_FORMAT=json
ENV FAPILOG_SINKS=stdout

# Your application code
COPY . .
CMD ["python", "app.py"]
```

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
        - name: myapp
          image: myapp:latest
          env:
            - name: FAPILOG_LEVEL
              value: "INFO"
            - name: FAPILOG_FORMAT
              value: "json"
```

### How do I send logs to external systems?

fapilog supports various external destinations:

```bash
# HTTP sink for log aggregation
export FAPILOG_HTTP__URL=https://logs.example.com/api/logs
export FAPILOG_HTTP__AUTH_TOKEN=your-token

# Custom sinks via plugins
export FAPILOG_PLUGINS__SINKS=custom_sink
```

## Support Questions

### Where can I get help?

Multiple support channels are available:

- **Documentation** - This site and guides
- **GitHub Issues** - Bug reports and feature requests
- **Discussions** - Community support and questions
- **Professional Support** - Enterprise users (contact sales)

### How do I report a bug?

Report bugs on GitHub:

1. **Check existing issues** - Search for similar problems
2. **Provide details** - Include error messages and logs
3. **Reproduce steps** - Clear steps to reproduce the issue
4. **Environment info** - Python version, OS, fapilog version

### Can I contribute to fapilog?

Yes! fapilog is open source and welcomes contributions:

- **Code contributions** - Bug fixes and new features
- **Documentation** - Improve guides and examples
- **Testing** - Report bugs and test fixes
- **Community** - Help other users

See the [Contributing Guide](../contributing/index.md) for details.

---

_Can't find the answer you're looking for? Check the [Troubleshooting](../troubleshooting/index.md) guide or ask the community._
