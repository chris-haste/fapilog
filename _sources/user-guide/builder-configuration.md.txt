# Configuring Fapilog with the Builder API

The Builder API provides a fluent, type-safe way to configure fapilog loggers. This guide covers common configuration tasks using the builder pattern.

## Why Use the Builder?

The Builder API offers several advantages over Settings-based configuration:

- **Discoverability** - IDE autocomplete shows all available options
- **Validation** - Configuration errors caught at build time with clear messages
- **Readability** - Configuration intent is clear from chained method calls
- **Type Safety** - Full type hints for all parameters

## Quick Start

```python
from fapilog import LoggerBuilder

# Minimal setup - stdout JSON logging
logger = LoggerBuilder().add_stdout().build()
logger.info("Hello from builder!")

# With preset for sensible defaults
logger = (
    LoggerBuilder()
    .with_preset("production")
    .build()
)
```

For async applications:

```python
from fapilog import AsyncLoggerBuilder

async def main():
    logger = await (
        AsyncLoggerBuilder()
        .with_preset("fastapi")
        .add_stdout()
        .build_async()
    )
    await logger.info("Async logging ready")
```

---

## Common Tasks

### Setting Log Level

Control which messages are logged:

```python
logger = (
    LoggerBuilder()
    .with_level("INFO")  # DEBUG, INFO, WARNING, ERROR
    .add_stdout()
    .build()
)
```

### Adding Multiple Sinks

Send logs to multiple destinations:

```python
logger = (
    LoggerBuilder()
    .add_stdout()                                    # Console output
    .add_file("logs/app", max_bytes="50 MB")        # File rotation
    .add_cloudwatch("/myapp/prod", region="us-east-1")  # CloudWatch
    .build()
)
```

### Configuring File Rotation

Set up rotating file logs with compression:

```python
logger = (
    LoggerBuilder()
    .add_file(
        "logs/app",
        max_bytes="100 MB",    # Rotate at 100 MB
        max_files=10,          # Keep 10 rotated files
        compress=True,         # Gzip old files
    )
    .build()
)
```

### Setting Up Redaction

Protect sensitive data in logs:

```python
# Simple field-based redaction
logger = (
    LoggerBuilder()
    .with_redaction(fields=["password", "api_key", "ssn"])
    .add_stdout()
    .build()
)

# Advanced redaction with patterns
logger = (
    LoggerBuilder()
    .with_field_mask(
        ["password", "credit_card"],
        mask="[REDACTED]",
    )
    .with_regex_mask(["(?i).*secret.*", "(?i).*token.*"])
    .with_url_credential_redaction()  # Scrub user:pass from URLs
    .add_stdout()
    .build()
)
```

### Configuring Sampling

Reduce log volume while maintaining visibility:

```python
# Fixed-rate sampling (keep 10%)
logger = (
    LoggerBuilder()
    .with_sampling(rate=0.1)
    .add_stdout()
    .build()
)

# Adaptive sampling based on volume
logger = (
    LoggerBuilder()
    .with_adaptive_sampling(
        target_events_per_sec=1000,
        min_rate=0.01,
        max_rate=1.0,
    )
    .add_stdout()
    .build()
)

# Trace-aware sampling (honor distributed trace decisions)
logger = (
    LoggerBuilder()
    .with_trace_sampling(default_rate=0.1, honor_upstream=True)
    .add_stdout()
    .build()
)
```

### Rate Limiting

Prevent log flooding:

```python
logger = (
    LoggerBuilder()
    .with_rate_limit(
        capacity=100,        # Bucket size
        refill_rate=10.0,    # Tokens per second
    )
    .add_stdout()
    .build()
)

# Per-key rate limiting
logger = (
    LoggerBuilder()
    .with_rate_limit(
        capacity=10,
        refill_rate=1.0,
        key_field="user_id",  # Separate bucket per user
    )
    .add_stdout()
    .build()
)
```

### Configuring Circuit Breaker

Isolate failing sinks to prevent cascading failures:

```python
logger = (
    LoggerBuilder()
    .with_circuit_breaker(
        enabled=True,
        failure_threshold=5,      # Open after 5 failures
        recovery_timeout="30s",   # Probe after 30 seconds
    )
    .add_cloudwatch("/myapp/prod")
    .build()
)
```

### Level-Based Routing

Send different log levels to different destinations:

```python
logger = (
    LoggerBuilder()
    .add_stdout()
    .add_cloudwatch("/myapp/errors")
    .add_file("logs/debug")
    .with_routing(
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
            {"levels": ["DEBUG"], "sinks": ["rotating_file"]},
            {"levels": ["INFO", "WARNING"], "sinks": ["stdout_json"]},
        ],
        fallback=["stdout_json"],
    )
    .build()
)
```

### Adding Context

Bind default context to all log entries:

```python
logger = (
    LoggerBuilder()
    .with_context(
        service="api-gateway",
        environment="production",
        version="1.2.3",
    )
    .add_stdout()
    .build()
)

# All logs now include service, environment, version
logger.info("Request received")
```

### Configuring Enrichers

Add automatic metadata to logs:

```python
logger = (
    LoggerBuilder()
    .with_enrichers("runtime_info", "context_vars")
    .configure_enricher("runtime_info", service="my-api")
    .add_stdout()
    .build()
)
```

---

## Performance Tuning

### Queue and Batch Configuration

Optimize for throughput or latency:

```python
# High-throughput configuration
logger = (
    LoggerBuilder()
    .with_queue_size(10000)       # Large buffer
    .with_batch_size(500)         # Large batches
    .with_batch_timeout("1s")     # Flush every second
    .with_workers(4)              # Parallel processing
    .add_stdout()
    .build()
)

# Low-latency configuration
logger = (
    LoggerBuilder()
    .with_queue_size(1000)
    .with_batch_size(10)          # Small batches
    .with_batch_timeout("100ms")  # Flush quickly
    .add_stdout()
    .build()
)
```

### Backpressure Configuration

Control behavior when queue is full:

```python
# Drop logs when queue full (default, protects app performance)
logger = (
    LoggerBuilder()
    .with_backpressure(wait_ms=50, drop_on_full=True)
    .add_stdout()
    .build()
)

# Wait for queue space (preserves logs, may slow app)
logger = (
    LoggerBuilder()
    .with_backpressure(wait_ms=100, drop_on_full=False)
    .add_stdout()
    .build()
)
```

### Size Guards

Prevent oversized payloads:

```python
logger = (
    LoggerBuilder()
    .with_size_guard(
        max_bytes="256 KB",
        action="truncate",
        preserve_fields=["level", "timestamp", "message"],
    )
    .add_stdout()
    .build()
)
```

---

## Production Checklist

A complete production configuration:

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    # Start with production preset
    .with_preset("production")

    # Override specific settings
    .with_level("INFO")
    .with_app_name("my-service")

    # Add sinks
    .add_file("logs/app", max_bytes="100 MB", max_files=20, compress=True)
    .add_cloudwatch("/myapp/prod", region="us-east-1")

    # Security
    .with_field_mask(["password", "api_key", "ssn", "credit_card"])
    .with_url_credential_redaction()

    # Reliability
    .with_circuit_breaker(enabled=True, failure_threshold=5)
    .with_backpressure(drop_on_full=False)  # Don't lose logs
    .with_shutdown_timeout("10s")

    # Performance
    .with_queue_size(10000)
    .with_batch_size(100)
    .with_workers(2)

    # Routing (errors to CloudWatch, all to file)
    .with_routing(
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
        ],
        fallback=["rotating_file"],
    )

    # Observability
    .with_metrics(enabled=True)
    .with_diagnostics(enabled=True)

    .build()
)
```

---

## Presets Reference

Presets provide pre-configured defaults for common scenarios:

### `dev` - Local Development

```python
logger = LoggerBuilder().with_preset("dev").build()
```

- DEBUG level for maximum visibility
- Pretty console output in terminals
- Immediate flushing (batch_size=1) for real-time debugging
- No redaction (safe for local testing)
- Internal diagnostics enabled

### `production` - Production Deployments

```python
logger = LoggerBuilder().with_preset("production").build()
```

- INFO level
- File rotation (50MB, 10 files, compressed)
- Automatic redaction of 9 sensitive fields
- `drop_on_full=False` ensures no log loss
- Larger batch size for efficiency

### `fastapi` - FastAPI Applications

```python
logger = await AsyncLoggerBuilder().with_preset("fastapi").build_async()
```

- INFO level
- Container-friendly stdout JSON
- Balanced batch size (50)
- Automatic redaction enabled
- `context_vars` enricher only (reduced overhead)

### `minimal` - Backwards Compatible

```python
logger = LoggerBuilder().with_preset("minimal").build()
```

- Matches `get_logger()` with no arguments
- INFO level, stdout JSON, default batching

---

## Builder vs Settings

| Feature | Builder | Settings |
|---------|---------|----------|
| IDE Autocomplete | Yes | Limited |
| Type Safety | Full | Partial |
| Chaining | Yes | No |
| Runtime Flexibility | At build time | Full runtime |
| Env Var Support | Via preset | Native |
| Serializable Config | No | Yes (JSON/YAML) |

**Use Builder when:**
- Writing new code with IDE support
- Configuration is known at development time
- Readability and discoverability matter

**Use Settings when:**
- Configuration comes from environment/files
- Need runtime configuration changes
- Integrating with config management systems

---

## Next Steps

- [Builder API Reference](../api-reference/builder.md) - Complete method documentation
- [Migration Guide](../guides/settings-to-builder-migration.md) - Convert Settings to Builder
- [Example Configurations](../examples/builder-configurations.md) - Real-world examples
