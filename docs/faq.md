# Frequently Asked Questions

Common questions and answers about fapilog.

## General Questions

### Why JSON lines by default?

fapilog uses JSON lines by default because:

- **Machine-readable** - Easy to parse and analyze with log aggregation tools
- **Structured data** - Preserves field types and relationships
- **Industry standard** - Compatible with ELK, Splunk, and other tools
- **Performance** - Fast serialization and parsing

You can switch the log format for development:

```bash
export FAPILOG_OBSERVABILITY__LOGGING__FORMAT=text
```

### How to add custom fields globally?

Use context binding to add fields to all log messages:

```python
from fapilog import get_logger

logger = get_logger()
logger.bind(service_name="user-service", environment="production", version="1.2.3")
logger.info("Application started")
```

### Do I still need log levels?

Yes, log levels are still important for:

- **Filtering** - Show only relevant logs in production
- **Prioritization** - Focus on errors and warnings
- **Compliance** - Meet audit and regulatory requirements
- **Debugging** - Enable detailed logging when needed

```bash
# Set appropriate levels for different environments
export FAPILOG_CORE__LOG_LEVEL=DEBUG    # Development
export FAPILOG_CORE__LOG_LEVEL=INFO     # Production
export FAPILOG_CORE__LOG_LEVEL=WARNING  # Testing
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
    logger = await get_async_logger("worker")

    await logger.info("Processing started", data_id=data.id)

    try:
        result = await process(data)
        await logger.info("Processing completed", result=result)
        return result
    except Exception as e:
        await logger.error("Processing failed", exc_info=True)
        raise
```

### How does context inheritance work?

fapilog stores bound context in a `ContextVar`, which flows to child tasks spawned from the same context. Each request/task should bind its own context:

```python
import asyncio
from fapilog import runtime_async

async def child_task(name, logger):
    await logger.info(f"{name} started")

async def main():
    async with runtime_async() as logger:
        logger.bind(request_id="req-123")
        await asyncio.gather(
            child_task("task1", logger),
            child_task("task2", logger),
        )
        logger.clear_context()  # End-of-request cleanup
```

### What happens if a sink fails?

fapilog handles sink failures gracefully:

- **Retry logic** - Automatic retries for transient failures
- **Circuit breakers** - Prevent cascading failures
- **Fallback behavior** - Continue logging to other sinks
- **Error reporting** - Log sink failures for debugging

```bash
# Configure HTTP sink retry behavior
export FAPILOG_HTTP__RETRY_MAX_ATTEMPTS=3
export FAPILOG_HTTP__RETRY_BACKOFF_SECONDS=0.5
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
export FAPILOG_CORE__MAX_QUEUE_SIZE=65536
export FAPILOG_CORE__BATCH_MAX_SIZE=500
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.1
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=25
```

### What's the memory overhead?

fapilog has minimal memory overhead:

- **Queue size** - Configurable (default: 8KB)
- **Batch processing** - Reduces memory pressure
- **Object pooling** - Reuses objects
- **Garbage collection** - Minimal impact

```bash
# Monitor internal metrics
export FAPILOG_CORE__ENABLE_METRICS=true
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
from fapilog import Settings, get_logger

settings = Settings(
    core__log_level="INFO",
    core__max_queue_size=10000,
    http__endpoint="https://logs.example.com/ingest",
)

logger = get_logger(settings=settings)
```

### How do I configure different environments?

Use environment-specific configuration:

```bash
# Development
export FAPILOG_CORE__LOG_LEVEL=DEBUG
export FAPILOG_OBSERVABILITY__LOGGING__FORMAT=text

# Production
export FAPILOG_CORE__LOG_LEVEL=INFO
export FAPILOG_FILE__DIRECTORY=/var/log/myapp

# Testing
export FAPILOG_CORE__LOG_LEVEL=WARNING
export FAPILOG_CORE__DROP_ON_FULL=true
```

### Can I change configuration at runtime?

Configuration is resolved when you create a logger/runtime. To change settings, construct a new `Settings` object and pass it when you create a new logger; don’t mutate globals in place.

```python
from fapilog import Settings, get_logger

settings = Settings(core__log_level="DEBUG", core__enable_metrics=True)
logger = get_logger(settings=settings)
```

For running apps that need different behavior, create a new logger/runtime with updated settings rather than mutating an existing one.

## Integration Questions

### How do I integrate with FastAPI?

fapilog has built-in FastAPI integration:

```python
from fastapi import FastAPI, Depends
from fapilog import get_async_logger

app = FastAPI()

async def logger_dep():
    return await get_async_logger("request")

@app.get("/users/{user_id}")
async def get_user(user_id: str, logger = Depends(logger_dep)):
    await logger.info("Fetching user", user_id=user_id)
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
ENV FAPILOG_CORE__LOG_LEVEL=INFO
ENV FAPILOG_OBSERVABILITY__LOGGING__FORMAT=json
ENV FAPILOG_CORE__ENABLE_METRICS=false

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
            - name: FAPILOG_CORE__LOG_LEVEL
              value: "INFO"
            - name: FAPILOG_OBSERVABILITY__LOGGING__FORMAT
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

See the {doc}`Contributing Guide <contributing/index>` for details.

---

_Can't find the answer you're looking for? Check the {doc}`Troubleshooting guide <troubleshooting/index>` or ask the community._
