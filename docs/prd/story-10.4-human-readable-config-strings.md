# Story 10.4: Human-Readable Configuration Strings

## Context / Background

Currently, fapilog configuration requires raw numeric values (bytes, seconds) which are error-prone and hard to read:

**Current experience:**
```python
from fapilog import get_logger, Settings
from fapilog.core.settings import RotatingFileSettings

# Confusing: Is this 10MB or 100MB?
settings = Settings(
    file=RotatingFileSettings(
        max_bytes=10485760,        # 10MB in bytes (hard to read)
        interval_seconds=86400,    # 24 hours in seconds (not obvious)
        max_total_bytes=104857600, # 100MB (need calculator)
    )
)
logger = get_logger(settings=settings)
```

**Problems:**
1. **Not human-readable**: `10485760` doesn't obviously mean "10 MB"
2. **Error-prone**: Easy to add/drop zeros (`10485760` vs `1048576`)
3. **Requires calculation**: Converting MB to bytes, hours to seconds
4. **Poor DX**: Worse than loguru's `rotation="10 MB"`
5. **Not discoverable**: Users don't know valid values without docs

**Target experience:**
```python
from fapilog import get_logger, Settings
from fapilog.core.settings import RotatingFileSettings

# Clear and obvious
settings = Settings(
    file=RotatingFileSettings(
        max_bytes="10 MB",        # Clear: 10 megabytes
        interval_seconds="daily",  # Clear: rotate daily
        max_total_bytes="100 MB",  # Clear: 100 megabytes
    )
)
logger = get_logger(settings=settings)
```

This story implements human-readable configuration strings using **Pydantic v2's native Annotated types with BeforeValidator**, matching loguru's ergonomics while maintaining fapilog's type safety and validation.

## Scope (In / Out)

### In Scope

- **Size parsing**: "10 KB", "50 MB", "1 GB", "2 TB" → bytes
- **Duration parsing**: "5s", "10m", "1h", "7d", "weekly" → seconds
- **Rotation keywords**: "hourly", "daily", "weekly" → interval_seconds
- **Pydantic v2 Annotated types**: SizeField, DurationField (reusable)
- **Backward compatibility**: Existing integer values still work
- **Type safety**: Static type checkers see correct types
- **Clear error messages**: Validation errors show format examples
- **Comprehensive tests**: Parsers, validators, Pydantic integration

### Out of Scope

- **Multiple unit parsing** ("1h 30m") - defer to Story 10.x if needed
- **Combined retention** (`retention={"count": 7, "age": "30 days"}`) - defer to Story 10.x
- **Time-of-day rotation** ("00:00" cron-like) - defer to Story 10.x
- **Custom units** (user-defined) - standard units only
- **Locale-specific parsing** (European decimals "10,5 MB") - English only
- **Compression level strings** ("high", "medium") - boolean only

## Acceptance Criteria

### AC1: Size Parsing

**SizeField accepts strings and integers:**
```python
from fapilog.core.settings import RotatingFileSettings

# All valid:
RotatingFileSettings(max_bytes="10 KB")    # → 10240 bytes
RotatingFileSettings(max_bytes="50 MB")    # → 52428800 bytes
RotatingFileSettings(max_bytes="1 GB")     # → 1073741824 bytes
RotatingFileSettings(max_bytes="2 TB")     # → 2199023255552 bytes
RotatingFileSettings(max_bytes=10485760)   # → 10485760 bytes (backward compatible)
```

**Case insensitive:**
```python
"10 MB" == "10 mb" == "10 Mb" == "10 mB"  # All parse to same value
```

**Decimal numbers supported:**
```python
"10.5 MB" → 11010048 bytes  # 10.5 * 1024 * 1024
"0.5 GB" → 536870912 bytes  # 0.5 * 1024^3
```

**Whitespace flexible:**
```python
"10 MB" == "10MB" == "10  MB"  # All valid
```

**Validation errors:**
```python
RotatingFileSettings(max_bytes="10 XB")
# ValidationError: Invalid size format: '10 XB'. Use format like '10 MB' (units: KB, MB, GB, TB)

RotatingFileSettings(max_bytes="-10 MB")
# ValidationError: Size must be non-negative

RotatingFileSettings(max_bytes="ten MB")
# ValidationError: Invalid size format: 'ten MB'. Use format like '10 MB' (units: KB, MB, GB, TB)
```

### AC2: Duration Parsing

**DurationField accepts strings and numbers:**
```python
# All valid:
RotatingFileSettings(interval_seconds="5s")   # → 5.0 seconds
RotatingFileSettings(interval_seconds="10m")  # → 600.0 seconds
RotatingFileSettings(interval_seconds="1h")   # → 3600.0 seconds
RotatingFileSettings(interval_seconds="7d")   # → 604800.0 seconds
RotatingFileSettings(interval_seconds="2w")   # → 1209600.0 seconds
RotatingFileSettings(interval_seconds=3600)   # → 3600.0 (backward compatible)
RotatingFileSettings(interval_seconds=3600.5) # → 3600.5 (floats work)
```

**Case insensitive:**
```python
"10s" == "10S"  # Both valid
"1h" == "1H"    # Both valid
```

**Validation errors:**
```python
RotatingFileSettings(interval_seconds="10x")
# ValidationError: Invalid duration format: '10x'. Use format like '5s', '10m', '1h', '7d'

RotatingFileSettings(interval_seconds="-5s")
# ValidationError: Duration must be non-negative
```

### AC3: Rotation Keywords

**Special keywords for common intervals:**
```python
RotatingFileSettings(interval_seconds="hourly")  # → 3600 seconds (1 hour)
RotatingFileSettings(interval_seconds="daily")   # → 86400 seconds (24 hours)
RotatingFileSettings(interval_seconds="weekly")  # → 604800 seconds (7 days)
```

**Case insensitive:**
```python
"daily" == "Daily" == "DAILY"  # All valid
```

**Note in documentation:**
- "hourly" = every 60 minutes (not "at top of hour")
- "daily" = every 24 hours (not "at midnight")
- True time-of-day rotation ("00:00") deferred to Story 10.x

**Validation errors:**
```python
RotatingFileSettings(interval_seconds="monthly")
# ValidationError: Invalid duration format: 'monthly'. Use format like '5s', '10m', '1h', '7d' or 'hourly', 'daily', 'weekly'
```

### AC4: Pydantic v2 Annotated Types

**New types defined** in `src/fapilog/core/types.py`:
```python
from typing import Annotated
from pydantic import BeforeValidator

SizeField = Annotated[int, BeforeValidator(_parse_size)]
DurationField = Annotated[float, BeforeValidator(_parse_duration)]
OptionalSizeField = Annotated[int | None, BeforeValidator(_parse_size)]
OptionalDurationField = Annotated[float | None, BeforeValidator(_parse_duration)]
```

**Reusable across models:**
```python
# settings.py
from .types import SizeField, DurationField

class RotatingFileSettings(BaseModel):
    max_bytes: SizeField  # Accepts str or int
    interval_seconds: OptionalDurationField  # Accepts str or int or None

class SizeGuardConfig(BaseModel):
    max_bytes: SizeField  # Same type, reused

class HttpSinkSettings(BaseModel):
    timeout_seconds: DurationField  # Reused
```

**Type inference works:**
```python
settings = RotatingFileSettings(max_bytes="10 MB")
reveal_type(settings.max_bytes)  # int (not int | str)
```

### AC5: Backward Compatibility

**All existing code continues to work:**
```python
# Old way (integers) - STILL WORKS
settings = Settings(
    file=RotatingFileSettings(
        max_bytes=10485760,
        interval_seconds=86400,
    )
)

# New way (strings) - ALSO WORKS
settings = Settings(
    file=RotatingFileSettings(
        max_bytes="10 MB",
        interval_seconds="daily",
    )
)

# Mixed (both) - ALSO WORKS
settings = Settings(
    file=RotatingFileSettings(
        max_bytes="10 MB",       # String
        interval_seconds=86400,   # Integer
    )
)
```

**No breaking changes:**
- Existing Settings objects work unchanged
- Existing tests pass without modification
- Environment variables still use integers (strings parsed from env handled)

### AC6: Type Safety

**Static type checkers understand the types:**
```python
from fapilog.core.settings import RotatingFileSettings

settings = RotatingFileSettings(max_bytes="10 MB")

# mypy/pyright knows:
max_bytes: int = settings.max_bytes  # ✅ Correct type
max_bytes_str: str = settings.max_bytes  # ❌ Type error
```

**Field types are clean:**
```python
# Type is int, not int | str (union)
max_bytes: SizeField  # Resolves to int at runtime

# This is better than:
max_bytes: int | str  # Confusing - is it str or int after validation?
```

### AC7: Error Messages

**Clear validation errors with examples:**
```python
# Invalid size
try:
    RotatingFileSettings(max_bytes="10 XB")
except ValidationError as e:
    print(e)
# Output:
# 1 validation error for RotatingFileSettings
# max_bytes
#   Value error, Invalid size format: '10 XB'. Use format like '10 MB' (units: KB, MB, GB, TB)

# Invalid duration
try:
    RotatingFileSettings(interval_seconds="10x")
except ValidationError as e:
    print(e)
# Output:
# 1 validation error for RotatingFileSettings
# interval_seconds
#   Value error, Invalid duration format: '10x'. Use format like '5s', '10m', '1h', '7d' or 'hourly', 'daily', 'weekly'
```

**Errors show original input:**
```python
RotatingFileSettings(max_bytes="100 PB")  # Petabytes not supported
# Error shows: "Invalid size format: '100 PB'..." (original input visible)
```

### AC8: Integration with Existing Fields

**All size fields updated:**
```python
class RotatingFileSettings(BaseModel):
    max_bytes: SizeField  # NEW: Accepts "10 MB"
    max_total_bytes: OptionalSizeField  # NEW: Accepts "100 MB"

class SizeGuardConfig(BaseModel):
    max_bytes: SizeField  # NEW: Accepts "10 MB"
```

**All duration fields updated:**
```python
class RotatingFileSettings(BaseModel):
    interval_seconds: OptionalDurationField  # NEW: Accepts "1h" or "daily"

class WebhookSettings(BaseModel):
    timeout_seconds: DurationField  # NEW: Accepts "5s"
    retry_backoff_seconds: OptionalDurationField  # NEW: Accepts "2s"
    batch_timeout_seconds: DurationField  # NEW: Accepts "5s"

class HttpSinkSettings(BaseModel):
    timeout_seconds: DurationField  # NEW: Accepts "30s"
    batch_timeout_seconds: DurationField  # NEW: Accepts "5s"

class LokiSinkSettings(BaseModel):
    batch_timeout_seconds: DurationField  # NEW: Accepts "5s"
    timeout_seconds: DurationField  # NEW: Accepts "10s"
    retry_base_delay: DurationField  # NEW: Accepts "1s"

class CloudWatchSinkSettings(BaseModel):
    batch_timeout_seconds: DurationField  # NEW: Accepts "5s"
    retry_base_delay: DurationField  # NEW: Accepts "1s"
```

**Documentation updated for all fields:**
- Field descriptions include string format examples
- Type hints show SizeField/DurationField (discoverable)
- Docstrings show both string and integer examples

## API Design Decision

### Problem Statement

How do we enable human-readable strings while maintaining:
1. Pydantic v2 native patterns (leverage our dependency)
2. Type safety (static checkers understand types)
3. Backward compatibility (existing integers still work)
4. Reusability (DRY across all Settings models)
5. Clear error messages

### Options Considered

**Option A: Field Validators (Pydantic v1 style)** ❌
```python
class RotatingFileSettings(BaseModel):
    max_bytes: int | str  # Union type

    @field_validator('max_bytes')
    def parse_max_bytes(cls, v):
        if isinstance(v, str):
            return parse_size(v)
        return v
```
**Pros**: Simple, familiar pattern
**Cons**:
- ❌ Pydantic v1 style (not v2 best practice)
- ❌ Not reusable (need validator on each field)
- ❌ Type is `int | str` (confuses type checkers)
- ❌ Not composable

---

**Option B: Annotated Types with BeforeValidator (Pydantic v2 native)** ✅ **CHOSEN**
```python
from typing import Annotated
from pydantic import BeforeValidator

SizeField = Annotated[int, BeforeValidator(parse_size)]

class RotatingFileSettings(BaseModel):
    max_bytes: SizeField  # Type is int, accepts strings via validator
```
**Pros**:
- ✅ **Pydantic v2 recommended pattern** (from official docs)
- ✅ **Reusable** across all models (define once, use everywhere)
- ✅ **Type-safe** (type is `int`, not union)
- ✅ **Composable** (can chain validators)
- ✅ **Optimizable** by Pydantic's Rust core
- ✅ **Declarative** (validation is part of type)

**Cons**:
- ⚠️ Requires understanding Annotated (but standard Python typing)

---

**Option C: Custom Pydantic Types** ❌
```python
class SizeStr:
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        # Complex schema definition
        ...

max_bytes: SizeStr
```
**Pros**: Maximum control
**Cons**:
- ❌ Overly complex for this use case
- ❌ Hard to maintain
- ❌ More code than benefit

---

### Decision: Option B (Annotated + BeforeValidator)

**Rationale:**
1. **Aligns with Pydantic v2 philosophy** - We're heavily invested in Pydantic v2, should use its native patterns
2. **Follows official recommendations** - Pydantic v2 docs recommend Annotated validators
3. **Reusable** - Define SizeField once, use in 10+ models
4. **Type-safe** - mypy/pyright see `int`, not `int | str`
5. **Composable** - Can add AfterValidator for additional checks
6. **Future-proof** - Pydantic v2 optimizes these better than field_validator
7. **Clean API** - Users see `SizeField` in type hints (clear intent)

**Precedent:** This is the recommended pattern in Pydantic v2 migration guide and official documentation.

## Implementation Notes

### File Structure

```
src/fapilog/core/types.py (NEW)
src/fapilog/core/settings.py (MODIFIED - use new types)
tests/unit/test_parsers.py (NEW)
tests/unit/test_annotated_types.py (NEW)
tests/integration/test_settings_strings.py (NEW)
```

### Implementation Steps

#### Step 1: Create Parser Functions and Annotated Types

**File**: `src/fapilog/core/types.py` (NEW)

```python
"""Pydantic v2 custom types for human-readable configuration.

This module provides Annotated types that accept human-readable strings
for sizes and durations, automatically converting them to appropriate
numeric types via BeforeValidator.

Examples:
    >>> from fapilog.core.settings import RotatingFileSettings
    >>>
    >>> # Size parsing
    >>> settings = RotatingFileSettings(max_bytes="10 MB")
    >>> settings.max_bytes
    10485760
    >>>
    >>> # Duration parsing
    >>> settings = RotatingFileSettings(interval_seconds="daily")
    >>> settings.interval_seconds
    86400.0
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BeforeValidator

# ============================================================================
# Parser Functions (Private - for logic only)
# ============================================================================

SIZE_UNITS = {
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}

# Matches: "10 MB", "10MB", "10.5 GB", etc.
SIZE_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMGT]?B)$", re.IGNORECASE)


def _parse_size(value: str | int | None) -> int | None:
    """Parse size string to bytes.

    Args:
        value: Size as string ("10 MB"), int (bytes), or None

    Returns:
        Size in bytes or None if input is None

    Raises:
        ValueError: If string format is invalid or value is negative

    Examples:
        >>> _parse_size("10 MB")
        10485760
        >>> _parse_size("1.5 GB")
        1610612736
        >>> _parse_size(1024)
        1024
        >>> _parse_size(None)
        None
    """
    if value is None:
        return None

    if isinstance(value, int):
        if value < 0:
            raise ValueError("Size must be non-negative")
        return value

    # Parse string
    value_str = str(value).strip()
    match = SIZE_PATTERN.match(value_str)

    if not match:
        raise ValueError(
            f"Invalid size format: '{value_str}'. "
            f"Use format like '10 MB' (units: KB, MB, GB, TB)"
        )

    number_str, unit_str = match.groups()
    number = float(number_str)
    multiplier = SIZE_UNITS[unit_str.lower()]

    result = number * multiplier

    if result < 0:
        raise ValueError("Size must be non-negative")

    return int(result)


DURATION_UNITS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}

ROTATION_INTERVALS = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
}

# Matches: "5s", "10m", "1h", "7d", "2w"
DURATION_PATTERN = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)


def _parse_duration(value: str | int | float | None) -> float | None:
    """Parse duration string to seconds.

    Args:
        value: Duration as string ("5s", "daily"), number (seconds), or None

    Returns:
        Duration in seconds or None if input is None

    Raises:
        ValueError: If string format is invalid or value is negative

    Examples:
        >>> _parse_duration("5s")
        5.0
        >>> _parse_duration("10m")
        600.0
        >>> _parse_duration("daily")
        86400.0
        >>> _parse_duration(3600)
        3600.0
        >>> _parse_duration(None)
        None
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("Duration must be non-negative")
        return float(value)

    # Parse string
    value_str = str(value).strip().lower()

    # Check for rotation keywords
    if value_str in ROTATION_INTERVALS:
        return float(ROTATION_INTERVALS[value_str])

    # Parse duration units
    match = DURATION_PATTERN.match(value_str)

    if not match:
        valid_keywords = ", ".join(f"'{k}'" for k in ROTATION_INTERVALS.keys())
        raise ValueError(
            f"Invalid duration format: '{value}'. "
            f"Use format like '5s', '10m', '1h', '7d' or keywords: {valid_keywords}"
        )

    number_str, unit_str = match.groups()
    number = int(number_str)
    multiplier = DURATION_UNITS[unit_str.lower()]

    result = number * multiplier

    if result < 0:
        raise ValueError("Duration must be non-negative")

    return float(result)


# ============================================================================
# Public Annotated Types
# ============================================================================

SizeField = Annotated[
    int,
    BeforeValidator(_parse_size),
]
"""Type for size fields that accepts human-readable strings.

Accepts:
    - Integers: raw bytes (e.g., 10485760)
    - Strings: human-readable sizes (e.g., "10 MB", "1.5 GB")

Units: KB, MB, GB, TB (case-insensitive)

Examples:
    >>> class MyModel(BaseModel):
    ...     size: SizeField
    >>>
    >>> MyModel(size="10 MB").size
    10485760
    >>> MyModel(size=1024).size
    1024
"""

DurationField = Annotated[
    float,
    BeforeValidator(_parse_duration),
]
"""Type for duration fields that accepts human-readable strings.

Accepts:
    - Numbers: raw seconds (e.g., 3600, 3600.5)
    - Strings: human-readable durations (e.g., "1h", "daily")

Units: s, m, h, d, w (case-insensitive)
Keywords: hourly, daily, weekly (case-insensitive)

Examples:
    >>> class MyModel(BaseModel):
    ...     interval: DurationField
    >>>
    >>> MyModel(interval="1h").interval
    3600.0
    >>> MyModel(interval="daily").interval
    86400.0
    >>> MyModel(interval=60).interval
    60.0
"""

OptionalSizeField = Annotated[
    int | None,
    BeforeValidator(_parse_size),
]
"""Optional variant of SizeField (allows None)."""

OptionalDurationField = Annotated[
    float | None,
    BeforeValidator(_parse_duration),
]
"""Optional variant of DurationField (allows None)."""


__all__ = [
    "SizeField",
    "DurationField",
    "OptionalSizeField",
    "OptionalDurationField",
]
```

#### Step 2: Update Settings to Use New Types

**File**: `src/fapilog/core/settings.py` (MODIFIED)

```python
"""Settings models for fapilog."""

from __future__ import annotations

# ... existing imports ...

from .types import (
    DurationField,
    OptionalDurationField,
    OptionalSizeField,
    SizeField,
)


class RotatingFileSettings(BaseModel):
    """Per-plugin configuration for RotatingFileSink."""

    directory: str | None = Field(
        default=None, description="Log directory for rotating file sink"
    )
    filename_prefix: str = Field(default="fapilog", description="Filename prefix")
    mode: Literal["json", "text"] = Field(
        default="json", description="Output format: json or text"
    )

    # UPDATED: Now accepts strings like "10 MB"
    max_bytes: SizeField = Field(
        default=10 * 1024 * 1024,
        description="Max bytes before rotation. Accepts '10 MB' or 10485760",
    )

    # UPDATED: Now accepts strings like "1h" or "daily"
    interval_seconds: OptionalDurationField = Field(
        default=None,
        description="Rotation interval. Accepts '1h', 'daily', or 3600",
    )

    max_files: int | None = Field(
        default=None, description="Max number of rotated files to keep"
    )

    # UPDATED: Now accepts strings like "100 MB"
    max_total_bytes: OptionalSizeField = Field(
        default=None,
        description="Max total bytes across all files. Accepts '100 MB' or 104857600",
    )

    compress_rotated: bool = Field(
        default=False, description="Compress rotated log files with gzip"
    )


class WebhookSettings(BaseModel):
    """Per-plugin configuration for WebhookSink."""

    endpoint: str | None = Field(default=None, description="Webhook destination URL")
    secret: str | None = Field(default=None, description="Shared secret for signing")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Additional HTTP headers"
    )
    retry_max_attempts: int | None = Field(
        default=None, ge=1, description="Maximum retry attempts on failure"
    )

    # UPDATED: Now accepts strings like "2s"
    retry_backoff_seconds: OptionalDurationField = Field(
        default=None,
        description="Backoff between retries. Accepts '2s' or 2.0",
    )

    # UPDATED: Now accepts strings like "5s"
    timeout_seconds: DurationField = Field(
        default=5.0,
        description="Request timeout. Accepts '5s' or 5.0",
    )

    batch_size: int = Field(
        default=1,
        ge=1,
        description="Maximum events per webhook request (1 = no batching)",
    )

    # UPDATED: Now accepts strings like "5s"
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        description="Max seconds before flushing partial batch. Accepts '5s' or 5.0",
    )


class SizeGuardSettings(BaseModel):
    """Per-processor configuration for SizeGuard."""

    enabled: bool = Field(default=False, description="Enable size guard processor")

    # UPDATED: Now accepts strings like "10 MB"
    max_bytes: SizeField = Field(
        default=1 * 1024 * 1024,
        description="Max bytes per log entry. Accepts '1 MB' or 1048576",
    )

    action: Literal["drop", "truncate"] = Field(
        default="truncate",
        description="Action to take when payload exceeds max_bytes",
    )


class HttpSinkSettings(BaseModel):
    """Configuration for HTTP sink."""

    endpoint: str | None = Field(default=None, description="HTTP endpoint URL")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Additional HTTP headers"
    )

    # UPDATED: Now accepts strings like "30s"
    timeout_seconds: DurationField = Field(
        default=30.0,
        description="Request timeout. Accepts '30s' or 30.0",
    )

    batch_size: int = Field(default=100, ge=1, description="Events per batch")

    # UPDATED: Now accepts strings like "5s"
    batch_timeout_seconds: DurationField = Field(
        default=5.0,
        description="Batch flush timeout. Accepts '5s' or 5.0",
    )

    # ... rest unchanged


# Update all other Settings classes similarly:
# - LokiSinkSettings: timeout_seconds, batch_timeout_seconds, retry_base_delay
# - CloudWatchSinkSettings: batch_timeout_seconds, retry_base_delay
# - PostgresSinkSettings: timeout, retry_delay
# etc.
```

#### Step 3: Export Types from Core

**File**: `src/fapilog/core/__init__.py` (MODIFIED)

```python
"""Core fapilog components."""

from .types import (
    DurationField,
    OptionalDurationField,
    OptionalSizeField,
    SizeField,
)

__all__ = [
    # ... existing exports ...
    "SizeField",
    "DurationField",
    "OptionalSizeField",
    "OptionalDurationField",
]
```

### Usage Examples

```python
# Example 1: Simple usage with strings
from fapilog import get_logger, Settings
from fapilog.core.settings import RotatingFileSettings

settings = Settings(
    file=RotatingFileSettings(
        max_bytes="10 MB",
        interval_seconds="daily",
        max_total_bytes="100 MB",
    )
)
logger = get_logger(settings=settings)

# Example 2: Mixed strings and integers
settings = Settings(
    file=RotatingFileSettings(
        max_bytes="10 MB",        # String
        interval_seconds=3600,     # Integer (still works)
        max_files=7,               # Integer
    )
)

# Example 3: With preset (Story 10.1 integration)
from fapilog.core.settings import Settings, RotatingFileSettings

settings = Settings(
    preset="production",  # Story 10.1 preset
    file=RotatingFileSettings(
        max_bytes="50 MB",  # Override preset with string
        interval_seconds="hourly",
    )
)

# Example 4: Direct instantiation
config = RotatingFileSettings(
    directory="./logs",
    max_bytes="25 MB",
    interval_seconds="2h",
    max_files=10,
    compress_rotated=True,
)
```

### Type Checking Examples

```python
from fapilog.core.settings import RotatingFileSettings

# Static type checkers understand the types:
settings = RotatingFileSettings(max_bytes="10 MB")

# mypy/pyright knows this is int:
x: int = settings.max_bytes  # ✅ Type checks

# This is an error:
y: str = settings.max_bytes  # ❌ Type error: Expected str, got int

# IDE autocomplete shows:
settings.max_bytes  # Type: int
```

## Tasks

### Phase 1: Parser Implementation

- [ ] Create `src/fapilog/core/types.py` module
- [ ] Implement `_parse_size()` function
- [ ] Implement `_parse_duration()` function
- [ ] Define SIZE_UNITS dictionary (KB, MB, GB, TB)
- [ ] Define DURATION_UNITS dictionary (s, m, h, d, w)
- [ ] Define ROTATION_INTERVALS dictionary (hourly, daily, weekly)
- [ ] Create SIZE_PATTERN regex
- [ ] Create DURATION_PATTERN regex
- [ ] Add comprehensive docstrings with examples

### Phase 2: Annotated Type Definitions

- [ ] Define `SizeField` Annotated type
- [ ] Define `DurationField` Annotated type
- [ ] Define `OptionalSizeField` Annotated type
- [ ] Define `OptionalDurationField` Annotated type
- [ ] Add type documentation strings
- [ ] Export from `src/fapilog/core/__init__.py`

### Phase 3: Settings Integration

- [ ] Update `RotatingFileSettings.max_bytes` to use SizeField
- [ ] Update `RotatingFileSettings.interval_seconds` to use DurationField
- [ ] Update `RotatingFileSettings.max_total_bytes` to use OptionalSizeField
- [ ] Update `WebhookSettings.timeout_seconds` to use DurationField
- [ ] Update `WebhookSettings.retry_backoff_seconds` to use OptionalDurationField
- [ ] Update `WebhookSettings.batch_timeout_seconds` to use DurationField
- [ ] Update `SizeGuardSettings.max_bytes` to use SizeField
- [ ] Update `HttpSinkSettings.timeout_seconds` to use DurationField
- [ ] Update `HttpSinkSettings.batch_timeout_seconds` to use DurationField
- [ ] Update `LokiSinkSettings` duration fields
- [ ] Update `CloudWatchSinkSettings` duration fields
- [ ] Update `PostgresSinkSettings` duration fields
- [ ] Update all field descriptions to mention string formats

### Phase 4: Testing

- [ ] Create `tests/unit/test_parsers.py`
- [ ] Test `_parse_size()` with valid inputs
- [ ] Test `_parse_size()` with invalid inputs
- [ ] Test `_parse_size()` edge cases (negative, zero, overflow)
- [ ] Test `_parse_size()` case insensitivity
- [ ] Test `_parse_size()` decimal numbers
- [ ] Test `_parse_size()` whitespace handling
- [ ] Test `_parse_duration()` with valid inputs
- [ ] Test `_parse_duration()` with invalid inputs
- [ ] Test `_parse_duration()` rotation keywords
- [ ] Test `_parse_duration()` case insensitivity
- [ ] Create `tests/unit/test_annotated_types.py`
- [ ] Test SizeField in Pydantic model
- [ ] Test DurationField in Pydantic model
- [ ] Test OptionalSizeField (with None)
- [ ] Test OptionalDurationField (with None)
- [ ] Create `tests/integration/test_settings_strings.py`
- [ ] Test RotatingFileSettings with all string formats
- [ ] Test Settings with preset + string overrides
- [ ] Test backward compatibility (integers still work)
- [ ] Test error messages are clear

### Phase 5: Documentation

- [ ] Update `README.md` with string format examples
- [ ] Update `docs/user-guide/configuration.md` with string formats
- [ ] Create `docs/api-reference/types.md` documenting custom types
- [ ] Update `docs/user-guide/comparisons.md` (vs loguru)
- [ ] Create `examples/string_config/` with examples
- [ ] Update `CHANGELOG.md`

## Tests

### Unit Tests (`tests/unit/test_parsers.py`)

```python
"""Unit tests for size and duration parsers."""

import pytest

from fapilog.core.types import _parse_duration, _parse_size


class TestParseSize:
    """Test _parse_size parser function."""

    def test_parse_size_kilobytes(self):
        """Parse kilobytes to bytes."""
        assert _parse_size("10 KB") == 10 * 1024
        assert _parse_size("1KB") == 1024
        assert _parse_size("5 kb") == 5 * 1024

    def test_parse_size_megabytes(self):
        """Parse megabytes to bytes."""
        assert _parse_size("10 MB") == 10 * 1024 * 1024
        assert _parse_size("1MB") == 1024 * 1024
        assert _parse_size("50 mb") == 50 * 1024 * 1024

    def test_parse_size_gigabytes(self):
        """Parse gigabytes to bytes."""
        assert _parse_size("1 GB") == 1024**3
        assert _parse_size("2GB") == 2 * 1024**3

    def test_parse_size_terabytes(self):
        """Parse terabytes to bytes."""
        assert _parse_size("1 TB") == 1024**4
        assert _parse_size("2TB") == 2 * 1024**4

    def test_parse_size_bytes(self):
        """Parse bytes unit."""
        assert _parse_size("100 B") == 100
        assert _parse_size("1024B") == 1024

    def test_parse_size_decimal_numbers(self):
        """Parse decimal numbers."""
        assert _parse_size("10.5 MB") == int(10.5 * 1024 * 1024)
        assert _parse_size("0.5 GB") == int(0.5 * 1024**3)
        assert _parse_size("1.25 KB") == int(1.25 * 1024)

    def test_parse_size_case_insensitive(self):
        """All case variations work."""
        assert _parse_size("10 MB") == _parse_size("10 mb")
        assert _parse_size("10 MB") == _parse_size("10 Mb")
        assert _parse_size("10 MB") == _parse_size("10 mB")

    def test_parse_size_whitespace_flexible(self):
        """Whitespace variations work."""
        assert _parse_size("10 MB") == _parse_size("10MB")
        assert _parse_size("10 MB") == _parse_size("10  MB")
        assert _parse_size("10 MB") == _parse_size(" 10 MB ")

    def test_parse_size_integer_passthrough(self):
        """Integers pass through unchanged."""
        assert _parse_size(10485760) == 10485760
        assert _parse_size(1024) == 1024
        assert _parse_size(0) == 0

    def test_parse_size_none_passthrough(self):
        """None passes through unchanged."""
        assert _parse_size(None) is None

    def test_parse_size_invalid_unit(self):
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("10 XB")

        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("10 PB")  # Petabytes not supported

    def test_parse_size_invalid_number(self):
        """Invalid number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("ten MB")

        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("MB 10")

    def test_parse_size_negative_number(self):
        """Negative size raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _parse_size(-1024)

    def test_parse_size_empty_string(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid size format"):
            _parse_size("")

    def test_parse_size_error_message_includes_input(self):
        """Error message shows original input."""
        with pytest.raises(ValueError, match="'10 XB'"):
            _parse_size("10 XB")


class TestParseDuration:
    """Test _parse_duration parser function."""

    def test_parse_duration_seconds(self):
        """Parse seconds."""
        assert _parse_duration("5s") == 5.0
        assert _parse_duration("30s") == 30.0
        assert _parse_duration("1S") == 1.0

    def test_parse_duration_minutes(self):
        """Parse minutes to seconds."""
        assert _parse_duration("1m") == 60.0
        assert _parse_duration("10m") == 600.0
        assert _parse_duration("5M") == 300.0

    def test_parse_duration_hours(self):
        """Parse hours to seconds."""
        assert _parse_duration("1h") == 3600.0
        assert _parse_duration("2h") == 7200.0
        assert _parse_duration("24H") == 86400.0

    def test_parse_duration_days(self):
        """Parse days to seconds."""
        assert _parse_duration("1d") == 86400.0
        assert _parse_duration("7d") == 604800.0
        assert _parse_duration("30D") == 2592000.0

    def test_parse_duration_weeks(self):
        """Parse weeks to seconds."""
        assert _parse_duration("1w") == 604800.0
        assert _parse_duration("2w") == 1209600.0
        assert _parse_duration("4W") == 2419200.0

    def test_parse_duration_rotation_keywords(self):
        """Parse rotation keywords."""
        assert _parse_duration("hourly") == 3600.0
        assert _parse_duration("daily") == 86400.0
        assert _parse_duration("weekly") == 604800.0

    def test_parse_duration_keywords_case_insensitive(self):
        """Rotation keywords are case insensitive."""
        assert _parse_duration("HOURLY") == 3600.0
        assert _parse_duration("Daily") == 86400.0
        assert _parse_duration("Weekly") == 604800.0

    def test_parse_duration_integer_passthrough(self):
        """Integers pass through as floats."""
        assert _parse_duration(3600) == 3600.0
        assert _parse_duration(60) == 60.0
        assert _parse_duration(0) == 0.0

    def test_parse_duration_float_passthrough(self):
        """Floats pass through unchanged."""
        assert _parse_duration(3600.5) == 3600.5
        assert _parse_duration(0.5) == 0.5

    def test_parse_duration_none_passthrough(self):
        """None passes through unchanged."""
        assert _parse_duration(None) is None

    def test_parse_duration_invalid_unit(self):
        """Invalid unit raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("10x")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("10 min")  # Must be "10m" not "10 min"

    def test_parse_duration_invalid_keyword(self):
        """Invalid keyword raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("monthly")

        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("yearly")

    def test_parse_duration_invalid_number(self):
        """Invalid number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            _parse_duration("ten s")

    def test_parse_duration_negative_number(self):
        """Negative duration raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            _parse_duration(-60)

    def test_parse_duration_error_message_shows_valid_formats(self):
        """Error message shows valid formats."""
        with pytest.raises(
            ValueError, match="Use format like '5s', '10m', '1h', '7d'"
        ):
            _parse_duration("invalid")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_size_max_value(self):
        """Very large sizes work."""
        result = _parse_size("9999 TB")
        assert result > 0

    def test_parse_size_min_value(self):
        """Zero size works."""
        assert _parse_size("0 MB") == 0
        assert _parse_size(0) == 0

    def test_parse_duration_max_value(self):
        """Very large durations work."""
        result = _parse_duration("9999w")
        assert result > 0

    def test_parse_duration_min_value(self):
        """Zero duration works."""
        assert _parse_duration("0s") == 0.0
        assert _parse_duration(0) == 0.0
```

### Annotated Type Tests (`tests/unit/test_annotated_types.py`)

```python
"""Test Pydantic Annotated types."""

import pytest
from pydantic import BaseModel, ValidationError

from fapilog.core.types import (
    DurationField,
    OptionalDurationField,
    OptionalSizeField,
    SizeField,
)


class TestSizeField:
    """Test SizeField Annotated type."""

    def test_size_field_accepts_string(self):
        """SizeField accepts string input."""

        class Model(BaseModel):
            size: SizeField

        m = Model(size="10 MB")
        assert m.size == 10 * 1024 * 1024
        assert isinstance(m.size, int)

    def test_size_field_accepts_integer(self):
        """SizeField accepts integer input."""

        class Model(BaseModel):
            size: SizeField

        m = Model(size=1048576)
        assert m.size == 1048576

    def test_size_field_validation_error(self):
        """SizeField raises ValidationError on invalid input."""

        class Model(BaseModel):
            size: SizeField

        with pytest.raises(ValidationError) as exc_info:
            Model(size="10 XB")

        error = exc_info.value.errors()[0]
        assert "Invalid size format" in str(error["ctx"]["error"])

    def test_size_field_type_annotation(self):
        """SizeField resolves to int for type checkers."""

        class Model(BaseModel):
            size: SizeField

        m = Model(size="10 MB")

        # Runtime type is int
        assert isinstance(m.size, int)


class TestDurationField:
    """Test DurationField Annotated type."""

    def test_duration_field_accepts_string(self):
        """DurationField accepts string input."""

        class Model(BaseModel):
            duration: DurationField

        m = Model(duration="1h")
        assert m.duration == 3600.0
        assert isinstance(m.duration, float)

    def test_duration_field_accepts_number(self):
        """DurationField accepts numeric input."""

        class Model(BaseModel):
            duration: DurationField

        m = Model(duration=3600)
        assert m.duration == 3600.0

        m2 = Model(duration=3600.5)
        assert m2.duration == 3600.5

    def test_duration_field_accepts_keyword(self):
        """DurationField accepts rotation keywords."""

        class Model(BaseModel):
            duration: DurationField

        m = Model(duration="daily")
        assert m.duration == 86400.0

    def test_duration_field_validation_error(self):
        """DurationField raises ValidationError on invalid input."""

        class Model(BaseModel):
            duration: DurationField

        with pytest.raises(ValidationError) as exc_info:
            Model(duration="invalid")

        error = exc_info.value.errors()[0]
        assert "Invalid duration format" in str(error["ctx"]["error"])


class TestOptionalFields:
    """Test optional variants."""

    def test_optional_size_field_accepts_none(self):
        """OptionalSizeField accepts None."""

        class Model(BaseModel):
            size: OptionalSizeField

        m = Model(size=None)
        assert m.size is None

    def test_optional_size_field_accepts_value(self):
        """OptionalSizeField accepts values."""

        class Model(BaseModel):
            size: OptionalSizeField

        m = Model(size="10 MB")
        assert m.size == 10 * 1024 * 1024

    def test_optional_duration_field_accepts_none(self):
        """OptionalDurationField accepts None."""

        class Model(BaseModel):
            duration: OptionalDurationField

        m = Model(duration=None)
        assert m.duration is None

    def test_optional_duration_field_accepts_value(self):
        """OptionalDurationField accepts values."""

        class Model(BaseModel):
            duration: OptionalDurationField

        m = Model(duration="1h")
        assert m.duration == 3600.0


class TestFieldDefaults:
    """Test fields with default values."""

    def test_size_field_with_default(self):
        """SizeField works with default values."""

        class Model(BaseModel):
            size: SizeField = 1024

        m1 = Model()
        assert m1.size == 1024

        m2 = Model(size="10 MB")
        assert m2.size == 10 * 1024 * 1024

    def test_optional_field_defaults_to_none(self):
        """Optional fields default to None."""

        class Model(BaseModel):
            size: OptionalSizeField = None
            duration: OptionalDurationField = None

        m = Model()
        assert m.size is None
        assert m.duration is None
```

### Integration Tests (`tests/integration/test_settings_strings.py`)

```python
"""Integration tests for Settings with string configuration."""

import pytest
from pydantic import ValidationError

from fapilog import Settings
from fapilog.core.settings import RotatingFileSettings, WebhookSettings


class TestRotatingFileSettingsStrings:
    """Test RotatingFileSettings with string values."""

    def test_all_fields_accept_strings(self):
        """All size/duration fields accept strings."""
        settings = RotatingFileSettings(
            max_bytes="10 MB",
            interval_seconds="1h",
            max_total_bytes="100 MB",
        )

        assert settings.max_bytes == 10 * 1024 * 1024
        assert settings.interval_seconds == 3600.0
        assert settings.max_total_bytes == 100 * 1024 * 1024

    def test_rotation_keywords(self):
        """Rotation keywords work."""
        settings = RotatingFileSettings(
            interval_seconds="hourly",
        )
        assert settings.interval_seconds == 3600.0

        settings = RotatingFileSettings(
            interval_seconds="daily",
        )
        assert settings.interval_seconds == 86400.0

    def test_mixed_strings_and_integers(self):
        """Strings and integers can be mixed."""
        settings = RotatingFileSettings(
            max_bytes="10 MB",       # String
            interval_seconds=3600,    # Integer
            max_files=7,              # Integer
            max_total_bytes="50 MB",  # String
        )

        assert settings.max_bytes == 10 * 1024 * 1024
        assert settings.interval_seconds == 3600.0
        assert settings.max_files == 7
        assert settings.max_total_bytes == 50 * 1024 * 1024

    def test_backward_compatibility(self):
        """Existing integer config still works."""
        # Old way (all integers)
        settings = RotatingFileSettings(
            max_bytes=10485760,
            interval_seconds=86400,
            max_total_bytes=104857600,
        )

        assert settings.max_bytes == 10485760
        assert settings.interval_seconds == 86400.0
        assert settings.max_total_bytes == 104857600


class TestWebhookSettingsStrings:
    """Test WebhookSettings with string durations."""

    def test_timeout_accepts_string(self):
        """timeout_seconds accepts string."""
        settings = WebhookSettings(
            endpoint="https://example.com/webhook",
            timeout_seconds="10s",
        )

        assert settings.timeout_seconds == 10.0

    def test_all_duration_fields_accept_strings(self):
        """All duration fields accept strings."""
        settings = WebhookSettings(
            endpoint="https://example.com/webhook",
            timeout_seconds="30s",
            retry_backoff_seconds="2s",
            batch_timeout_seconds="5s",
        )

        assert settings.timeout_seconds == 30.0
        assert settings.retry_backoff_seconds == 2.0
        assert settings.batch_timeout_seconds == 5.0


class TestSettingsValidationErrors:
    """Test validation error messages."""

    def test_invalid_size_error_message(self):
        """Invalid size shows clear error."""
        with pytest.raises(ValidationError) as exc_info:
            RotatingFileSettings(max_bytes="10 XB")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "max_bytes" in str(errors[0]["loc"])
        assert "Invalid size format" in str(errors[0]["ctx"]["error"])
        assert "'10 XB'" in str(errors[0]["ctx"]["error"])

    def test_invalid_duration_error_message(self):
        """Invalid duration shows clear error."""
        with pytest.raises(ValidationError) as exc_info:
            RotatingFileSettings(interval_seconds="10x")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "interval_seconds" in str(errors[0]["loc"])
        assert "Invalid duration format" in str(errors[0]["ctx"]["error"])


class TestSettingsWithPreset:
    """Test Settings with preset and string overrides."""

    def test_preset_with_string_overrides(self):
        """Preset + string overrides work together."""
        from fapilog import get_logger

        # This should work (pending Story 10.1 implementation)
        # settings = Settings(
        #     preset="production",
        #     file=RotatingFileSettings(max_bytes="50 MB")
        # )

        # For now, test Settings alone
        settings = Settings(
            file=RotatingFileSettings(
                max_bytes="50 MB",
                interval_seconds="daily",
            )
        )

        assert settings.file.max_bytes == 50 * 1024 * 1024
        assert settings.file.interval_seconds == 86400.0
```

## Definition of Done

### Code Complete
- [ ] `src/fapilog/core/types.py` created with all parsers and types
- [ ] `_parse_size()` function implemented
- [ ] `_parse_duration()` function implemented
- [ ] `SizeField` Annotated type defined
- [ ] `DurationField` Annotated type defined
- [ ] `OptionalSizeField` defined
- [ ] `OptionalDurationField` defined
- [ ] All Settings classes updated to use new types
- [ ] All field descriptions updated to mention string formats
- [ ] Types exported from `src/fapilog/core/__init__.py`

### Quality Assurance
- [ ] Unit tests: >95% coverage of types.py
- [ ] All size parsing tests passing (valid, invalid, edge cases)
- [ ] All duration parsing tests passing (valid, invalid, keywords)
- [ ] Annotated type tests passing (Pydantic integration)
- [ ] Integration tests passing (Settings with strings)
- [ ] Backward compatibility tests passing (integers still work)
- [ ] Error message tests passing (clear, helpful messages)
- [ ] Type checking tests passing (mypy/pyright)
- [ ] No regression in existing tests

### Type Safety
- [ ] mypy passes with strict mode
- [ ] pyright passes
- [ ] IDE autocomplete shows SizeField/DurationField
- [ ] Type hints resolve to int/float (not unions)
- [ ] Type stubs updated if needed

### Documentation
- [ ] `README.md` updated with string format examples
- [ ] `docs/user-guide/configuration.md` documents string formats
- [ ] `docs/api-reference/types.md` created (NEW)
- [ ] Type docstrings include examples
- [ ] Field descriptions mention both string and numeric formats
- [ ] `docs/user-guide/comparisons.md` updated (vs loguru)
- [ ] `examples/string_config/` created with examples
- [ ] `CHANGELOG.md` updated with feature announcement

### Integration with Other Stories
- [ ] Story 10.1: Preset strings work with new types
- [ ] Story 10.2: Dev preset strings work
- [ ] Story 10.3: setup_logging() strings work
- [ ] Verify: All existing Settings continue to work

### Review & Release
- [ ] Code review approved
- [ ] Documentation reviewed for clarity
- [ ] CI/CD pipeline passing
- [ ] No performance regression
- [ ] Ready for merge

## Risks / Rollback / Monitoring

### Risks

1. **Risk**: Parsing overhead impacts performance
   - **Mitigation**: BeforeValidator runs once during validation, not per-access
   - **Mitigation**: Regex patterns are pre-compiled
   - **Mitigation**: Performance benchmarks enforce < 1ms overhead

2. **Risk**: Type confusion (users think it's int | str)
   - **Mitigation**: Clear documentation that type is int/float
   - **Mitigation**: Type hints show SizeField (not union)
   - **Mitigation**: Examples show both formats work

3. **Risk**: Breaking changes to existing config
   - **Mitigation**: Backward compatibility tests ensure integers work
   - **Mitigation**: BeforeValidator passes integers through unchanged
   - **Mitigation**: Zero breaking changes

4. **Risk**: Pydantic v2 API changes in future
   - **Mitigation**: Using recommended Annotated pattern (stable API)
   - **Mitigation**: Parser functions are independent of Pydantic
   - **Mitigation**: Can switch validator approach if needed

5. **Risk**: Users expect more units (PB, EB, etc.)
   - **Mitigation**: Clear error messages show supported units
   - **Mitigation**: Can add more units in future without breaking changes

### Rollback Plan

If string parsing causes issues:

1. **Easy rollback**: Revert Settings classes to int fields
   ```python
   # Revert to:
   max_bytes: int  # Remove SizeField
   ```

2. **Keep parsers available**: Users can still call explicitly
   ```python
   from fapilog.core.types import _parse_size
   max_bytes = _parse_size("10 MB")
   ```

3. **Full removal**: Delete `types.py`, revert all Settings
   - Isolated to one file (minimal churn)
   - No API surface changes (internal implementation)

### Success Metrics

**Quantitative:**
- [ ] Parsing overhead < 1ms (measured)
- [ ] No performance regression in Settings instantiation
- [ ] Type checking passes (mypy strict mode)

**Qualitative:**
- [ ] Developer feedback: "Much easier than calculating bytes"
- [ ] GitHub issues: No confusion about string formats
- [ ] Documentation: Examples reduce questions

### Monitoring

- Track string format usage (if telemetry added)
- Monitor GitHub issues for parsing errors
- Collect user feedback on string formats
- Watch for type checking issues

## Dependencies

- **Depends on**: None (standalone feature)
- **Enhances**: Story 10.1 (Presets can use strings)
- **Enhances**: Story 10.3 (setup_logging can use strings)
- **Blocks**: Story 10.5 (Simplified File Rotation API needs parsers)

## Estimated Effort

- **Implementation**: 6 hours
  - types.py creation: 3 hours
  - Settings updates: 2 hours
  - Integration: 1 hour

- **Testing**: 4 hours
  - Parser unit tests: 2 hours
  - Annotated type tests: 1 hour
  - Integration tests: 1 hour

- **Documentation**: 2 hours
  - API docs: 1 hour
  - Examples: 1 hour

- **Total**: 10-12 hours for one developer

## Related Stories

- **Story 10.1**: Configuration Presets (can use string formats)
- **Story 10.2**: Pretty Console Output (uses durations)
- **Story 10.3**: FastAPI One-Liner (can use string config)
- **Story 10.5**: Simplified File Rotation API (uses parsers)
- **Future**: Combined retention (`retention={"count": 7, "age": "30 days"}`)
- **Future**: Multi-unit parsing ("1h 30m")
- **Future**: Time-of-day rotation ("00:00" cron-like)

## Change Log

| Date       | Change                                    | Author |
| ---------- | ----------------------------------------- | ------ |
| 2025-01-11 | Initial story creation (implementation-ready) | Claude |
