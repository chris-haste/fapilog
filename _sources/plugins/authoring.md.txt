# Authoring Fapilog Plugins

This guide covers entry points, required metadata, and the Plugin API versioning policy.

## Entry Points

Declare entry points in `pyproject.toml` under one of the v3 groups per plugin type:

```
[project.entry-points."fapilog.sinks"]
"my-sink" = "my_package.my_sink"

[project.entry-points."fapilog.processors"]
"my-processor" = "my_package.my_processor"

[project.entry-points."fapilog.enrichers"]
"my-enricher" = "my_package.my_enricher"

[project.entry-points."fapilog.redactors"]
"my-redactor" = "my_package.my_redactor"

[project.entry-points."fapilog.alerting"]
"my-alert" = "my_package.my_alert"

# Fallback generic group (type derived from PLUGIN_METADATA["plugin_type"]) when needed
[project.entry-points."fapilog.plugins"]
"legacy-plugin" = "my_package.legacy"
```

## PLUGIN_METADATA

Each module must export a `PLUGIN_METADATA` mapping with at least:

```
PLUGIN_METADATA = {
  "name": "my-plugin",
  "version": "1.2.3",
  "plugin_type": "sink",  # sink|processor|enricher|redactor|alerting
  "entry_point": "my_package.my_sink:Plugin",
  "description": "...",
  "author": "Your Name",
  "compatibility": {"min_fapilog_version": "3.0.0"},
  "api_version": "1.0",  # Plugin API contract version
  # Optional configuration docs
  "config_schema": {...},
  "default_config": {...},
}
```

## API Versioning

- Current API contract is defined at `fapilog.plugins.versioning.PLUGIN_API_VERSION` (e.g., `(1, 0)`).
- Policy: compatible when declared major matches current major, and declared minor is less than or equal to current minor.
- Utilities: `parse_api_version()` and `is_plugin_api_compatible()`.

## Protocols

Author implementations should satisfy the runtime-checkable Protocol for their type:

```
from fapilog.plugins import BaseSink, BaseProcessor, BaseEnricher, BaseRedactor
```

All interfaces are async-first and must contain errors rather than raising into the core pipeline.

## Testing Your Plugin

fapilog provides comprehensive testing utilities in the `fapilog.testing` module. See the [Testing Plugins Guide](../user-guide/testing-plugins.md) for complete documentation.

Quick example:

```python
import pytest
from fapilog.testing import validate_sink, validate_plugin_lifecycle

def test_my_sink_protocol():
    sink = MySink()
    result = validate_sink(sink)
    assert result.valid, f"Protocol errors: {result.errors}"

@pytest.mark.asyncio
async def test_my_sink_lifecycle():
    sink = MySink()
    result = await validate_plugin_lifecycle(sink)
    assert result.valid
```

### Available Utilities

- **Mock plugins**: `MockSink`, `MockEnricher`, `MockRedactor`, `MockProcessor`
- **Validators**: `validate_sink()`, `validate_enricher()`, `validate_redactor()`, `validate_processor()`
- **Lifecycle testing**: `validate_plugin_lifecycle()`
- **Event factories**: `create_log_event()`, `create_batch_events()`, `create_sensitive_event()`
