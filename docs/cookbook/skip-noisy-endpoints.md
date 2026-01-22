# Skipping health/metrics endpoints (noise reduction)

Health checks and readiness probes run every few seconds. With 12 replicas and a 5-second interval, that's 17,000 log entries per day per endpoint—before a single real request. This noise buries actual traffic and inflates log storage costs.

fapilog's path filtering skips these endpoints while logging everything else.

## The Problem

A typical Kubernetes deployment generates massive log volume from health checks:

```
# Per instance, per endpoint
1 check × 12 checks/minute × 60 minutes × 24 hours = 17,280 logs/day

# With 10 instances and 3 health endpoints (/health, /ready, /metrics)
17,280 × 10 × 3 = 518,400 logs/day
```

These logs are identical, contain no useful information, and obscure the logs that matter—actual user requests, errors, and business events.

## The Solution

Skip health endpoints with `skip_paths`:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging

lifespan = setup_logging(
    skip_paths=[
        "/health",
        "/healthz",
        "/ready",
        "/readiness",
        "/metrics",
        "/ping",
    ],
)
app = FastAPI(lifespan=lifespan)
```

Requests to these paths are processed normally—they just don't generate log entries.

## Common Patterns to Skip

| Pattern | Used By | Purpose |
|---------|---------|---------|
| `/health`, `/healthz` | Kubernetes, AWS ALB | Liveness checks |
| `/ready`, `/readiness` | Kubernetes | Readiness probes |
| `/metrics` | Prometheus | Metrics scraping |
| `/ping` | Load balancers, uptime monitors | Basic availability |
| `/livez` | Kubernetes (newer) | Liveness (alternative) |

### Kubernetes-Focused Setup

```python
lifespan = setup_logging(
    skip_paths=["/health", "/healthz", "/ready", "/readiness", "/livez"],
)
```

### AWS / Generic Load Balancer Setup

```python
lifespan = setup_logging(
    skip_paths=["/health", "/ping", "/_health"],
)
```

## Pattern Matching Syntax

`skip_paths` uses exact string matching:

| Path in Request | `skip_paths=["/health"]` | Logged? |
|-----------------|--------------------------|---------|
| `/health` | Match | No |
| `/health/` | No match | Yes |
| `/health/db` | No match | Yes |
| `/healthz` | No match | Yes |
| `/api/health` | No match | Yes |

This means:

- **Case-sensitive**: `/Health` and `/health` are different
- **No wildcards**: `/health/*` won't match anything (it's a literal string)
- **No regex**: Use exact paths only
- **Trailing slashes matter**: Include both `/health` and `/health/` if your API accepts both

### Complete Health Check Coverage

If your endpoints accept trailing slashes or subpaths, list each variant:

```python
lifespan = setup_logging(
    skip_paths=[
        "/health",
        "/health/",
        "/ready",
        "/ready/",
        "/metrics",
    ],
)
```

## Manual Middleware Configuration

If you need more control, configure the middleware directly:

```python
from fastapi import FastAPI
from fapilog.fastapi.logging import LoggingMiddleware
from fapilog.fastapi.context import RequestContextMiddleware

app = FastAPI()

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    LoggingMiddleware,
    skip_paths=["/health", "/metrics"],
)
```

This gives identical behavior to `setup_logging(skip_paths=...)`.

## Impact on Log Volume

Skipping health endpoints typically reduces log volume by 50-90%, depending on:

- **Check frequency**: 5-second intervals generate more than 30-second intervals
- **Number of instances**: More replicas = more health checks
- **Number of health endpoints**: Some setups have 3-5 different health paths
- **Actual traffic**: Low-traffic services see the biggest percentage reduction

### Before and After

| Metric | Before | After (with skip_paths) |
|--------|--------|------------------------|
| Logs per day (10 instances) | 520,000 | 52,000 |
| Storage cost | $15/month | $1.50/month |
| Time to find errors | Minutes | Seconds |

The real benefit isn't just cost—it's signal-to-noise ratio. When health checks are 90% of your logs, finding an actual error requires wading through noise.

## Errors Still Get Logged

`skip_paths` only suppresses successful request completion logs. If a health endpoint returns an error (5xx status), it's still logged:

```python
@app.get("/health")
async def health():
    if not db.is_connected():
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
```

When the database is down, you'll see `request_failed` logs for `/health` even though successful health checks are skipped. This ensures you catch infrastructure issues without drowning in routine checks.

## Combining with Sampling

For high-traffic endpoints that aren't health checks, combine path filtering with sampling:

```python
lifespan = setup_logging(
    skip_paths=["/health", "/metrics"],  # Skip entirely
    sample_rate=0.1,                      # Log 10% of other requests
)
```

This setup:
- Never logs `/health` or `/metrics`
- Logs 10% of all other successful requests
- Always logs errors (sample_rate doesn't affect error logs)

## Going Deeper

- [FastAPI Integration Guide](../user-guide/fastapi.md) - Complete middleware options
- [Log Sampling](../cookbook/non-blocking-async-logging.md) - Rate limiting and backpressure
