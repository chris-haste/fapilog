# Authoring Fapilog Plugins

This guide covers entry points, required metadata, and the Plugin API versioning policy.

## Entry Points

Declare entry points in `pyproject.toml` under one of the v3 groups per plugin type:

```
[project.entry-points."fapilog.sinks"]
"my_sink" = "my_package.my_sink"

[project.entry-points."fapilog.processors"]
"my_processor" = "my_package.my_processor"

[project.entry-points."fapilog.enrichers"]
"my_enricher" = "my_package.my_enricher"

[project.entry-points."fapilog.redactors"]
"my_redactor" = "my_package.my_redactor"

[project.entry-points."fapilog.filters"]
"my_filter" = "my_package.my_filter"

# Fallback generic group (type derived from PLUGIN_METADATA["plugin_type"]) when needed
[project.entry-points."fapilog.plugins"]
"legacy-plugin" = "my_package.legacy"
```

## Naming Convention

- Use lowercase with underscores (snake_case): `field_mask`, `rotating_file`, `runtime_info`.
- Avoid type suffixes in names (`-sink`, `-processor`, etc.); the `plugin_type` field already captures that.
- The class `name` attribute and `PLUGIN_METADATA["name"]` must match.
- Hyphen variants are normalized automatically for compatibility, but prefer snake_case in docs/config.

## PLUGIN_METADATA

Each module must export a `PLUGIN_METADATA` mapping with at least:

```
PLUGIN_METADATA = {
  "name": "my_plugin",
  "version": "1.2.3",
  "plugin_type": "sink",  # sink|processor|enricher|redactor|filter
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

**Valid plugin types:**
- `sink` - Output destinations for log entries
- `processor` - Transform serialized bytes
- `enricher` - Add fields to log events
- `redactor` - Sanitize sensitive data
- `filter` - Drop or transform events before enrichment

## API Versioning

- Current API contract is defined at `fapilog.plugins.versioning.PLUGIN_API_VERSION` as a tuple (e.g., `(1, 0)`).
- Plugins declare their version in `PLUGIN_METADATA["api_version"]` as a **string** (e.g., `"1.0"`).
- Policy: compatible when declared major matches current major, and declared minor is less than or equal to current minor.
- Utilities: `parse_api_version("1.0") -> (1, 0)` and `is_plugin_api_compatible((major, minor)) -> bool`.

## Protocols

Author implementations should satisfy the runtime-checkable Protocol for their type:

```
from fapilog.plugins import (
    BaseSink,
    BaseProcessor,
    BaseEnricher,
    BaseRedactor,
    BaseFilter,
)
```

All interfaces are async-first and must contain errors rather than raising into the core pipeline.

## Configuration Pattern

Use Pydantic v2 models for plugin configuration to get validation, coercion, and typo protection for free.

```python
from pydantic import BaseModel, ConfigDict, Field


class MyPluginConfig(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    threshold: int = Field(default=100, ge=1)
    enabled: bool = True
```

Parse configs with the shared helper so plugins accept config objects, dicts, kwargs, or loader-style nested `{"config": {...}}`:

```python
from fapilog.plugins import parse_plugin_config


class MyPlugin:
    name = "my_plugin"

    def __init__(
        self,
        *,
        config: MyPluginConfig | dict | None = None,
        **kwargs: object,
    ) -> None:
        cfg = parse_plugin_config(MyPluginConfig, config, **kwargs)
        self._threshold = cfg.threshold
        self._enabled = cfg.enabled
```

Supported inputs:
- Config object: `MyPlugin(config=MyPluginConfig(threshold=50))`
- Dict: `MyPlugin(config={"threshold": 50})`
- Kwargs: `MyPlugin(threshold=50)`
- Loader format: `MyPlugin(config={"config": {"threshold": 50}})`

Validation behavior:
- String numbers coerce to native types (`{"threshold": "5"}` -> `5`)
- Unknown keys raise `ValidationError` (catches typos)
- Bounds in `Field(...)` are enforced (e.g., `ge=0`, `le=1`)
