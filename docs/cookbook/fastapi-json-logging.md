# FastAPI JSON logging to stdout (Uvicorn access logs included)

Container platforms like Docker, Kubernetes, and AWS ECS expect structured JSON logs on stdout. Without consistent formatting, log aggregation systems (CloudWatch, Datadog, ELK) can't parse your logs reliably.

## The Problem

A typical FastAPI application produces two distinct log streams:

**Application logs** (your code):
```
INFO:     Processing order 12345
```

**Uvicorn access logs** (HTTP requests):
```
INFO:     127.0.0.1:52486 - "GET /api/orders HTTP/1.1" 200 OK
```

These plain text formats cause problems:

1. **Inconsistent structure** - App logs and access logs have different formats
2. **Color codes** - Uvicorn adds ANSI escape sequences that break JSON parsers
3. **No machine-readable fields** - Can't filter by status code, latency, or request ID

## The Solution

fapilog provides unified JSON output for both application and access logs:

```python
from fastapi import FastAPI, Depends
from fapilog.fastapi import setup_logging, get_request_logger

lifespan = setup_logging(preset="fastapi")
app = FastAPI(lifespan=lifespan)

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, logger=Depends(get_request_logger)):
    await logger.info("Processing order", order_id=order_id)
    return {"order_id": order_id, "status": "shipped"}
```

The `preset="fastapi"` configuration:
- Outputs JSON to stdout (no files)
- Disables color codes
- Includes request context (request_id) automatically
- Masks sensitive fields (passwords, API keys, tokens)

## Sample Output

**Application log:**
```json
{"timestamp": "2026-01-21T10:30:00.123Z", "level": "INFO", "message": "Processing order", "order_id": "12345", "request_id": "550e8400-e29b-41d4-a716-446655440000"}
```

**Access log:**
```json
{"timestamp": "2026-01-21T10:30:00.456Z", "level": "INFO", "message": "HTTP request", "method": "GET", "path": "/api/orders/12345", "status_code": 200, "duration_ms": 15.2, "request_id": "550e8400-e29b-41d4-a716-446655440000"}
```

Both share consistent field names (`timestamp`, `level`, `message`, `request_id`), making log aggregation straightforward.

## Including Uvicorn Access Logs

fapilog's `setup_logging()` automatically installs middleware that captures HTTP requests. The `LoggingMiddleware` handles:

- Request method, path, and query parameters
- Response status codes
- Request duration
- Client IP address
- Request ID correlation

No additional Uvicorn configuration is needed. The default Uvicorn access log is effectively replaced by fapilog's structured output.

### Disabling Default Uvicorn Logs

If you want to suppress Uvicorn's default access logging entirely (recommended to avoid duplicate logs), configure Uvicorn:

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        access_log=False,  # Disable Uvicorn's access log
    )
```

Or via CLI:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --no-access-log
```

## Docker Configuration

A minimal Dockerfile for JSON logging:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use --no-access-log to avoid duplicate access logs
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
```

### Docker Compose

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FAPILOG_CORE__LOG_LEVEL=INFO
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## Explicit Format Control

If you're not using the FastAPI integration but still want JSON output:

```python
from fapilog import get_async_logger

async def main():
    # format="json" ensures JSON output regardless of environment
    logger = await get_async_logger(format="json")
    await logger.info("Starting service", version="1.0.0")
```

For automatic format detection (JSON in containers, pretty in terminals):

```python
logger = await get_async_logger(format="auto")
```

## Going Deeper

- [FastAPI request_id Logging](fastapi-request-id-logging.md) - Correlation ID middleware
- [Context Enrichment](../user-guide/context-enrichment.md) - Adding custom fields to all logs
- [Redaction](../redaction/index.md) - Masking sensitive data
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
