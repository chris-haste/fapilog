# Migrating from Settings to Builder

This guide helps you convert existing Settings-based configurations to the Builder API.

## When to Migrate

**Migrate to Builder when:**
- Starting a new project or feature
- Refactoring existing configuration code
- Want better IDE support and discoverability
- Configuration is defined in Python code

**Keep Settings when:**
- Configuration is entirely environment-variable driven
- Need runtime configuration changes after logger creation
- Integrating with external config management systems (Consul, etc.)
- Configuration is loaded from JSON/YAML files

---

## Quick Conversion Reference

### Core Settings

| Settings Pattern | Builder Pattern |
|------------------|-----------------|
| `CoreSettings(log_level="INFO")` | `.with_level("INFO")` |
| `CoreSettings(app_name="my-app")` | `.with_app_name("my-app")` |
| `CoreSettings(max_queue_size=10000)` | `.with_queue_size(10000)` |
| `CoreSettings(batch_max_size=100)` | `.with_batch_size(100)` |
| `CoreSettings(batch_timeout_seconds=1.0)` | `.with_batch_timeout("1s")` |
| `CoreSettings(worker_count=4)` | `.with_workers(4)` |
| `CoreSettings(shutdown_timeout_seconds=5.0)` | `.with_shutdown_timeout("5s")` |
| `CoreSettings(backpressure_wait_ms=50)` | `.with_backpressure(wait_ms=50)` |
| `CoreSettings(drop_on_full=False)` | `.with_backpressure(drop_on_full=False)` |
| `CoreSettings(enable_metrics=True)` | `.with_metrics(enabled=True)` |
| `CoreSettings(sink_parallel_writes=True)` | `.with_parallel_sink_writes(True)` |

### Circuit Breaker

| Settings Pattern | Builder Pattern |
|------------------|-----------------|
| `CoreSettings(sink_circuit_breaker_enabled=True)` | `.with_circuit_breaker(enabled=True)` |
| `CoreSettings(sink_circuit_breaker_failure_threshold=5)` | `.with_circuit_breaker(failure_threshold=5)` |
| `CoreSettings(sink_circuit_breaker_recovery_timeout_seconds=30)` | `.with_circuit_breaker(recovery_timeout="30s")` |

### Sinks

| Settings Pattern | Builder Pattern |
|------------------|-----------------|
| `CoreSettings(sinks=["stdout_json"])` | `.add_stdout()` |
| `CoreSettings(sinks=["stdout_pretty"])` | `.add_stdout(format="pretty")` |
| `CoreSettings(sinks=["rotating_file"])` + config | `.add_file(directory, ...)` |
| `CoreSettings(sinks=["http"])` + config | `.add_http(endpoint, ...)` |
| `CoreSettings(sinks=["webhook"])` + config | `.add_webhook(endpoint, ...)` |
| `CoreSettings(sinks=["cloudwatch"])` + config | `.add_cloudwatch(log_group, ...)` |
| `CoreSettings(sinks=["loki"])` + config | `.add_loki(url, ...)` |
| `CoreSettings(sinks=["postgres"])` + config | `.add_postgres(...)` |

### Filters

| Settings Pattern | Builder Pattern |
|------------------|-----------------|
| `CoreSettings(filters=["sampling"])` + config | `.with_sampling(rate=0.1)` |
| `CoreSettings(filters=["adaptive_sampling"])` + config | `.with_adaptive_sampling(...)` |
| `CoreSettings(filters=["trace_sampling"])` + config | `.with_trace_sampling(...)` |
| `CoreSettings(filters=["rate_limit"])` + config | `.with_rate_limit(...)` |
| `CoreSettings(filters=["first_occurrence"])` + config | `.with_first_occurrence(...)` |

### Redaction

| Settings Pattern | Builder Pattern |
|------------------|-----------------|
| `CoreSettings(redactors=["field_mask"])` + config | `.with_field_mask(fields, ...)` |
| `CoreSettings(redactors=["regex_mask"])` + config | `.with_regex_mask(patterns, ...)` |
| `CoreSettings(redactors=["url_credentials"])` | `.with_url_credential_redaction()` |

### Enrichers

| Settings Pattern | Builder Pattern |
|------------------|-----------------|
| `CoreSettings(enrichers=["runtime_info", "context_vars"])` | `.with_enrichers("runtime_info", "context_vars")` |
| `CoreSettings(default_bound_context={...})` | `.with_context(key=value, ...)` |

---

## Step-by-Step Migration

### Example 1: Basic Configuration

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import CoreSettings

settings = Settings(
    core=CoreSettings(
        log_level="INFO",
        sinks=["stdout_json"],
    )
)
logger = get_logger(name="app", settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_name("app")
    .with_level("INFO")
    .add_stdout()
    .build()
)
```

---

### Example 2: File Sink with Rotation

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import CoreSettings, SinkConfig, RotatingFileSinkSettings

settings = Settings(
    core=CoreSettings(
        log_level="INFO",
        sinks=["rotating_file"],
    ),
    sink_config=SinkConfig(
        rotating_file=RotatingFileSinkSettings(
            directory="/var/log/myapp",
            max_bytes="50 MB",
            max_files=10,
            compress_rotated=True,
        )
    ),
)
logger = get_logger(settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .add_file(
        "/var/log/myapp",
        max_bytes="50 MB",
        max_files=10,
        compress=True,
    )
    .build()
)
```

---

### Example 3: CloudWatch with Circuit Breaker

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import CoreSettings, SinkConfig, CloudWatchSinkSettings

settings = Settings(
    core=CoreSettings(
        log_level="INFO",
        sinks=["cloudwatch"],
        sink_circuit_breaker_enabled=True,
        sink_circuit_breaker_failure_threshold=5,
        sink_circuit_breaker_recovery_timeout_seconds=30.0,
    ),
    sink_config=SinkConfig(
        cloudwatch=CloudWatchSinkSettings(
            log_group_name="/myapp/prod",
            region="us-east-1",
        )
    ),
)
logger = get_logger(settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .add_cloudwatch("/myapp/prod", region="us-east-1")
    .with_circuit_breaker(
        enabled=True,
        failure_threshold=5,
        recovery_timeout="30s",
    )
    .build()
)
```

---

### Example 4: Sampling and Rate Limiting

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import CoreSettings, FilterConfig, SamplingFilterSettings, RateLimitFilterSettings

settings = Settings(
    core=CoreSettings(
        log_level="INFO",
        sinks=["stdout_json"],
        filters=["sampling", "rate_limit"],
    ),
    filter_config=FilterConfig(
        sampling=SamplingFilterSettings(sample_rate=0.1),
        rate_limit=RateLimitFilterSettings(
            capacity=100,
            refill_rate_per_sec=10.0,
        ),
    ),
)
logger = get_logger(settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .add_stdout()
    .with_sampling(rate=0.1)
    .with_rate_limit(capacity=100, refill_rate=10.0)
    .build()
)
```

---

### Example 5: Redaction Configuration

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import CoreSettings, RedactorConfig, FieldMaskSettings, RegexMaskSettings

settings = Settings(
    core=CoreSettings(
        log_level="INFO",
        sinks=["stdout_json"],
        redactors=["field_mask", "regex_mask", "url_credentials"],
    ),
    redactor_config=RedactorConfig(
        field_mask=FieldMaskSettings(
            fields_to_mask=["password", "api_key"],
            mask_string="[REDACTED]",
        ),
        regex_mask=RegexMaskSettings(
            patterns=["(?i).*secret.*"],
        ),
    ),
)
logger = get_logger(settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .add_stdout()
    .with_field_mask(["password", "api_key"], mask="[REDACTED]")
    .with_regex_mask(["(?i).*secret.*"])
    .with_url_credential_redaction()
    .build()
)
```

---

### Example 6: Sink Routing

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import CoreSettings, SinkConfig, CloudWatchSinkSettings, SinkRoutingSettings

settings = Settings(
    core=CoreSettings(
        sinks=["stdout_json", "cloudwatch"],
    ),
    sink_config=SinkConfig(
        cloudwatch=CloudWatchSinkSettings(
            log_group_name="/myapp/errors",
            region="us-east-1",
        )
    ),
    sink_routing=SinkRoutingSettings(
        enabled=True,
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
            {"levels": ["INFO", "WARNING"], "sinks": ["stdout_json"]},
        ],
        fallback_sinks=["stdout_json"],
    ),
)
logger = get_logger(settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .add_stdout()
    .add_cloudwatch("/myapp/errors", region="us-east-1")
    .with_routing(
        rules=[
            {"levels": ["ERROR", "CRITICAL"], "sinks": ["cloudwatch"]},
            {"levels": ["INFO", "WARNING"], "sinks": ["stdout_json"]},
        ],
        fallback=["stdout_json"],
    )
    .build()
)
```

---

### Example 7: Full Production Configuration

**Before (Settings):**
```python
from fapilog import Settings, get_logger
from fapilog.core.settings import (
    CoreSettings,
    SinkConfig,
    FilterConfig,
    RedactorConfig,
    RotatingFileSinkSettings,
    CloudWatchSinkSettings,
    SamplingFilterSettings,
    FieldMaskSettings,
)

settings = Settings(
    core=CoreSettings(
        log_level="INFO",
        app_name="my-service",
        sinks=["rotating_file", "cloudwatch"],
        filters=["sampling"],
        redactors=["field_mask", "url_credentials"],
        max_queue_size=10000,
        batch_max_size=100,
        worker_count=2,
        sink_circuit_breaker_enabled=True,
        sink_circuit_breaker_failure_threshold=5,
        drop_on_full=False,
        enable_metrics=True,
    ),
    sink_config=SinkConfig(
        rotating_file=RotatingFileSinkSettings(
            directory="logs/app",
            max_bytes="100 MB",
            max_files=20,
            compress_rotated=True,
        ),
        cloudwatch=CloudWatchSinkSettings(
            log_group_name="/myapp/prod",
            region="us-east-1",
        ),
    ),
    filter_config=FilterConfig(
        sampling=SamplingFilterSettings(sample_rate=0.5),
    ),
    redactor_config=RedactorConfig(
        field_mask=FieldMaskSettings(
            fields_to_mask=["password", "api_key", "ssn"],
        ),
    ),
)
logger = get_logger(settings=settings)
```

**After (Builder):**
```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_level("INFO")
    .with_app_name("my-service")

    # Sinks
    .add_file("logs/app", max_bytes="100 MB", max_files=20, compress=True)
    .add_cloudwatch("/myapp/prod", region="us-east-1")

    # Filters
    .with_sampling(rate=0.5)

    # Redaction
    .with_field_mask(["password", "api_key", "ssn"])
    .with_url_credential_redaction()

    # Performance
    .with_queue_size(10000)
    .with_batch_size(100)
    .with_workers(2)

    # Reliability
    .with_circuit_breaker(enabled=True, failure_threshold=5)
    .with_backpressure(drop_on_full=False)

    # Observability
    .with_metrics(enabled=True)

    .build()
)
```

---

## Handling Presets

If you're using environment variables with Settings, consider using Builder presets:

**Before (Environment-driven Settings):**
```python
from fapilog import Settings, get_logger

# Settings reads from FAPILOG_* environment variables
settings = Settings()
logger = get_logger(settings=settings)
```

**After (Builder with Preset):**
```python
from fapilog import LoggerBuilder
import os

# Use preset based on environment
preset = "production" if os.getenv("ENV") == "production" else "dev"
logger = (
    LoggerBuilder()
    .with_preset(preset)
    .build()
)
```

Or continue using Settings for pure environment-variable configuration - the Builder is not required for all use cases.

---

## Migration Tips

1. **Start with presets** - Use `.with_preset()` as a base and override specific values

2. **Method chaining order doesn't matter** - Builder accumulates configuration; order is flexible

3. **Duration strings accepted** - Use `"30s"`, `"5m"`, `"1h"` instead of seconds

4. **Size strings accepted** - Use `"10 MB"`, `"1 GB"` instead of bytes

5. **Sinks auto-registered** - `add_*` methods handle both sink registration and configuration

6. **Filters auto-enabled** - `with_sampling()`, `with_rate_limit()`, etc. enable the filter automatically

---

## Next Steps

- [Builder API Reference](../api-reference/builder.md) - Complete method documentation
- [Builder Configuration Guide](../user-guide/builder-configuration.md) - Task-oriented tutorials
- [Example Configurations](../examples/builder-configurations.md) - Real-world examples
