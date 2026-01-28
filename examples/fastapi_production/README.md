# FastAPI Production Template

Production-ready FastAPI application with fapilog structured logging.

## Features

- Structured JSON logging with request correlation
- Health check endpoint (`/health`)
- Prometheus metrics endpoint (`/metrics`)
- Graceful shutdown with log draining
- Error logging with stack traces

## Quick Start

```bash
# Install dependencies
pip install fapilog[fastapi] uvicorn prometheus-client

# Run the application
python -m uvicorn examples.fastapi_production.main:app --reload

# Or run directly
cd examples/fastapi_production
python main.py
```

## Test Endpoints

```bash
# Root endpoint
curl http://localhost:8000/

# Health check
curl http://localhost:8000/health

# Metrics (Prometheus format)
curl http://localhost:8000/metrics

# Trigger error logging
curl http://localhost:8000/error
```

## Production Deployment

See the [Production Checklist](../../docs/user-guide/production-checklist.md) for
complete deployment guidance.

## Customization

Modify `main.py` to:

- Change the preset (`fastapi`, `production`, `serverless`)
- Add custom enrichers or redactors
- Configure additional sinks (CloudWatch, Loki, etc.)
- Adjust middleware settings (sampling, header redaction)

## Middleware Options

```python
app.add_middleware(
    LoggingMiddleware,
    skip_paths=["/health", "/metrics"],  # Skip noisy endpoints
    sample_rate=0.1,                      # Sample 10% of requests
    include_headers=True,                 # Include headers (sensitive redacted)
    log_errors_on_skip=True,              # Still log errors on skipped paths
)
```

## Health Check Details

The `/health` endpoint checks:
- Logger is initialized
- Logger is not drained (still accepting logs)

Returns `200 OK` when healthy, `503 Service Unavailable` when unhealthy.

## Metrics Integration

For full Prometheus integration:

```python
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from fapilog.core.observability import (
    ObservabilitySettings,
    create_metrics_collector_from_settings,
)

metrics = create_metrics_collector_from_settings(
    ObservabilitySettings(metrics={"enabled": True, "exporter": "prometheus"})
)

@app.get("/metrics")
async def metrics_endpoint():
    return Response(
        content=generate_latest(metrics.registry),
        media_type=CONTENT_TYPE_LATEST,
    )
```
