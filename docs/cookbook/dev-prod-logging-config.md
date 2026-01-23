# One FastAPI logging config for dev + prod (Uvicorn/Gunicorn)

Stop maintaining separate logging configs for each environment. fapilog auto-detects whether you're in development or production and adapts formatting, log levels, and color output automatically.

## The Problem

A typical project starts with something like this:

```python
# config/logging_dev.py
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "pretty"
LOG_COLORS = True

# config/logging_prod.py
LOG_LEVEL = "INFO"
LOG_FORMAT = "json"
LOG_COLORS = False
```

These configurations drift apart over time:
- Someone adds a field to prod logging but forgets dev
- Color codes in production break JSON parsers
- Debug logs flood production when someone forgets to change `LOG_LEVEL`

## The Solution: One Config That Adapts

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

lifespan = setup_logging(preset="fastapi")
app = FastAPI(lifespan=lifespan)
```

This single configuration works everywhere:
- **Local development** (`uvicorn main:app --reload`): Pretty format, DEBUG level, colors enabled
- **Production** (Gunicorn workers): JSON format, INFO level, no colors

No environment-specific config files. No conditional imports. Just one line.

## What Changes Per Environment

fapilog detects your environment and adjusts defaults accordingly:

| Setting | Development (TTY) | Production (no TTY) |
|---------|------------------|---------------------|
| Format | Pretty (human-readable) | JSON (machine-parseable) |
| Level | DEBUG | INFO |
| Colors | Yes | No |

### How Detection Works

fapilog uses multiple signals to determine the environment:

1. **TTY detection**: Is stdout connected to a terminal?
   - Yes → Development defaults (pretty format, DEBUG)
   - No → Production defaults (JSON format, INFO)

2. **CI detection**: Common CI environment variables (`CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, etc.)
   - Present → Forces INFO level, no colors

3. **Container detection**: Docker, Kubernetes, Lambda
   - Detected → Production-appropriate defaults

The priority order ensures containers and CI always get production behavior, while local terminals get developer-friendly output.

## Running in Different Environments

### Local Development (Uvicorn)

```bash
uvicorn main:app --reload
```

Output is pretty-printed with colors:

```
2026-01-21 10:30:00 INFO  Processing order order_id=12345 request_id=abc-123
```

### Production (Gunicorn)

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

Output is JSON (no colors):

```json
{"timestamp": "2026-01-21T10:30:00.123Z", "level": "INFO", "message": "Processing order", "order_id": "12345", "request_id": "abc-123"}
```

### Docker

```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Automatic JSON format—Docker containers don't have TTYs.

## Overriding Defaults

Sometimes you need to force specific behavior regardless of environment.

### Environment Variable Overrides

```bash
# Force DEBUG in production (temporary debugging)
export FAPILOG_CORE__LOG_LEVEL=DEBUG

# Force JSON in development (testing log aggregation locally)
export FAPILOG_CORE__SINKS='["stdout_json"]'
```

### Programmatic Overrides

```python
from fapilog.fastapi import setup_logging

# Always use JSON, even in development
lifespan = setup_logging(
    preset="fastapi",
    sinks=["stdout_json"],
)

# Always DEBUG, even in production (not recommended)
lifespan = setup_logging(
    preset="fastapi",
    log_level="DEBUG",
)
```

### Testing JSON Output Locally

To verify your JSON output before deploying:

```bash
# Pipe through jq to validate JSON
uvicorn main:app 2>&1 | jq .
```

Or force JSON format in code:

```python
from fapilog import get_async_logger

async def main():
    logger = await get_async_logger(format="json")
    await logger.info("Testing JSON output")
```

## Complete Example

```python
from fastapi import FastAPI, Depends
from fapilog.fastapi import setup_logging, get_request_logger

# One line - works everywhere
lifespan = setup_logging(preset="fastapi")
app = FastAPI(lifespan=lifespan)

@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, logger=Depends(get_request_logger)):
    await logger.info("Processing order", order_id=order_id)
    return {"order_id": order_id, "status": "shipped"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Run locally:
```bash
python main.py  # Pretty output, DEBUG level
```

Run in production:
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker  # JSON output, INFO level
```

## Going Deeper

- [FastAPI JSON Logging](fastapi-json-logging.md) - Detailed JSON output configuration
- [Environment Variables](../user-guide/environment-variables.md) - All configuration options
- [Configuration](../user-guide/configuration.md) - Settings hierarchy and precedence
- [Why Fapilog?](../why-fapilog.md) - How fapilog compares to other logging libraries
