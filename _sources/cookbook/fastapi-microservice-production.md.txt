# FastAPI Microservices in Production

Production microservices need logging that handles Kubernetes probes, containerized deployments, traffic spikes, and observability pipelines. This guide covers the optimal fapilog configuration for containerized FastAPI services.

## Quick Start

The recommended configuration for most production microservices:

```python
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .skip_paths(["/health", "/healthz", "/ready", "/live", "/metrics"])
        .include_headers(["content-type", "accept", "user-agent", "x-request-id"])
        .build()
)
```

This configuration:
- Uses the optimized `fastapi` preset (2 workers, JSON output, credential redaction)
- Skips Kubernetes probes and Prometheus metrics
- Logs only safe headers via allowlist (no accidental credential leaks)

## Preset Selection

Choose based on your traffic patterns and deployment environment:

| Preset | Best For | Key Features |
|--------|----------|--------------|
| `fastapi` | Most microservices | Balanced throughput, JSON output, credential redaction |
| `high-volume` | >1000 req/sec | Adaptive sampling, drops for latency |
| `serverless` | Cloud Run, Lambda | Smaller batches, fast drain, drop-tolerant |
| `production-latency` | Latency-critical APIs | Drops over blocking, no file I/O |

### Standard Microservice (100-1000 req/sec)

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .skip_paths(["/health", "/healthz", "/ready", "/live", "/metrics"])
        .build()
)
```

### High-Volume Service (>1000 req/sec)

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("high-volume")  # Adaptive sampling kicks in
        .skip_paths(["/health", "/healthz", "/ready", "/live", "/metrics"])
        .build()
)
```

The `high-volume` preset automatically samples down during traffic spikes while always logging errors. See [Adaptive Sampling](adaptive-sampling-high-volume.md) for details.

### Environment-Based Selection

```python
import os
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder

PRESET = os.getenv("FAPILOG_PRESET", "fastapi")

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset(PRESET)
        .skip_paths(["/health", "/healthz", "/ready", "/live", "/metrics"])
        .build()
)
```

Set via environment:
```bash
# Development
FAPILOG_PRESET=dev

# Standard production
FAPILOG_PRESET=fastapi

# High-traffic periods
FAPILOG_PRESET=high-volume
```

## Kubernetes Deployments

### Probe Configuration

Kubernetes uses multiple probe endpoints. Skip all of them:

```python
KUBERNETES_PROBES = [
    "/health",
    "/healthz",
    "/ready",
    "/readiness",
    "/live",
    "/livez",
    "/startup",
]

OBSERVABILITY_PATHS = [
    "/metrics",      # Prometheus
    "/metrics/",
]

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .skip_paths(KUBERNETES_PROBES + OBSERVABILITY_PATHS)
        .build()
)
```

### Resource-Aware Configuration

Match fapilog's buffer sizes to your container limits:

```python
from fapilog import LoggerBuilder

# For memory-constrained pods (256-512MB)
logger = (
    LoggerBuilder()
    .with_preset("fastapi")
    .with_batch_size(25)      # Smaller batches
    .with_queue_size(1000)    # Limit memory usage
    .build()
)

# For larger pods (1GB+)
logger = (
    LoggerBuilder()
    .with_preset("fastapi")
    .with_batch_size(100)
    .with_queue_size(10000)
    .build()
)
```

### Graceful Shutdown

fapilog drains automatically during lifespan shutdown. Ensure your `terminationGracePeriodSeconds` allows time for log flushing:

```yaml
# kubernetes deployment
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 30  # Allow time for drain
      containers:
        - name: app
          lifecycle:
            preStop:
              exec:
                command: ["sleep", "5"]  # Allow in-flight requests
```

The `FastAPIBuilder` lifespan handles drain automatically:
```python
# No manual drain needed - handled by lifespan
app = FastAPI(lifespan=FastAPIBuilder().with_preset("fastapi").build())
```

## Serverless Containers

### Google Cloud Run

Cloud Run captures stdout automatically. Use the `serverless` preset for optimal cold-start behavior:

```python
from fastapi import FastAPI
from fapilog.fastapi import FastAPIBuilder

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("serverless")  # Smaller batches, fast drain
        .skip_paths(["/health", "/_ah/health"])  # Cloud Run health checks
        .build()
)
```

#### Cloud Logging Integration

Cloud Run parses JSON logs with specific fields. fapilog's JSON output is compatible:

```python
# Logs appear in Cloud Logging with:
# - severity: mapped from log level
# - message: log message
# - All metadata fields: searchable as jsonPayload.*
```

For explicit severity mapping (optional):

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("serverless")
    .add_stdout_json(
        level_key="severity",  # Cloud Logging expects "severity"
    )
    .build()
)
```

### AWS Fargate / ECS

Fargate captures stdout to CloudWatch. Configure the awslogs driver:

```json
{
  "containerDefinitions": [{
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/my-service",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
```

fapilog configuration:

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("serverless")
        .skip_paths(["/health", "/"])  # ALB health check path
        .build()
)
```

#### Direct CloudWatch Integration

For direct CloudWatch writes (bypassing stdout):

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("serverless")
    .add_cloudwatch(
        log_group="/ecs/my-service",
        log_stream="app",
        region="us-east-1",
    )
    .build()
)
```

### AWS Lambda

Lambda requires aggressive draining before the handler returns:

```python
from fapilog import get_async_logger
from mangum import Mangum

app = FastAPI()

@app.get("/")
async def root():
    logger = await get_async_logger("lambda", preset="serverless")
    await logger.info("request processed")
    return {"ok": True}

# Mangum adapter for Lambda
handler = Mangum(app, lifespan="off")
```

For proper lifespan support with Lambda, use explicit drain:

```python
import asyncio
from fapilog import get_async_logger

async def lambda_handler(event, context):
    logger = await get_async_logger("lambda", preset="serverless")
    try:
        await logger.info("processing", event_type=event.get("type"))
        # ... your logic ...
        return {"statusCode": 200}
    finally:
        await logger.drain()  # Critical: drain before Lambda freezes
```

### Azure Container Apps

Similar to Cloud Run, Azure captures stdout:

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("serverless")
        .skip_paths(["/health", "/liveness", "/readiness"])
        .build()
)
```

## Header Logging Strategies

### Allowlist (Recommended)

Log only known-safe headers:

```python
app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .include_headers([
            "content-type",
            "accept",
            "user-agent",
            "x-request-id",
            "x-correlation-id",
            "x-forwarded-for",
        ])
        .build()
)
```

Benefits:
- New headers don't accidentally leak
- Smaller log payloads
- No surprises from third-party middleware adding headers

### Redaction (When You Need More Headers)

When you need most headers but must redact sensitive ones, use the middleware directly:

```python
from fapilog.fastapi import FastAPIBuilder
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI(
    lifespan=FastAPIBuilder()
        .with_preset("fastapi")
        .build()
)
app.add_middleware(
    LoggingMiddleware,
    include_headers=True,
    additional_redact_headers=[
        "x-api-key",
        "x-internal-token",
        "x-session-id",
    ],
)
```

Default redactions (always applied):
- `authorization`, `proxy-authorization`
- `cookie`, `set-cookie`
- `x-api-key`, `x-auth-token`, `x-csrf-token`

## Observability Integration

### Grafana Loki

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("fastapi")
    .add_loki(
        url="http://loki:3100/loki/api/v1/push",
        labels={"app": "my-service", "env": "production"},
    )
    .add_stdout_json()  # Keep stdout for container logs
    .build()
)
```

### AWS CloudWatch

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("fastapi")
    .add_cloudwatch(
        log_group="/app/my-service",
        log_stream="production",
        region="us-east-1",
    )
    .build()
)
```

### Datadog

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("fastapi")
    .add_stdout_json(
        # Datadog-compatible fields
        extra_fields={
            "ddsource": "python",
            "service": "my-service",
        }
    )
    .build()
)
```

Datadog Agent picks up JSON logs from stdout when configured with `logs_enabled: true`.

## Complete Production Example

```python
import os
from fastapi import FastAPI, Depends
from fapilog.fastapi import FastAPIBuilder, get_request_logger

# Configuration from environment
PRESET = os.getenv("FAPILOG_PRESET", "fastapi")
SKIP_PATHS = [
    "/health", "/healthz",
    "/ready", "/readiness",
    "/live", "/livez",
    "/metrics",
]
ALLOWED_HEADERS = [
    "content-type", "accept", "user-agent",
    "x-request-id", "x-correlation-id", "x-forwarded-for",
]

app = FastAPI(
    title="My Microservice",
    lifespan=FastAPIBuilder()
        .with_preset(PRESET)
        .skip_paths(SKIP_PATHS)
        .include_headers(ALLOWED_HEADERS)
        .build()
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/users/{user_id}")
async def get_user(user_id: int, logger=Depends(get_request_logger)):
    await logger.info("fetching user", user_id=user_id)
    return {"user_id": user_id, "name": "Example User"}
```

## Troubleshooting

### Logs Not Appearing in Cloud Provider

1. **Check stdout**: Ensure logs reach stdout: `docker logs <container>`
2. **JSON format**: Cloud providers parse JSON better than plain text
3. **Log driver**: Verify container log driver configuration

### High Memory Usage

Reduce buffer sizes:
```python
logger = LoggerBuilder().with_preset("fastapi").with_queue_size(500).build()
```

### Slow Shutdown

fapilog waits up to 5 seconds for drain by default. For faster shutdown:
```python
# In your shutdown handler
await logger.drain(timeout=2.0)
```

### Missing Request Context

Ensure middleware order is correct (handled automatically by `FastAPIBuilder`):
```python
# RequestContextMiddleware must come BEFORE LoggingMiddleware
# FastAPIBuilder handles this automatically
```

## Going Deeper

- [Skipping Health Endpoints](skip-noisy-endpoints.md) - Detailed path filtering
- [Adaptive Sampling](adaptive-sampling-high-volume.md) - High-volume traffic handling
- [Graceful Shutdown](graceful-shutdown-flush.md) - Drain patterns
- [FastAPI Integration Guide](../user-guide/fastapi.md) - Complete middleware reference
