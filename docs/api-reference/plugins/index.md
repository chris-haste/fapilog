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

fapilog's plugin system allows you to extend functionality in four key areas:

- **Sinks** - Output destinations for log messages
- **Enrichers** - Add context and metadata to messages
- **Redactors** - Remove or mask sensitive information
- **Processors** - Transform and optimize messages

## Plugin Types

### Sinks (Output Plugins)

- **[Sinks](sinks.md)** - Output destinations (stdout JSON, rotating file, HTTP, etc.)

### Enrichers (Input/Context Plugins)

- **[Enrichers](enrichers.md)** - Add runtime/context metadata before sinks

### Redactors (Security Plugins)

- **[Redactors](redactors.md)** - Mask/remove sensitive fields or secrets

### Processors (Transform Plugins)

- **[Processors](processors.md)** - Transform/filter entries before sinks

## Plugin Architecture

### Plugin Lifecycle

```python
class BasePlugin:
    async def start(self) -> None:
        """Initialize the plugin."""
        pass

    async def stop(self) -> None:
        """Clean up plugin resources."""
        pass

    async def health_check(self) -> bool:
        """Check plugin health."""
        return True
```

### Plugin Configuration

Plugins are configured through the main settings:

```python
from fapilog import Settings

settings = Settings(
    # Enable specific plugins
    plugins__sinks=["stdout", "file"],
    plugins__enrichers=["runtime_info", "context_vars"],
    plugins__redactors=["field_mask", "regex_mask"],
    plugins__processors=["zero_copy"]
)
```

### Plugin Discovery

fapilog automatically discovers available plugins:

```python
from fapilog import discover_plugins

# Discover all available plugins
plugins = await discover_plugins()

print(f"Available sinks: {plugins.sinks}")
print(f"Available enrichers: {plugins.enrichers}")
print(f"Available redactors: {plugins.redactors}")
print(f"Available processors: {plugins.processors}")
```

## Built-in Plugins

### Default Configuration

By default, fapilog includes:

```python
# Default plugin configuration
DEFAULT_SINKS = ["stdout_json"]
DEFAULT_ENRICHERS = ["runtime_info", "context_vars"]
DEFAULT_REDACTORS = ["field_mask"]
DEFAULT_PROCESSORS = ["pass_through"]
```

### Plugin Dependencies

Some plugins have dependencies:

```python
# Optional dependencies for specific plugins
OPTIONAL_DEPENDENCIES = {
    "http_client_sink": ["httpx"],
    "mmap_sink": ["mmap"],
    "prometheus_metrics": ["prometheus_client"]
}
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

## Plugin Configuration Examples

### Development Environment

```python
from fapilog import Settings

dev_settings = Settings(
    plugins__sinks=["stdout_json"],
    plugins__enrichers=["runtime_info"],
    plugins__redactors=["field_mask"],
    plugins__processors=["pass_through"]
)
```

### Production Environment

```python
from fapilog import Settings

prod_settings = Settings(
    plugins__sinks=["rotating_file", "http_client"],
    plugins__enrichers=["runtime_info", "context_vars"],
    plugins__redactors=["field_mask", "regex_mask", "url_credentials"],
    plugins__processors=["zero_copy"]
)
```

### High-Performance Configuration

```python
from fapilog import Settings

perf_settings = Settings(
    plugins__sinks=["mmap_persistence"],
    plugins__enrichers=["context_vars"],  # Minimal enrichers
    plugins__redactors=["field_mask"],    # Basic redaction
    plugins__processors=["zero_copy"]     # High-performance processing
)
```

## Plugin Health Monitoring

### Health Checks

All plugins support health monitoring:

```python
from fapilog import get_plugin_health

# Check health of all plugins
health = await get_plugin_health()

for plugin_type, plugins in health.items():
    print(f"{plugin_type}:")
    for name, status in plugins.items():
        print(f"  {name}: {'✅' if status else '❌'}")
```

### Plugin Metrics

Plugins expose metrics for monitoring:

```python
from fapilog import get_plugin_metrics

# Get metrics from all plugins
metrics = await get_plugin_metrics()

for plugin_type, plugin_metrics in metrics.items():
    print(f"{plugin_type} metrics:")
    for name, metric_data in plugin_metrics.items():
        print(f"  {name}: {metric_data}")
```

## Best Practices

1. **Start simple** - Use built-in plugins before creating custom ones
2. **Health monitoring** - Always implement health checks for custom plugins
3. **Resource management** - Properly implement start/stop lifecycle
4. **Error handling** - Gracefully handle failures in custom plugins
5. **Configuration** - Make plugins configurable through settings
6. **Testing** - Test plugins in isolation and integration

---

_The plugin system provides extensibility and customization for fapilog._
