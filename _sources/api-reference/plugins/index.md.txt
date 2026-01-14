# Plugins

Extensible sinks, enrichers, redactors, processors, and filters for fapilog.

```{toctree}
:maxdepth: 2
:caption: Plugins

sinks
enrichers
redactors
processors
filters
```

## Overview

fapilog's plugin system provides base protocols for extending functionality in five key areas:

- **Sinks** - Output destinations for log messages
- **Enrichers** - Add context and metadata to messages
- **Redactors** - Remove or mask sensitive information
- **Processors** - Transform and optimize messages
- **Filters** - Drop or reshape events before enrichment

## Built-in Plugins

fapilog includes several built-in plugins that ship with the library:

### Sinks

| Sink | Name | Description |
|------|------|-------------|
| `StdoutJsonSink` | `stdout_json` | JSON lines to stdout |
| `StdoutPrettySink` | `stdout_pretty` | Human-readable console output (TTY) |
| `RotatingFileSink` | `rotating_file` | Size/time-based rotation with compression |
| `HttpSink` | `http` | POST to HTTP endpoints with retry |
| `WebhookSink` | `webhook` | Webhook delivery with HMAC signing |
| `CloudWatchSink` | `cloudwatch` | AWS CloudWatch Logs (requires `boto3`) |
| `LokiSink` | `loki` | Grafana Loki log aggregation |
| `PostgresSink` | `postgres` | PostgreSQL database (requires `asyncpg`) |
| `AuditSink` | `audit` | Compliance audit logging |
| `RoutingSink` | `routing` | Level-based routing to multiple sinks |

### Enrichers

| Enricher | Name | Description |
|----------|------|-------------|
| `RuntimeInfoEnricher` | `runtime_info` | Adds service, env, version, host, pid, python |
| `ContextVarsEnricher` | `context_vars` | Adds request_id, user_id from ContextVar |
| `KubernetesEnricher` | `kubernetes` / `k8s` | Adds pod, namespace, node from K8s downward API |

### Redactors

| Redactor | Name | Description |
|----------|------|-------------|
| `FieldMaskRedactor` | `field_mask` | Masks specific field names |
| `RegexMaskRedactor` | `regex_mask` | Masks values matching regex patterns |
| `UrlCredentialsRedactor` | `url_credentials` | Strips credentials from URLs |

### Filters

| Filter | Name | Description |
|--------|------|-------------|
| `LevelFilter` | `level` | Drop events below threshold |
| `SamplingFilter` | `sampling` | Keep a random percentage of events |
| `RateLimitFilter` | `rate_limit` | Token bucket rate limiter |
| `AdaptiveSamplingFilter` | `adaptive_sampling` | Dynamic volume-based sampling |
| `TraceSamplingFilter` | `trace_sampling` | Trace context-based sampling |
| `FirstOccurrenceFilter` | `first_occurrence` | Track unique message patterns |

### Processors

| Processor | Name | Description |
|-----------|------|-------------|
| `ZeroCopyProcessor` | `zero_copy` | Zero-copy optimization for throughput |
| `SizeGuardProcessor` | `size_guard` | Truncate or drop oversized events |

## Plugin Configuration

Plugins are configured through environment variables or settings:

```python
from fapilog import Settings

settings = Settings(
    # Enable/disable plugin loading
    plugins__enabled=True,
    
    # Allow only specific plugins
    plugins__allowlist=["my-sink", "my-enricher"],
    
    # Block specific plugins
    plugins__denylist=["untrusted-plugin"],
)
```

## Custom Plugin Development

### Creating a Custom Sink

```python
from fapilog.plugins.sinks import BaseSink

class CustomSink(BaseSink):
    def __init__(self, config: dict):
        self.config = config
        self.connection = None

    async def start(self) -> None:
        """Initialize the sink."""
        self.connection = await self.connect()

    async def write(self, entry: dict) -> None:
        """Write a log entry."""
        await self.connection.send(entry)

    async def stop(self) -> None:
        """Clean up resources."""
        if self.connection:
            await self.connection.close()

    async def health_check(self) -> bool:
        """Check sink health."""
        return self.connection and self.connection.is_connected()
```

### Creating a Custom Enricher

```python
from fapilog.plugins.enrichers import BaseEnricher

class BusinessEnricher(BaseEnricher):
    def __init__(self, config: dict):
        self.config = config

    async def enrich(self, entry: dict) -> dict:
        """Add business context to the entry."""
        entry["business_unit"] = self.config.get("business_unit", "unknown")
        entry["environment"] = self.config.get("environment", "development")
        return entry
```

### Creating a Custom Redactor

```python
from fapilog.plugins.redactors import BaseRedactor

class CustomRedactor(BaseRedactor):
    def __init__(self, config: dict):
        self.patterns = config.get("patterns", [])

    async def redact(self, entry: dict) -> dict:
        """Apply custom redaction rules."""
        for pattern in self.patterns:
            entry = self.apply_pattern(entry, pattern)
        return entry

    def apply_pattern(self, entry: dict, pattern: str) -> dict:
        """Apply a specific redaction pattern."""
        # Custom redaction logic here
        return entry
```

## Plugin Protocols

All plugins follow base protocols defined in `fapilog.plugins`:

```python
from fapilog.plugins import (
    BaseSink,
    BaseEnricher,
    BaseRedactor,
    BaseProcessor,
    BaseFilter,
)
```

### Plugin Lifecycle

Plugins implement async lifecycle hooks:

```python
class BasePlugin:
    async def start(self) -> None:
        """Initialize the plugin. Called once on startup."""
        pass

    async def stop(self) -> None:
        """Clean up plugin resources. Called on shutdown."""
        pass

    async def health_check(self) -> bool:
        """Check plugin health for monitoring."""
        return True
```

## Enterprise Plugins

For enterprise features like tamper-evident logging, install the `fapilog-tamper` add-on
and configure it via standard plugin settings:

```python
from fapilog import Settings

settings = Settings(
    core__enrichers=["runtime_info", "integrity"],
    core__sinks=["sealed"],
    enricher_config__integrity={
        "algorithm": "HMAC-SHA256",
        "key_provider": "env",
        "key_id": "audit-key",
    },
)
```

See [Tamper-Evident Logging](../../addons/tamper-evident-logging.md) for full configuration options.

## Best Practices

1. **Start simple** - Use built-in plugins before creating custom ones
2. **Implement lifecycle** - Properly implement `start()` and `stop()` methods
3. **Error handling** - Gracefully handle failures in custom plugins
4. **Resource management** - Clean up connections/files in `stop()`
5. **Testing** - Test plugins in isolation and integration

---

_The plugin system provides extensibility and customization for fapilog._
