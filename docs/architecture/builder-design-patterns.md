# Builder API Design Patterns

This document defines consistent patterns for implementing new LoggerBuilder methods.

## 1. Naming Conventions

### Method Prefixes

| Prefix | Use Case | Example |
|--------|----------|---------|
| `with_*` | Set/configure settings | `with_level()`, `with_batch_size()` |
| `add_*` | Add sinks (multiple allowed) | `add_file()`, `add_cloudwatch()` |
| `configure_*` | Configure plugin-specific settings | `configure_filter()` |
| `enable_*` | Toggle boolean features | `enable_metrics()` |

### Naming Rules

1. **Use snake_case** for method names (Python convention)
2. **Match Settings field names** where practical
3. **Prefer short, clear names** over verbose descriptions
4. **Group related settings** into single methods with parameters

### Examples

```python
# Good: matches Settings field
.with_level("INFO")           # -> core.log_level

# Good: clear and concise
.with_batch_size(100)         # -> core.batch_max_size
.with_batch_timeout("500ms")  # -> core.batch_timeout_seconds

# Good: grouped related settings
.with_circuit_breaker(
    enabled=True,
    threshold=5,
    recovery_timeout="30s"
)

# Bad: too verbose
.with_maximum_batch_size_before_flush(100)

# Bad: inconsistent prefix
.set_level("INFO")  # Should be with_level
```

## 2. Parameter Style

### Human-Readable Strings

Accept human-readable strings for sizes and durations. Parse to native types internally.

```python
# Durations: support string and numeric
.with_batch_timeout("500ms")    # String with unit
.with_batch_timeout(0.5)        # Float seconds

# Sizes: support string and numeric
.add_file(directory="/logs", max_bytes="10 MB")   # String with unit
.add_file(directory="/logs", max_bytes=10485760)  # Integer bytes

# Supported duration formats:
# "500ms", "1s", "30s", "5m", "1h", "daily"

# Supported size formats:
# "1 KB", "10 MB", "1 GB", "1024" (bytes)
```

### Type Annotations

All parameters must have type annotations:

```python
def with_batch_timeout(self, timeout: str | float) -> LoggerBuilder:
    """Set batch timeout.

    Args:
        timeout: Batch timeout (supports "1s", "500ms" strings or float seconds)
    """
```

### Optional vs Required Parameters

- **Required**: Use positional parameters (no default)
- **Optional**: Use keyword-only with defaults

```python
def add_cloudwatch(
    self,
    log_group: str,              # Required (positional)
    *,                           # Force keyword-only below
    region: str | None = None,   # Optional
    batch_size: int = 100,       # Optional with default
) -> LoggerBuilder:
```

### Boolean Toggles

For boolean features, use `enable_*` methods or explicit `enabled` parameter:

```python
# Option 1: enable_* method (preferred for simple toggles)
.enable_metrics()
.enable_metrics(port=9090)

# Option 2: explicit parameter (for grouped settings)
.with_circuit_breaker(enabled=True, threshold=5)
```

## 3. Namespace Strategy

### Flat Namespace (Current)

Keep all methods at the top level of the builder:

```python
LoggerBuilder()
    .with_level("INFO")
    .add_cloudwatch(log_group="/app/logs")
    .with_circuit_breaker(enabled=True)
    .build()
```

### Rationale for Flat Namespace

1. **Simplicity**: Single chaining point, no nested objects
2. **Discoverability**: All methods visible via IDE autocomplete
3. **Consistency**: Matches existing builder pattern
4. **Fewer objects**: No sub-builder maintenance

### Rejected: Nested Builders

```python
# NOT recommended - adds complexity
LoggerBuilder()
    .sinks.cloudwatch(log_group="/app/logs")
    .core.with_level("INFO")
    .build()
```

## 4. Return Type

All builder methods return `Self` for chaining:

```python
from typing import Self

class LoggerBuilder:
    def with_level(self, level: str) -> Self:
        self._config.setdefault("core", {})["log_level"] = level.upper()
        return self
```

Note: Use `LoggerBuilder` as return type if `Self` is not available in the Python version.

## 5. Validation Strategy

### Lazy Validation (Preferred)

Validate on `build()`, not on individual method calls:

```python
# Good: validates in build()
def add_cloudwatch(self, log_group: str, *, region: str | None = None) -> Self:
    config = {"log_group_name": log_group}
    if region:
        config["region"] = region
    self._sinks.append({"name": "cloudwatch", "config": config})
    return self  # No validation here

def build(self) -> SyncLoggerFacade:
    settings = Settings(**config)  # Pydantic validates here
    return get_logger(settings=settings)
```

### Exceptions to Lazy Validation

Validate immediately for:

1. **Type coercion failures** (invalid duration/size strings)
2. **Clearly invalid values** (empty required strings)

```python
def add_file(self, directory: str, *, max_bytes: str | int = "10 MB") -> Self:
    if not directory:
        raise ValueError("File sink requires directory parameter")

    # Parse human-readable string
    if isinstance(max_bytes, str):
        parsed = _parse_size(max_bytes)
        if parsed is None:
            raise ValueError(f"Invalid size format: {max_bytes}")
        max_bytes = parsed

    # Rest of configuration...
    return self
```

## 6. Error Handling Patterns

### Error Messages

Provide clear, actionable error messages:

```python
# Good: specific and actionable
raise ValueError("HTTP sink requires endpoint parameter")
raise ValueError(f"Invalid timeout format: {timeout}. Use '30s' or numeric seconds.")

# Bad: vague
raise ValueError("Invalid configuration")
```

### Error Aggregation

When possible, collect multiple errors and report them together in `build()`:

```python
def build(self) -> SyncLoggerFacade:
    try:
        settings = Settings(**config)
    except ValidationError as e:
        # Pydantic provides detailed field-level errors
        raise ValueError(f"Invalid builder configuration: {e}") from e
```

## 7. Documentation Standards

### Docstrings

Every public method needs a docstring with:

```python
def add_cloudwatch(
    self,
    log_group: str,
    *,
    region: str | None = None,
    batch_size: int = 100,
) -> LoggerBuilder:
    """Add CloudWatch Logs sink.

    Args:
        log_group: CloudWatch log group name (required)
        region: AWS region (uses default credentials chain if not specified)
        batch_size: Events per PutLogEvents batch (1-10000)

    Raises:
        ValueError: If log_group is empty

    Example:
        builder.add_cloudwatch(
            log_group="/myapp/prod",
            region="us-west-2",
            batch_size=500
        )
    """
```

## 8. Implementation Checklist

When adding a new builder method:

- [ ] Follow naming convention (`with_*`, `add_*`, `configure_*`, `enable_*`)
- [ ] Add type annotations for all parameters
- [ ] Support human-readable strings where applicable
- [ ] Return `Self` for chaining
- [ ] Validate in `build()` except for type coercion
- [ ] Write docstring with Args, Raises, Example
- [ ] Add to parity test mapping
- [ ] Add unit tests covering success and error cases
