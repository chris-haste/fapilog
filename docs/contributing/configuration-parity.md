# Configuration Parity Guide

This guide explains how to maintain parity between Settings classes and the LoggerBuilder API.

## Overview

Fapilog supports two configuration approaches:

1. **Settings classes** - YAML/dict-based configuration for full control
2. **LoggerBuilder API** - Fluent builder for programmatic configuration

Every Settings field should have a corresponding builder method to ensure users can configure everything through either approach.

## Enforcement Layers

| Layer | When | Purpose |
|-------|------|---------|
| Pre-commit hook | Before commit | Fast local feedback |
| CI test | On PR | Comprehensive validation |
| Claude skills | During implementation | AI-assisted guidance |

## Configuration Categories

### Core Settings

**Location:** `CoreSettings` in `src/fapilog/core/settings.py`
**Builder pattern:** `with_*()` methods

```python
# Settings field
worker_count: int = Field(default=1, description="Number of workers")

# Builder method
def with_workers(self, count: int = 1) -> LoggerBuilder:
    self._config.setdefault("core", {})["worker_count"] = count
    return self
```

### Cloud Sink Settings

**Location:** `CloudWatchSinkSettings`, `LokiSinkSettings`, `PostgresSinkSettings`
**Builder pattern:** `add_*()` methods with parameter mapping

```python
# Settings field
log_group_name: str = Field(...)

# Builder param uses simplified name
def add_cloudwatch(self, log_group: str, ...) -> LoggerBuilder:
    config["log_group_name"] = log_group  # Maps param -> field
```

**Important:** Document param->field mappings in `scripts/builder_param_mappings.py`

### Filter Settings

**Location:** `FilterConfig` nested class
**Builder pattern:** `with_*()` methods that enable AND configure

```python
def with_sampling(self, rate: float = 1.0, *, seed: int | None = None):
    # Enable the filter
    filters = self._config.setdefault("core", {}).setdefault("filters", [])
    if "sampling" not in filters:
        filters.append("sampling")
    # Configure it
    filter_config = self._config.setdefault("filter_config", {})
    filter_config["sampling"] = {"sample_rate": rate, "seed": seed}
```

### Processor Settings

**Location:** `ProcessorConfigSettings`, `SizeGuardSettings`
**Builder pattern:** `with_*()` methods

### Advanced Settings

**Location:** `SinkRoutingSettings`, `RedactorConfig.*`, `PluginsSettings`
**Builder pattern:** `with_routing()`, `with_field_mask()`, `with_plugins()`

## Adding a New Setting

### Step 1: Add the Settings field

```python
# In src/fapilog/core/settings.py
class CoreSettings(BaseModel):
    my_new_field: int = Field(
        default=10,
        ge=1,
        description="Description of what this field does"
    )
```

### Step 2: Add the builder method

```python
# In src/fapilog/builder.py
def with_my_new_feature(self, value: int = 10) -> LoggerBuilder:
    """Configure my new feature.

    Args:
        value: What the value controls

    Example:
        >>> builder.with_my_new_feature(20)
    """
    self._config.setdefault("core", {})["my_new_field"] = value
    return self
```

### Step 3: Update the mapping registry

```python
# In scripts/builder_param_mappings.py
CORE_COVERAGE = {
    # ... existing mappings ...
    "with_my_new_feature": ["my_new_field"],
}
```

### Step 4: Add tests

```python
# In tests/test_builder.py
def test_with_my_new_feature_sets_config(self) -> None:
    builder = LoggerBuilder()
    builder.with_my_new_feature(20)
    assert builder._config["core"]["my_new_field"] == 20
```

### Step 5: Verify parity

```bash
python scripts/check_builder_parity.py
```

## Consistency Requirements

### Duration fields

Accept both string ("30s") and numeric values:

```python
def with_timeout(self, timeout: str | float) -> LoggerBuilder:
    from .core.types import _parse_duration
    if isinstance(timeout, str):
        parsed = _parse_duration(timeout)
        if parsed is None:
            raise ValueError(f"Invalid timeout: {timeout}")
        timeout = parsed
    self._config.setdefault("core", {})["timeout_seconds"] = timeout
    return self
```

### Size fields

Settings `SizeField` type handles string parsing automatically. Builder should accept both:

```python
def add_file(self, max_bytes: str | int = "10 MB") -> LoggerBuilder:
    # Strings like "10 MB" are parsed by SizeField in Settings
    config["max_bytes"] = max_bytes
```

### Boolean toggle methods

Use `enabled` as the parameter name:

```python
def with_metrics(self, enabled: bool = True) -> LoggerBuilder:
    self._config.setdefault("core", {})["enable_metrics"] = enabled
    return self
```

### Return type

All builder methods must return `Self` for chaining:

```python
def with_something(self, value: int) -> LoggerBuilder:
    # configure...
    return self  # Always return self for chaining
```

## Exclusion Lists

Some fields are intentionally excluded from parity requirements:

```python
# In scripts/builder_param_mappings.py
CORE_EXCLUSIONS = {
    "schema_version",      # Internal versioning
    "benchmark_file_path", # Test-only field
    "sensitive_fields_policy",  # Policy hint, not runtime config
}
```

### Adding an exclusion

1. Add the field to the appropriate exclusion set
2. Include a comment explaining WHY it's excluded
3. Only exclude fields that truly shouldn't be exposed via builder

## Verification Commands

```bash
# Run parity check
python scripts/check_builder_parity.py

# Run full test suite
pytest tests/test_builder_parity.py tests/test_builder_param_mappings.py -v

# Check specific category tests
pytest tests/test_check_builder_parity.py -v
```

## Troubleshooting

### "CoreSettings fields without builder methods"

1. Add a `with_*()` method to `LoggerBuilder`
2. Update `CORE_COVERAGE` in `builder_param_mappings.py`
3. Or add to `CORE_EXCLUSIONS` with rationale

### "CloudWatchSinkSettings fields without add_cloudwatch() coverage"

1. Add parameter to `add_cloudwatch()` method
2. Update `SINK_PARAM_MAPPINGS["add_cloudwatch"]`
3. Or add to `SINK_EXCLUSIONS` with rationale

### Pre-commit hook failing

The hook only runs when you modify `settings.py` or `builder.py`. If it fails:

1. Check which fields are missing coverage
2. Add the builder method or update mappings
3. Or bypass with `--no-verify` (not recommended)

## Related Documentation

- `docs/architecture/builder-design-patterns.md` - Naming conventions
- `docs/architecture/builder-api-gaps.md` - Full gap audit
- Stories 10.22-10.28 - Builder API implementation stories
