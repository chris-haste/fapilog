# Types

Reusable Pydantic Annotated types for human-readable sizes and durations.

These types are used across settings models and can be reused in custom configs.

## SizeField

Accepts:
- Integers: raw bytes (e.g., `10485760`)
- Strings: human-readable sizes (e.g., `"10 MB"`, `"1024B"`)

Formats:
- Units: `B`, `KB`, `MB`, `GB`, `TB` (case-insensitive)
- Optional whitespace: `"10MB"`, `"10 MB"`, `" 10 MB "`
- Decimals allowed with units: `"10.5 MB"`
- Numeric strings without units are treated as raw bytes: `"10485760"`

## DurationField

Accepts:
- Numbers: raw seconds (e.g., `3600`, `0.25`)
- Strings: human-readable durations (e.g., `"5s"`, `"1h"`, `"100ms"`)

Formats:
- Units: `ms`, `s`, `m`, `h`, `d`, `w` (case-insensitive)
- Optional whitespace: `"5s"`, `"5 s"`, `"100 ms"`
- Decimals with units: `"0.5s"`, `"1.5h"`, `"2.5d"`
- Numeric strings (including decimals) are treated as raw seconds: `"9.5"`

Examples:
```python
_parse_duration("100ms")   # 0.1 seconds
_parse_duration("500ms")   # 0.5 seconds
_parse_duration("0.5s")    # 0.5 seconds
_parse_duration("1.5h")    # 5400.0 seconds
_parse_duration("2.5d")    # 216000.0 seconds
```

## RotationDurationField

Accepts:
- All `DurationField` formats
- Rotation keywords: `hourly`, `daily`, `weekly` (case-insensitive)

Note: rotation keywords represent fixed intervals (e.g., `"daily"` means every 24 hours),
not wall-clock boundaries.

## Optional Variants

- `OptionalSizeField` accepts `None` in addition to valid sizes.
- `OptionalDurationField` accepts `None` in addition to valid durations.
- `OptionalRotationDurationField` accepts `None` in addition to valid rotation
  durations.

## Usage

```python
from pydantic import BaseModel
from fapilog.core.types import DurationField, RotationDurationField, SizeField


class MyConfig(BaseModel):
    max_bytes: SizeField
    timeout_seconds: DurationField
    interval_seconds: RotationDurationField


cfg = MyConfig(max_bytes="10 MB", timeout_seconds="5s", interval_seconds="daily")
assert cfg.max_bytes == 10 * 1024 * 1024
assert cfg.timeout_seconds == 5.0
assert cfg.interval_seconds == 86400.0
```
