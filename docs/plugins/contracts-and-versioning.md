# Plugin Contracts and API Versioning

This document explains the authoring contracts (protocols) and the Plugin API version policy used by Fapilog v3.

## Public Protocols

Fapilog exposes runtime-checkable Protocols for all plugin types. Implementations should be async-first and resilient.

- Sinks: `fapilog.plugins.sinks.BaseSink`
- Enrichers: `fapilog.plugins.enrichers.BaseEnricher`
- Processors: `fapilog.plugins.processors.BaseProcessor`
- Redactors: `fapilog.plugins.redactors.BaseRedactor`

These are re-exported in `fapilog.plugins` for convenient import:

```python
from fapilog.plugins import BaseSink, BaseEnricher, BaseProcessor, BaseRedactor
```

## Plugin API Version

- Current API version: defined as a tuple at `fapilog.plugins.versioning.PLUGIN_API_VERSION` (currently `(1, 0)`).
- Plugins declare their contract version via `PLUGIN_METADATA["api_version"]` as a string like `"1.0"`.
- Parsing and compatibility helpers live in `fapilog.plugins.versioning`:
  - `parse_api_version("1.0") -> (1, 0)`
  - `is_plugin_api_compatible((declared_major, declared_minor)) -> bool`

### Compatibility Policy

- Compatible when the declared major equals the current major, and the declared minor is less than or equal to the current minor.
- Incompatible otherwise. Example: Declared `2.0` is incompatible with current `1.x`.

## Plugin Metadata Keys

Minimal `PLUGIN_METADATA` example for a sink:

```python
PLUGIN_METADATA = {
    "name": "stdout-json-sink",
    "version": "0.1.0",
    "plugin_type": "sink",
    "entry_point": "your_module:YourPluginClassOrModule",
    "description": "Your description",
    "author": "Your Name",
    "compatibility": {"min_fapilog_version": "3.0.0"},
    "api_version": "1.0",  # Contract version
}
```

## Load-time Enforcement

The registry validates compatibility before loading:

1. Fapilog core version via `validate_fapilog_compatibility()`
2. Plugin API version via `parse_api_version()` and `is_plugin_api_compatible()`

On mismatch or parse failure, loading is rejected with `PluginRegistryError` and a structured warning is emitted via `fapilog.core.diagnostics.warn` with fields:

- `plugin`, `declared_api_version`, `expected_api_version`, `reason`

## Backward Compatibility

For the v1.x contract series, method signatures of the public Protocols will not change in a breaking way. Minor increments relax compatibility (e.g., adding optional methods) but do not break existing plugins.
