# Builder Configuration Examples

Real-world configuration patterns using the Builder API.

## Local Development

Optimized for debugging with immediate output and full visibility:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("dev")  # DEBUG level, pretty output, immediate flush
    .with_diagnostics(enabled=True)  # Show internal diagnostics
    .build()
)

# Or build from scratch:
logger = (
    LoggerBuilder()
    .with_level("DEBUG")
    .add_stdout(format="pretty")  # Human-readable output
    .with_batch_size(1)  # Immediate flush for debugging
    .with_diagnostics(enabled=True)
    .build()
)
```

---

## Production with CloudWatch

Standard production setup with AWS CloudWatch for centralized logging:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_app_name("my-service")
    .with_level("INFO")

    # CloudWatch for centralized logs
    .add_cloudwatch(
        "/myapp/prod",
        region="us-east-1",
        batch_size=200,
        batch_timeout="5s",
    )

    # Local file backup
    .add_file(
        "logs/app",
        max_bytes="100 MB",
        max_files=10,
        compress=True,
    )

    # Reliability
    .with_circuit_breaker(enabled=True, failure_threshold=5)
    .with_backpressure(drop_on_full=False)
    .with_shutdown_timeout("10s")

    # Performance (2 workers = ~30x throughput vs default)
    .with_queue_size(10000)
    .with_workers(2)  # Note: production preset defaults to 2 workers

    .build()
)
```

---

## Multi-Sink with Level Routing

Route errors to CloudWatch while keeping all logs in files:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("DEBUG")
    .with_app_name("api-gateway")

    # Define all sinks
    .add_stdout()  # For container stdout
    .add_cloudwatch("/myapp/errors", region="us-east-1")
    .add_file("logs/app", max_bytes="50 MB", max_files=20)

    # Route by level
    .with_routing(
        rules=[
            # Errors go to CloudWatch for alerting
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
            # Debug logs only to file (not stdout)
            {"levels": ["DEBUG"], "sinks": ["rotating_file"]},
            # Info/Warning to stdout for container logs
            {"levels": ["INFO", "WARNING"], "sinks": ["stdout_json"]},
        ],
        # Everything also goes to file
        fallback=["rotating_file"],
        overlap=True,  # Allow events to match multiple rules
    )

    .build()
)
```

---

## High-Throughput with Sampling

Handle high log volume with adaptive sampling:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .with_app_name("high-volume-service")

    # Adaptive sampling based on volume
    .with_adaptive_sampling(
        target_events_per_sec=1000,  # Target 1000 events/sec
        min_rate=0.01,  # Never go below 1%
        max_rate=1.0,   # Keep all when volume is low
        window_seconds=60,
    )

    # Rate limiting as safety net
    .with_rate_limit(
        capacity=5000,
        refill_rate=1000.0,
        overflow_action="drop",
    )

    # Performance tuning
    .with_queue_size(50000)
    .with_batch_size(500)
    .with_batch_timeout("500ms")
    .with_workers(4)
    .with_parallel_sink_writes(True)

    # Size guard for large payloads
    .with_size_guard(max_bytes="256 KB", action="truncate")

    .add_stdout()
    .build()
)
```

---

## Compliance-Ready with Full Redaction

HIPAA/PCI-DSS compliant logging with comprehensive redaction:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_app_name("healthcare-api")
    .with_level("INFO")

    # Comprehensive field redaction
    .with_field_mask(
        [
            # PII
            "ssn", "social_security", "date_of_birth", "dob",
            # Financial
            "credit_card", "card_number", "cvv", "account_number",
            # Authentication
            "password", "api_key", "token", "secret",
            "authorization", "bearer", "jwt",
            # Healthcare specific
            "patient_id", "medical_record", "diagnosis",
        ],
        mask="[REDACTED]",
        block_on_failure=True,  # Block if redaction fails
    )

    # Regex patterns for dynamic field names
    .with_regex_mask([
        r"(?i).*password.*",
        r"(?i).*secret.*",
        r"(?i).*token.*",
        r"(?i).*ssn.*",
        r"(?i).*credit.*card.*",
    ])

    # URL credential scrubbing
    .with_url_credential_redaction(max_string_length=8192)

    # Strict redaction guardrails
    .with_redaction_guardrails(max_depth=10, max_keys=10000)

    # Sinks
    .add_file(
        "logs/audit",
        max_bytes="100 MB",
        max_files=365,  # Keep a year of logs
        compress=True,
    )
    .add_cloudwatch("/healthcare/audit", region="us-east-1")

    # No log loss for compliance
    .with_backpressure(drop_on_full=False)

    .build()
)
```

---

## FastAPI Application

Async logger optimized for FastAPI:

```python
from fapilog import AsyncLoggerBuilder

async def create_logger():
    return await (
        AsyncLoggerBuilder()
        .with_preset("fastapi")
        .with_app_name("api-service")

        # Context for all requests
        .with_context(
            service="api-service",
            version="1.2.3",
        )

        # Enrichers for request context
        .with_enrichers("context_vars")

        # Redaction for API security
        .with_field_mask(["password", "api_key", "authorization"])
        .with_url_credential_redaction()

        # Performance for async
        .with_queue_size(5000)
        .with_batch_size(50)
        .with_batch_timeout("200ms")

        .add_stdout()
        .build_async()
    )

# In FastAPI lifespan:
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.logger = await create_logger()
    yield
    await app.state.logger.drain()

app = FastAPI(lifespan=lifespan)
```

---

## Grafana Loki Integration

Send logs to Grafana Loki for centralized observability:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .with_app_name("microservice")

    # Loki sink
    .add_loki(
        "http://loki:3100",
        tenant_id="my-org",
        labels={
            "env": "production",
            "service": "api",
            "team": "platform",
        },
        label_keys=["level", "logger"],  # Promote to Loki labels
        batch_size=100,
        batch_timeout="5s",
    )

    # Also log to stdout for container logs
    .add_stdout()

    # Circuit breaker for Loki failures
    .with_circuit_breaker(enabled=True, failure_threshold=3)

    .build()
)
```

---

## PostgreSQL Audit Logs

Store structured logs in PostgreSQL for querying:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .with_app_name("audit-service")

    # PostgreSQL sink
    .add_postgres(
        host="db.example.com",
        port=5432,
        database="audit_logs",
        user="logger",
        password="secure-password",
        table="application_logs",
        schema="audit",

        # Performance
        batch_size=100,
        batch_timeout="5s",
        min_pool=2,
        max_pool=10,

        # Schema options
        use_jsonb=True,  # JSONB for flexible querying
        extract_fields=["level", "logger", "user_id", "request_id"],
    )

    # Stdout backup
    .add_stdout()

    .with_circuit_breaker(enabled=True, failure_threshold=5)

    .build()
)
```

---

## Webhook Alerts

Send critical logs to a webhook for alerting:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")

    # Main logging
    .add_stdout()
    .add_file("logs/app", max_bytes="50 MB")

    # Webhook for alerts
    .add_webhook(
        "https://alerts.example.com/webhook",
        secret="signing-secret-key",
        timeout="5s",
        headers={"X-Source": "my-service"},
    )

    # Route only errors to webhook
    .with_routing(
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["webhook"]},
        ],
        fallback=["stdout_json", "rotating_file"],
    )

    .build()
)
```

---

## Kubernetes Deployment

Container-friendly configuration for Kubernetes:

```python
from fapilog import LoggerBuilder
import os

logger = (
    LoggerBuilder()
    .with_level(os.getenv("LOG_LEVEL", "INFO"))
    .with_app_name(os.getenv("APP_NAME", "unknown"))

    # Context from K8s environment
    .with_context(
        pod=os.getenv("POD_NAME", "unknown"),
        namespace=os.getenv("POD_NAMESPACE", "default"),
        node=os.getenv("NODE_NAME", "unknown"),
    )

    # Enrichers
    .with_enrichers("runtime_info", "context_vars")

    # JSON stdout for log aggregators (Fluentd, Fluent Bit)
    .add_stdout()

    # Redaction
    .with_field_mask(["password", "api_key", "token"])

    # Performance for ephemeral containers
    .with_queue_size(5000)
    .with_batch_timeout("500ms")
    .with_shutdown_timeout("5s")  # Fast shutdown for rolling updates

    .build()
)
```

---

## Testing Configuration

Minimal configuration for unit tests:

```python
from fapilog import LoggerBuilder

def create_test_logger():
    """Logger for unit tests - immediate flush, no external sinks."""
    return (
        LoggerBuilder()
        .with_level("DEBUG")
        .add_stdout(format="pretty")
        .with_batch_size(1)  # Immediate flush
        .with_queue_size(100)  # Small queue
        .build()
    )

# Or capture logs for assertions:
from io import StringIO
import json

def create_capturing_logger():
    """Logger that captures output for test assertions."""
    return (
        LoggerBuilder()
        .with_level("DEBUG")
        .add_stdout()  # JSON for parsing
        .with_batch_size(1)
        .build()
    )
```

---

## Microservice Template

Complete template for microservice logging:

```python
from fapilog import LoggerBuilder, AsyncLoggerBuilder
import os

def create_service_logger(
    service_name: str,
    *,
    async_mode: bool = False,
    cloudwatch_group: str | None = None,
):
    """Factory for consistent service logging configuration."""

    env = os.getenv("ENV", "development")
    is_production = env == "production"

    builder_class = AsyncLoggerBuilder if async_mode else LoggerBuilder
    builder = builder_class()

    # Base configuration
    builder = (
        builder
        .with_preset("production" if is_production else "dev")
        .with_app_name(service_name)
        .with_context(
            service=service_name,
            environment=env,
            version=os.getenv("APP_VERSION", "unknown"),
        )
    )

    # Production additions
    if is_production:
        builder = (
            builder
            .with_field_mask(["password", "api_key", "token", "secret"])
            .with_url_credential_redaction()
            .with_circuit_breaker(enabled=True)
            .with_backpressure(drop_on_full=False)
            .with_metrics(enabled=True)
        )

        # Optional CloudWatch
        if cloudwatch_group:
            builder = builder.add_cloudwatch(
                cloudwatch_group,
                region=os.getenv("AWS_REGION", "us-east-1"),
            )

    # Build
    if async_mode:
        return builder  # Caller must await .build_async()
    return builder.build()

# Usage:
logger = create_service_logger("user-service")

# Async:
# logger = await create_service_logger("user-service", async_mode=True).build_async()
```
