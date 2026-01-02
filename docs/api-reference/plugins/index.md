# Plugins

Extensible sinks, enrichers, redactors, and processors for fapilog.

```{toctree}
:maxdepth: 2
:caption: Plugins

sinks
enrichers
redactors
processors
```

## Overview

fapilog's plugin system provides base protocols for extending functionality in four key areas:

- **Sinks** - Output destinations for log messages
- **Enrichers** - Add context and metadata to messages
- **Redactors** - Remove or mask sensitive information
- **Processors** - Transform and optimize messages

## Built-in Plugins

fapilog includes several built-in plugins that ship with the library:

### Sinks

| Sink | Description |
|------|-------------|
| `StdoutJsonSink` | Outputs JSON to stdout |
| `RotatingFileSink` | Writes to rotating log files |
| `HttpSink` | Sends logs to HTTP endpoints |

### Enrichers

| Enricher | Description |
|----------|-------------|
| `RuntimeInfoEnricher` | Adds Python version, PID, hostname |
| `ContextVarsEnricher` | Adds context variables |

### Redactors

| Redactor | Description |
|----------|-------------|
| `FieldMaskRedactor` | Masks specific field names |
| `RegexMaskRedactor` | Masks values matching regex patterns |
| `UrlCredentialsRedactor` | Strips credentials from URLs |

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

For enterprise features like tamper-evident logging, use the `fapilog-tamper` add-on package which provides standard plugins:

```python
# Via Settings (recommended)
from fapilog import get_logger, Settings

settings = Settings(
    core__enrichers=["integrity"],  # IntegrityEnricher from fapilog-tamper
    core__sinks=["sealed"],         # SealedSink from fapilog-tamper
)

logger = get_logger(settings=settings)
```

```python
# Via direct plugin loading
from fapilog.plugins import load_plugin

enricher = load_plugin("fapilog.enrichers", "integrity", {
    "algorithm": "HMAC-SHA256",
    "key_id": "audit-key-2025",
})

sink = load_plugin("fapilog.sinks", "sealed", {
    "inner_sink": "rotating_file",
    "sign_manifests": True,
})
```

The `fapilog-tamper` package registers plugins via standard entry point groups (`fapilog.enrichers`, `fapilog.sinks`). See [Enterprise Features](../enterprise.md) for more details.

## Best Practices

1. **Start simple** - Use built-in plugins before creating custom ones
2. **Implement lifecycle** - Properly implement `start()` and `stop()` methods
3. **Error handling** - Gracefully handle failures in custom plugins
4. **Resource management** - Clean up connections/files in `stop()`
5. **Testing** - Test plugins in isolation and integration

---

_The plugin system provides extensibility and customization for fapilog._
