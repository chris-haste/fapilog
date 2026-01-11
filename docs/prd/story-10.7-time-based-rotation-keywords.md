# Story 10.7: Time-Based Rotation Keywords

**Epic**: Epic 10 - Developer Experience & Ergonomics Improvements
**Status**: Implementation-Ready
**Priority**: Medium (Phase 2: API Improvements)
**Estimated Complexity**: Low (2-3 days)

---

## User Story

**As a** developer,
**I want** to use human-readable time keywords for log rotation (e.g., "daily", "hourly"),
**So that** I don't have to calculate seconds for common rotation intervals.

---

## Business Value

### Current Pain Points:
1. **Time calculation required**: Must convert "daily" to 86400 seconds manually
2. **Not intuitive**: `interval_seconds=86400` doesn't obviously mean "daily"
3. **DX gap vs loguru**: Loguru supports `rotation="daily"`, fapilog requires calculation
4. **Error-prone**: Easy to miscalculate (hourly = 3600, not 360 or 36000)

### After This Story:

**Loguru:**
```python
logger.add("file.log", rotation="daily")
```

**Fapilog (Story 10.7):**
```python
from fapilog.sinks import rotating_file

logger = get_logger(sinks=[
    rotating_file("app.log", rotation="daily")  # Same DX as loguru!
])
```

**Additional Examples:**
```python
# Hourly rotation for high-volume services
rotating_file("api.log", rotation="hourly", retention="24h")

# Weekly rotation for low-volume logs
rotating_file("weekly.log", rotation="weekly", retention="4 weeks")

# Monthly rotation for archives
rotating_file("archive.log", rotation="monthly", retention="12 months")

# Midnight rotation (daily at 00:00)
rotating_file("app.log", rotation="midnight", retention="30 days")
```

---

## Scope

### In Scope:
- Time-based rotation keywords: "hourly", "daily", "weekly", "monthly"
- Special keyword: "midnight" (daily at 00:00 system time)
- Extend Story 10.4's `_parse_duration()` to support rotation keywords
- Update `rotating_file()` to accept time keywords in `rotation` parameter
- Update `RotatingFileSettings` to parse time keywords in `interval_seconds`
- Interval-based semantics: "daily" = every 24 hours, not "at midnight" (except "midnight" keyword)
- Backward compatibility: existing `interval_seconds=86400` still works

### Out of Scope (Deferred):
- Cron expressions ("0 0 * * *") - **Future** (too complex)
- Specific time rotation ("at 09:00", "at 14:30") - **Future** (requires scheduler)
- Multiple rotation times per day - **Future**
- Timezone-specific rotation - System timezone only
- Combined rotation (size AND time) - Already supported via existing logic

### Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides `_parse_duration()` parser)
- **Story 10.5**: Simplified File Sink Configuration (provides `rotating_file()` function)
- **Existing**: `RotatingFileSink` with `interval_seconds` field (already works)

---

## API Design Decision

### Decision 1: Rotation Semantics - Interval vs Absolute Time

**Question**: Should "daily" mean "every 24 hours from logger start" or "at midnight every day"?

**Options Considered:**

**Option A: Interval-based (every N hours from start)**
```python
# "daily" = rotate every 24 hours from first log
# Logger starts at 14:30 → rotates at 14:30 next day
rotation="daily"  # → interval_seconds = 86400
```

**Option B: Absolute time (at specific clock time)**
```python
# "daily" = rotate at midnight (00:00) system time
# Logger starts at 14:30 → rotates at 00:00 next day
rotation="daily"  # → calculate_next_midnight()
```

**Option C: Hybrid (keyword determines semantic)**
```python
# "daily" = interval (every 24h)
# "midnight" = absolute (at 00:00)
rotation="daily"     # → interval_seconds = 86400
rotation="midnight"  # → next_rotation = calculate_next_midnight()
```

**Decision**: **Option C** (hybrid approach)

**Rationale**:
1. **Simple default**: "daily"/"hourly" use interval semantics (simpler to implement)
2. **Explicit control**: "midnight" keyword for users who need absolute time
3. **Backward compatible**: Existing `interval_seconds` behavior unchanged
4. **Loguru compatibility**: Loguru's "daily" is interval-based
5. **Implementation simplicity**: Interval-based reuses existing `interval_seconds` logic

**Keyword Semantics**:
- `"hourly"` → Every 1 hour from logger start (interval-based)
- `"daily"` → Every 24 hours from logger start (interval-based)
- `"weekly"` → Every 7 days from logger start (interval-based)
- `"monthly"` → Every 30 days from logger start (interval-based)
- `"midnight"` → At 00:00 system time every day (absolute time)

**Trade-offs**:
- ✅ Simple for most use cases (interval-based)
- ✅ Explicit for absolute time needs ("midnight")
- ✅ Reuses existing implementation
- ⚠️ "daily" might surprise users expecting midnight rotation (docs clarify)

---

### Decision 2: Keyword Mapping - Which Keywords to Support?

**Options Considered:**

**Option A: Minimal set (4 keywords)**
```python
"hourly"  → 3600 seconds
"daily"   → 86400 seconds
"weekly"  → 604800 seconds
"monthly" → 2592000 seconds (30 days)
```

**Option B: Extended set (8+ keywords)**
```python
"minutely" → 60 seconds
"hourly"   → 3600 seconds
"daily"    → 86400 seconds
"weekly"   → 604800 seconds
"monthly"  → 2592000 seconds
"midnight" → absolute time (00:00)
"sunday"   → weekly on Sunday
"1st"      → monthly on 1st
```

**Option C: Loguru-compatible set**
```python
# Match loguru's supported keywords exactly
"daily", "hourly", "weekly", "monthly", "midnight"
```

**Decision**: **Option B (Extended set)** with practical subset

**Supported Keywords** (Story 10.7):
```python
"hourly"   → 3600 seconds        # Every hour
"daily"    → 86400 seconds       # Every 24 hours
"weekly"   → 604800 seconds      # Every 7 days
"monthly"  → 2592000 seconds     # Every 30 days
"midnight" → Absolute (00:00)    # Daily at midnight
```

**Deferred Keywords** (Future):
```python
"minutely" → Defer (rarely needed for log rotation)
"sunday"   → Defer (requires weekday logic)
"1st"      → Defer (requires day-of-month logic)
```

**Rationale**:
1. **Cover 95% of use cases**: Hourly through monthly covers most rotation needs
2. **Include "midnight"**: Common user expectation for daily logs
3. **Simple mapping**: Direct keyword → seconds, except "midnight"
4. **Extend Story 10.4**: Reuse `_parse_duration()` pattern

**Trade-offs**:
- ✅ Practical set for logging use cases
- ✅ Simple to implement and document
- ⚠️ "monthly" = 30 days (not calendar month) - acceptable approximation

---

### Decision 3: Integration with Existing `rotation` Parameter

**Question**: How does time-based rotation integrate with size-based rotation?

**Current State** (Story 10.5):
```python
rotating_file("app.log", rotation="10 MB")  # Size-based only
```

**Options Considered:**

**Option A: Union type (auto-detect size vs time)**
```python
rotating_file("app.log", rotation="10 MB")   # Size-based
rotating_file("app.log", rotation="daily")   # Time-based
rotating_file("app.log", rotation="1h")      # Time-based
```

**Option B: Dict for combined rotation**
```python
rotating_file("app.log", rotation={"size": "10 MB", "time": "daily"})
```

**Option C: Separate parameters**
```python
rotating_file("app.log", rotation_size="10 MB", rotation_time="daily")
```

**Decision**: **Option A** (union type with auto-detection)

**Rationale**:
1. **Simplest API**: Single `rotation` parameter, auto-detect size vs time
2. **Backward compatible**: Existing `rotation="10 MB"` still works
3. **Loguru-compatible**: Matches loguru's single `rotation` parameter
4. **Combined rotation**: Existing logic supports both `max_bytes` AND `interval_seconds`

**Detection Logic**:
```python
def _parse_rotation(rotation: str | int | None):
    if rotation is None:
        return None, None

    if isinstance(rotation, int):
        # Integer = size in bytes
        return rotation, None

    # Try parsing as size first
    try:
        size = _parse_size(rotation)
        return size, None
    except ValueError:
        pass

    # Try parsing as duration/keyword
    try:
        interval = _parse_duration(rotation)
        return None, interval
    except ValueError:
        pass

    # Special keyword: "midnight"
    if rotation.lower() == "midnight":
        return None, "midnight"  # Special marker

    raise ValueError(f"Invalid rotation format: {rotation}")
```

**Example Usage**:
```python
# Size-based rotation (existing)
rotating_file("app.log", rotation="10 MB")

# Time-based rotation (NEW)
rotating_file("app.log", rotation="daily")
rotating_file("app.log", rotation="1h")

# Combined rotation (both size AND time)
# Create two separate config fields
config = RotatingFileSinkConfig(
    max_bytes=10*1024*1024,    # 10 MB
    interval_seconds=86400,     # daily
)
# RotatingFileSink already supports both!
```

**Trade-offs**:
- ✅ Simple API (single parameter)
- ✅ Auto-detection works for 99% of cases
- ⚠️ Ambiguous strings (e.g., "10m" = 10 MB or 10 minutes?) - parser tries size first, then time

---

### Decision 4: "midnight" Implementation - Absolute Time Rotation

**Question**: How do we implement "midnight" (absolute time rotation)?

**Options Considered:**

**Option A: Calculate next midnight deadline**
```python
# In _open_new_file():
if rotation == "midnight":
    now = time.time()
    # Calculate seconds until next midnight
    dt = datetime.now()
    next_midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if dt.hour >= 0:  # Already past midnight today
        next_midnight += timedelta(days=1)
    self._next_rotation_deadline = next_midnight.timestamp()
```

**Option B: Store interval and recalculate on each rotation**
```python
# Store marker that this is absolute time
self._rotation_mode = "midnight"

# On rotation, calculate next midnight
def _calculate_next_deadline(self):
    if self._rotation_mode == "midnight":
        return calculate_next_midnight()
    else:
        return time.time() + self._cfg.interval_seconds
```

**Option C: Defer "midnight" to future story**
```python
# Story 10.7: Only support interval-based ("daily" = every 24h)
# Future story: Add absolute time ("midnight")
```

**Decision**: **Option A** (calculate next midnight deadline)

**Rationale**:
1. **User expectation**: "midnight" clearly means absolute time, not interval
2. **Simple implementation**: Calculate once per rotation (20 lines of code)
3. **Reuses existing logic**: `_next_rotation_deadline` already exists
4. **Common use case**: Daily logs organized by calendar day

**Implementation**:
```python
def _calculate_next_rotation_deadline(self, rotation_keyword: str | None) -> float | None:
    """Calculate next rotation deadline based on keyword or interval."""
    if rotation_keyword == "midnight":
        # Absolute time: next midnight
        from datetime import datetime, timedelta
        now = datetime.now()
        next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour > 0 or now.minute > 0 or now.second > 0:
            next_midnight += timedelta(days=1)
        return next_midnight.timestamp()

    elif self._cfg.interval_seconds:
        # Interval-based: current time + interval
        now = time.time()
        interval = float(self._cfg.interval_seconds)
        next_boundary = now - (now % interval) + interval
        return next_boundary

    return None
```

**Trade-offs**:
- ✅ Meets user expectations for "midnight"
- ✅ Simple implementation (reuses existing deadline logic)
- ⚠️ Adds ~20 lines of code for absolute time calculation
- ⚠️ DST transitions may cause slight drift (acceptable for logging)

---

## Implementation Guide

### Files to Create/Modify

#### 1. `src/fapilog/core/types.py` (MODIFY - extend Story 10.4)

**Extend `_parse_duration()` to support rotation keywords:**

```python
# Existing duration keywords (from Story 10.4)
DURATION_KEYWORDS = {
    "hourly": 3600.0,
    "daily": 86400.0,
    "weekly": 604800.0,
}

# Add rotation-specific keywords
ROTATION_KEYWORDS = {
    "hourly": 3600.0,        # Every hour
    "daily": 86400.0,        # Every 24 hours
    "weekly": 604800.0,      # Every 7 days
    "monthly": 2592000.0,    # Every 30 days
    # "midnight" handled specially (absolute time, not duration)
}


def _parse_duration(value: str | int | float | None) -> float | None:
    """Parse duration string to seconds.

    Args:
        value: Duration as string ("1h", "daily"), number (seconds), or None

    Returns:
        Duration in seconds or None if input is None

    Raises:
        ValueError: If string format is invalid

    Examples:
        >>> _parse_duration("1h")
        3600.0
        >>> _parse_duration("daily")
        86400.0
        >>> _parse_duration("midnight")
        Raises ValueError (not a duration, handled separately)
        >>> _parse_duration(3600)
        3600.0
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("Duration must be non-negative")
        return float(value)

    # Parse string
    value_str = str(value).strip().lower()

    # Check rotation keywords first
    if value_str in ROTATION_KEYWORDS:
        return ROTATION_KEYWORDS[value_str]

    # Special case: "midnight" is not a duration
    if value_str == "midnight":
        raise ValueError(
            "The 'midnight' keyword indicates absolute time rotation "
            "and cannot be used as a duration. Use it directly in the "
            "rotation parameter."
        )

    # Try duration keywords ("hourly", "daily", "weekly")
    if value_str in DURATION_KEYWORDS:
        return DURATION_KEYWORDS[value_str]

    # Try parsing as duration with units (existing logic)
    match = DURATION_PATTERN.match(value_str)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{value_str}'. "
            f"Use format like '1h', '30m', or keywords: "
            f"{', '.join(ROTATION_KEYWORDS.keys())}"
        )

    number_str, unit_str = match.groups()
    number = float(number_str)
    multiplier = DURATION_UNITS[unit_str.lower()]

    result = number * multiplier

    if result < 0:
        raise ValueError("Duration must be non-negative")

    return result
```

#### 2. `src/fapilog/sinks/__init__.py` (MODIFY)

**Update `rotating_file()` to parse rotation keywords:**

```python
def rotating_file(
    path: str,
    *,
    rotation: str | int | None = None,
    retention: int | str | dict | None = None,
    compression: bool = False,
    mode: Literal["json", "text"] = "json",
) -> RotatingFileSink:
    """
    Create a rotating file sink with human-readable configuration.

    Args:
        path: File path (e.g., "logs/app.log"). Parent directory must exist.
        rotation: Size or time-based rotation. Can be:
                 - Size: "10 MB", "50MB", 10485760 (bytes)
                 - Time interval: "hourly", "daily", "weekly", "monthly", "1h", "24h"
                 - Absolute time: "midnight" (rotate at 00:00 daily)
                 None = 10 MB default.
        retention: File retention policy (see Story 10.6)
        compression: If True, compress rotated files with gzip.
        mode: Output format - "json" (default) or "text".

    Returns:
        RotatingFileSink instance ready to pass to get_logger(sinks=[...])

    Example (time-based rotation):
        >>> from fapilog import get_logger
        >>> from fapilog.sinks import rotating_file
        >>>
        >>> # Rotate daily (every 24 hours)
        >>> logger = get_logger(sinks=[
        ...     rotating_file("logs/app.log", rotation="daily", retention="30 days")
        ... ])

        >>> # Rotate at midnight (absolute time)
        >>> logger = get_logger(sinks=[
        ...     rotating_file("logs/app.log", rotation="midnight", retention="7 days")
        ... ])

        >>> # Rotate hourly for high-volume logs
        >>> logger = get_logger(sinks=[
        ...     rotating_file("logs/api.log", rotation="hourly", retention="24h")
        ... ])
    """
    # Parse path to directory + prefix
    path_obj = Path(path)
    directory = path_obj.parent
    filename_prefix = path_obj.stem

    # Parse rotation parameter (size OR time)
    max_bytes = None
    interval_seconds = None
    rotation_keyword = None  # For "midnight"

    if rotation is None:
        # Default: 10 MB size-based rotation
        max_bytes = 10 * 1024 * 1024
    elif isinstance(rotation, int):
        # Integer = size in bytes
        max_bytes = rotation
    elif isinstance(rotation, str):
        rotation_str = rotation.strip().lower()

        # Special case: "midnight" (absolute time)
        if rotation_str == "midnight":
            rotation_keyword = "midnight"
            # interval_seconds will be calculated at sink creation
        else:
            # Try parsing as size first
            try:
                max_bytes = _parse_size(rotation)
            except ValueError:
                # Not a size, try parsing as duration/keyword
                try:
                    interval_seconds = _parse_duration(rotation)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid rotation format: '{rotation}'. "
                        f"Expected size (e.g., '10 MB'), time interval (e.g., 'daily', '1h'), "
                        f"or 'midnight'."
                    ) from e

    # Parse retention parameter (from Story 10.6)
    max_files = None
    max_age_seconds = None
    max_total_bytes = None

    if retention is not None:
        if isinstance(retention, int):
            max_files = retention
        elif isinstance(retention, str):
            max_age_seconds = _parse_duration(retention)
        elif isinstance(retention, dict):
            if "count" in retention:
                max_files = retention["count"]
            if "age" in retention:
                max_age_seconds = _parse_duration(retention["age"])
            if "size" in retention:
                max_total_bytes = _parse_size(retention["size"])
        else:
            raise ValueError(
                f"Invalid retention type: {type(retention).__name__}. "
                f"Expected int, str, or dict."
            )

    # Create config
    config = RotatingFileSinkConfig(
        directory=directory,
        filename_prefix=filename_prefix,
        mode=mode,
        max_bytes=max_bytes,
        interval_seconds=interval_seconds,
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        max_age_seconds=max_age_seconds,
        compress_rotated=compression,
    )

    # Create sink
    sink = RotatingFileSink(config)

    # Special handling for "midnight" rotation
    if rotation_keyword == "midnight":
        sink._rotation_mode = "midnight"  # Mark for absolute time rotation

    return sink
```

#### 3. `src/fapilog/plugins/sinks/rotating_file.py` (MODIFY)

**Add support for "midnight" absolute time rotation:**

```python
class RotatingFileSink:
    """Async rotating file sink with size/time rotation and retention."""

    def __init__(self, config: RotatingFileSinkConfig) -> None:
        self._cfg = config
        self._lock = asyncio.Lock()
        self._active_path: Path | None = None
        self._active_file: BinaryIO | None = None
        self._active_size: int = 0
        self._next_rotation_deadline: float | None = None
        self._rotation_mode: str | None = None  # NEW: "midnight" or None

    async def _open_new_file(self) -> None:
        """Open a new log file and set rotation deadline."""
        # Calculate next rotation deadline
        if hasattr(self, "_rotation_mode") and self._rotation_mode == "midnight":
            # Absolute time: rotate at next midnight
            self._next_rotation_deadline = self._calculate_next_midnight()
        elif self._cfg.interval_seconds and self._cfg.interval_seconds > 0:
            # Interval-based: rotate every N seconds
            now = time.time()
            interval = float(self._cfg.interval_seconds)
            next_boundary = now - (now % interval) + interval
            self._next_rotation_deadline = next_boundary
        else:
            self._next_rotation_deadline = None

        # Build filename (existing logic)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        base_name = f"{self._cfg.filename_prefix}-{ts}"
        ext = ".jsonl" if self._cfg.mode == "json" else ".log"

        # ... rest of existing code ...

    def _calculate_next_midnight(self) -> float:
        """Calculate timestamp of next midnight in system timezone."""
        from datetime import datetime, timedelta

        now = datetime.now()
        next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # If we're already past midnight, get tomorrow's midnight
        if now.hour > 0 or now.minute > 0 or now.second > 0:
            next_midnight += timedelta(days=1)

        return next_midnight.timestamp()

    async def _rotate_active_file(self) -> None:
        """Rotate the active file (existing logic)."""
        # ... existing rotation logic ...

        # After rotation, recalculate next deadline for "midnight" mode
        if hasattr(self, "_rotation_mode") and self._rotation_mode == "midnight":
            self._next_rotation_deadline = self._calculate_next_midnight()

        # ... rest of existing code ...
```

#### 4. `src/fapilog/core/settings.py` (MODIFY)

**Update `RotatingFileSettings` to parse time keywords:**

```python
from .types import OptionalSizeField, OptionalDurationField  # From Story 10.4


class RotatingFileSettings(BaseModel):
    """Per-plugin configuration for RotatingFileSink."""

    directory: str | None = Field(
        default=None, description="Log directory for rotating file sink"
    )
    filename_prefix: str = Field(default="fapilog", description="Filename prefix")
    mode: Literal["json", "text"] = Field(
        default="json", description="Output format: json or text"
    )
    max_bytes: OptionalSizeField = Field(
        default=10 * 1024 * 1024,
        description="Max bytes before rotation. Accepts '10 MB' or 10485760.",
    )
    interval_seconds: OptionalDurationField = Field(  # USES Story 10.4 parser
        default=None,
        description=(
            "Rotation interval in seconds. Accepts duration strings "
            "(e.g., '1h', '24h') or keywords (e.g., 'hourly', 'daily', 'weekly', 'monthly'). "
            "Note: Use 'midnight' in rotating_file() for absolute time rotation."
        )
    )
    max_files: int | None = Field(
        default=None, description="Max number of rotated files to keep"
    )
    max_total_bytes: OptionalSizeField = Field(
        default=None,
        description="Max total bytes across all rotated files. Accepts '100 MB' or 104857600."
    )
    max_age_seconds: OptionalDurationField = Field(  # From Story 10.6
        default=None,
        description="Max age of rotated files in seconds. Accepts '30 days', '1 week', or 2592000."
    )
    compress_rotated: bool = Field(
        default=False, description="Compress rotated log files with gzip"
    )
```

---

## Test Specification

### Unit Tests (`tests/unit/test_time_rotation_keywords.py`)

```python
import pytest
from fapilog.core.types import _parse_duration
from fapilog.sinks import rotating_file


class TestDurationParserKeywords:
    """Test _parse_duration() with rotation keywords."""

    def test_hourly_keyword(self):
        """Test 'hourly' keyword."""
        assert _parse_duration("hourly") == 3600.0

    def test_daily_keyword(self):
        """Test 'daily' keyword."""
        assert _parse_duration("daily") == 86400.0

    def test_weekly_keyword(self):
        """Test 'weekly' keyword."""
        assert _parse_duration("weekly") == 604800.0

    def test_monthly_keyword(self):
        """Test 'monthly' keyword."""
        assert _parse_duration("monthly") == 2592000.0  # 30 days

    def test_case_insensitive(self):
        """Test keywords are case-insensitive."""
        assert _parse_duration("DAILY") == 86400.0
        assert _parse_duration("Daily") == 86400.0
        assert _parse_duration("dAiLy") == 86400.0

    def test_midnight_keyword_raises_error(self):
        """Test 'midnight' raises error in _parse_duration() (not a duration)."""
        with pytest.raises(ValueError, match="midnight.*absolute time"):
            _parse_duration("midnight")


class TestRotatingFileTimeRotation:
    """Test rotating_file() with time-based rotation."""

    def test_rotation_hourly(self):
        """Test rotation='hourly'."""
        sink = rotating_file("logs/app.log", rotation="hourly")
        assert sink._cfg.interval_seconds == 3600.0
        assert sink._cfg.max_bytes is None

    def test_rotation_daily(self):
        """Test rotation='daily'."""
        sink = rotating_file("logs/app.log", rotation="daily")
        assert sink._cfg.interval_seconds == 86400.0
        assert sink._cfg.max_bytes is None

    def test_rotation_weekly(self):
        """Test rotation='weekly'."""
        sink = rotating_file("logs/app.log", rotation="weekly")
        assert sink._cfg.interval_seconds == 604800.0
        assert sink._cfg.max_bytes is None

    def test_rotation_monthly(self):
        """Test rotation='monthly'."""
        sink = rotating_file("logs/app.log", rotation="monthly")
        assert sink._cfg.interval_seconds == 2592000.0  # 30 days
        assert sink._cfg.max_bytes is None

    def test_rotation_midnight(self):
        """Test rotation='midnight' (absolute time)."""
        sink = rotating_file("logs/app.log", rotation="midnight")
        assert hasattr(sink, "_rotation_mode")
        assert sink._rotation_mode == "midnight"

    def test_rotation_duration_string(self):
        """Test rotation='1h' (duration string)."""
        sink = rotating_file("logs/app.log", rotation="1h")
        assert sink._cfg.interval_seconds == 3600.0

    def test_rotation_size_string(self):
        """Test rotation='10 MB' (size string) - existing behavior."""
        sink = rotating_file("logs/app.log", rotation="10 MB")
        assert sink._cfg.max_bytes == 10 * 1024 * 1024
        assert sink._cfg.interval_seconds is None

    def test_rotation_invalid_keyword(self):
        """Test invalid rotation keyword raises error."""
        with pytest.raises(ValueError, match="Invalid rotation format"):
            rotating_file("logs/app.log", rotation="invalidkeyword")


class TestRotatingFileSettingsTimeRotation:
    """Test RotatingFileSettings with time keywords."""

    def test_interval_seconds_hourly(self):
        """Test interval_seconds='hourly'."""
        from fapilog.core.settings import RotatingFileSettings

        settings = RotatingFileSettings(interval_seconds="hourly")
        assert settings.interval_seconds == 3600.0

    def test_interval_seconds_daily(self):
        """Test interval_seconds='daily'."""
        from fapilog.core.settings import RotatingFileSettings

        settings = RotatingFileSettings(interval_seconds="daily")
        assert settings.interval_seconds == 86400.0

    def test_interval_seconds_int(self):
        """Test interval_seconds accepts integer (backward compatible)."""
        from fapilog.core.settings import RotatingFileSettings

        settings = RotatingFileSettings(interval_seconds=7200)
        assert settings.interval_seconds == 7200

    def test_interval_seconds_duration_string(self):
        """Test interval_seconds='2h'."""
        from fapilog.core.settings import RotatingFileSettings

        settings = RotatingFileSettings(interval_seconds="2h")
        assert settings.interval_seconds == 7200.0


class TestMidnightRotationLogic:
    """Test _calculate_next_midnight() logic."""

    @pytest.mark.asyncio
    async def test_calculate_next_midnight(self):
        """Test next midnight calculation."""
        from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig
        from pathlib import Path
        from datetime import datetime, timedelta
        import time

        config = RotatingFileSinkConfig(directory=Path("logs"))
        sink = RotatingFileSink(config)

        next_midnight_ts = sink._calculate_next_midnight()
        next_midnight_dt = datetime.fromtimestamp(next_midnight_ts)

        # Should be midnight (00:00:00)
        assert next_midnight_dt.hour == 0
        assert next_midnight_dt.minute == 0
        assert next_midnight_dt.second == 0

        # Should be in the future
        now = datetime.now()
        assert next_midnight_dt > now

        # Should be within 24 hours
        time_until_midnight = next_midnight_ts - time.time()
        assert 0 < time_until_midnight <= 86400  # Within 24 hours

    @pytest.mark.asyncio
    async def test_midnight_rotation_sets_deadline(self, tmp_path):
        """Test that midnight rotation sets correct deadline."""
        from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig

        config = RotatingFileSinkConfig(directory=tmp_path)
        sink = RotatingFileSink(config)
        sink._rotation_mode = "midnight"

        await sink._open_new_file()

        # Should have deadline set
        assert sink._next_rotation_deadline is not None

        # Deadline should be at midnight
        from datetime import datetime
        deadline_dt = datetime.fromtimestamp(sink._next_rotation_deadline)
        assert deadline_dt.hour == 0
        assert deadline_dt.minute == 0


### Integration Tests (`tests/integration/test_time_rotation_integration.py`)

```python
import pytest
from pathlib import Path
from fapilog import get_logger
from fapilog.sinks import rotating_file


class TestTimeRotationIntegration:
    """Integration tests for time-based rotation."""

    def test_daily_rotation_config(self, tmp_path):
        """Test daily rotation configuration."""
        logger = get_logger(sinks=[
            rotating_file(str(tmp_path / "app.log"), rotation="daily", retention="7 days")
        ])

        logger.info("Test message")

        # Verify log file exists
        log_files = list(tmp_path.glob("app-*.log"))
        assert len(log_files) > 0

    def test_hourly_rotation_config(self, tmp_path):
        """Test hourly rotation configuration."""
        logger = get_logger(sinks=[
            rotating_file(str(tmp_path / "api.log"), rotation="hourly", retention=24)
        ])

        logger.info("Hourly log")

        log_files = list(tmp_path.glob("api-*.log"))
        assert len(log_files) > 0

    def test_midnight_rotation_config(self, tmp_path):
        """Test midnight rotation configuration."""
        logger = get_logger(sinks=[
            rotating_file(str(tmp_path / "midnight.log"), rotation="midnight", retention="30 days")
        ])

        logger.info("Midnight rotation log")

        log_files = list(tmp_path.glob("midnight-*.log"))
        assert len(log_files) > 0

    def test_combined_time_and_retention(self, tmp_path):
        """Test time rotation with age-based retention."""
        logger = get_logger(sinks=[
            rotating_file(
                str(tmp_path / "combined.log"),
                rotation="daily",
                retention={"count": 7, "age": "30 days", "size": "100 MB"}
            )
        ])

        logger.info("Combined retention log")

        log_files = list(tmp_path.glob("combined-*.log"))
        assert len(log_files) > 0
```

---

## Definition of Done

### Code Complete:
- [ ] `_parse_duration()` extended with rotation keywords ("hourly", "daily", "weekly", "monthly")
- [ ] "midnight" keyword handling in `rotating_file()`
- [ ] `_rotation_mode` attribute added to `RotatingFileSink` for "midnight"
- [ ] `_calculate_next_midnight()` method implemented
- [ ] `rotating_file()` auto-detects size vs time rotation
- [ ] `RotatingFileSettings.interval_seconds` uses `OptionalDurationField`

### Tests Complete:
- [ ] Unit tests for rotation keyword parsing
- [ ] Unit tests for `rotating_file()` with time keywords
- [ ] Unit tests for midnight calculation logic
- [ ] Integration tests for daily/hourly/weekly/monthly rotation
- [ ] Integration tests for "midnight" absolute time rotation
- [ ] Backward compatibility tests (existing `interval_seconds=3600` still works)

### Documentation Complete:
- [ ] Update `rotating-file-sink.md` with time rotation examples
- [ ] API reference for rotation keywords
- [ ] Docstring updates for `rotating_file()`
- [ ] Examples for common use cases (hourly, daily, midnight)
- [ ] Clarify interval vs absolute time semantics

### Quality Gates:
- [ ] Type hints pass mypy strict mode
- [ ] Code coverage ≥ 90% for new code
- [ ] No regressions in existing tests
- [ ] Backward compatibility: `interval_seconds=86400` still works

### User Acceptance:
- [ ] Can use time keywords: `rotation="daily"`
- [ ] Can use absolute time: `rotation="midnight"`
- [ ] Can combine time rotation with age retention: `rotation="daily", retention="30 days"`
- [ ] Settings accept time keywords via env vars
- [ ] Matches loguru DX for time-based rotation

---

## Examples

### Example 1: Daily Rotation (Interval-Based)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Rotate every 24 hours (from logger start)
logger = get_logger(sinks=[
    rotating_file("logs/app.log", rotation="daily", retention="30 days")
])

logger.info("Logs rotated daily, kept for 30 days")
```

### Example 2: Midnight Rotation (Absolute Time)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Rotate at midnight (00:00) every day
logger = get_logger(sinks=[
    rotating_file("logs/audit.log", rotation="midnight", retention="90 days")
])

logger.info("Audit logs rotated at midnight, kept for 90 days")
```

### Example 3: Hourly Rotation for High-Volume Service

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Rotate every hour, keep last 24 hours
logger = get_logger(sinks=[
    rotating_file("logs/api.log", rotation="hourly", retention=24)
])

logger.info("High-volume API logs rotated hourly")
```

### Example 4: Weekly Rotation for Low-Volume Logs

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Rotate every week, keep 4 weeks
logger = get_logger(sinks=[
    rotating_file("logs/weekly.log", rotation="weekly", retention="4 weeks")
])

logger.info("Low-volume logs rotated weekly")
```

### Example 5: Settings with Time Keywords

```python
from fapilog import get_logger, Settings

settings = Settings()
settings.file.directory = "logs"
settings.file.filename_prefix = "app"
settings.file.interval_seconds = "daily"  # Human-readable keyword!
settings.file.max_age_seconds = "30 days"
settings.file.compress_rotated = True

logger = get_logger(settings=settings)
logger.info("Configured via Settings with time keywords")
```

### Example 6: Environment Variables

```bash
export FAPILOG_FILE__DIRECTORY=logs
export FAPILOG_FILE__INTERVAL_SECONDS="daily"    # Time keyword!
export FAPILOG_FILE__MAX_AGE_SECONDS="30 days"
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

```python
from fapilog import get_logger

# Automatically picks up env vars with time keywords
logger = get_logger()
logger.info("Daily rotation via environment variables")
```

---

## Non-Goals

1. Cron expressions ("0 0 * * *") - **Future** (too complex)
2. Specific time rotation ("at 09:00", "at 14:30") - **Future** (requires advanced scheduler)
3. Multiple rotation times per day - **Future**
4. Timezone-specific rotation - System timezone only
5. Day-of-week rotation ("every Sunday") - **Future**
6. Day-of-month rotation ("every 1st") - **Future**

---

## Dependencies

### Story Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides `_parse_duration()` parser)
- **Story 10.5**: Simplified File Sink Configuration (provides `rotating_file()` function)

### External Dependencies:
- None (uses Python stdlib `datetime`, `time`)

### Internal Dependencies:
- `RotatingFileSink` implementation (exists)
- `interval_seconds` field (exists)
- `_next_rotation_deadline` logic (exists)

---

## Risks & Mitigations

### Risk 1: "daily" Semantic Confusion
**Risk**: Users expect "daily" to rotate at midnight, not every 24h from start
**Likelihood**: Medium
**Impact**: Low (confusion, not broken functionality)
**Mitigation**: Clear documentation, provide "midnight" keyword for absolute time

### Risk 2: DST Transitions
**Risk**: Daylight saving time transitions may cause midnight rotation to drift
**Likelihood**: Low (twice per year)
**Impact**: Low (logs rotate 1 hour early/late once per year)
**Mitigation**: Document DST behavior, acceptable for logging use case

### Risk 3: "monthly" = 30 Days
**Risk**: "monthly" is fixed at 30 days, not calendar month
**Likelihood**: High (always)
**Impact**: Low (acceptable approximation)
**Mitigation**: Document that "monthly" = 30 days, not calendar month

### Risk 4: Ambiguous Strings
**Risk**: "10m" could mean "10 MB" or "10 minutes"
**Likelihood**: Low (parser tries size first, then duration)
**Impact**: Low (parser will pick one, users can be explicit)
**Mitigation**: Document parsing order (size first, then duration), encourage explicit units

---

## Migration Path

### Fully Backward Compatible (No Migration Needed)

**Existing Code (Continues to Work)**:
```python
from fapilog.sinks import rotating_file

# Integer seconds (existing)
rotating_file("app.log", rotation="10 MB")  # Still works!

# Via Settings
settings = Settings()
settings.file.interval_seconds = 86400  # Still works!
```

**New Capability (Additive)**:
```python
# Time keywords (NEW)
rotating_file("app.log", rotation="daily")  # NEW!
rotating_file("app.log", rotation="hourly")  # NEW!
rotating_file("app.log", rotation="midnight")  # NEW!

# Via Settings
settings.file.interval_seconds = "daily"  # NEW!
```

---

## Future Enhancements (Out of Scope)

1. **Cron expressions**: `rotation="0 0 * * *"` (at midnight via cron syntax)
2. **Specific time**: `rotation="at 09:00"` (rotate at 9 AM)
3. **Day-of-week**: `rotation="every sunday"` (weekly on specific day)
4. **Day-of-month**: `rotation="every 1st"` (monthly on specific day)
5. **Timezone support**: `rotation="midnight UTC"` (timezone-specific)
6. **Multiple rotation times**: `rotation=["08:00", "16:00"]` (twice daily)

---

## Success Metrics

### DX Parity with Loguru:

**Loguru:**
```python
logger.add("file.log", rotation="daily")
logger.add("file.log", rotation="1 hour")
```

**Fapilog (Story 10.7):**
```python
from fapilog.sinks import rotating_file
logger = get_logger(sinks=[
    rotating_file("file.log", rotation="daily")
])
logger = get_logger(sinks=[
    rotating_file("file.log", rotation="1h")
])
```

✅ **Same capability, similar DX**

### Metrics:
- ✅ Time rotation: "daily" instead of calculating 86400 seconds
- ✅ Absolute time: "midnight" for calendar-day-aligned logs
- ✅ Intuitive keywords: hourly, daily, weekly, monthly
- ✅ Backward compatible: Existing `interval_seconds=3600` still works
- ✅ Low complexity: 2-3 day implementation, extends Story 10.4

---

## Conclusion

Story 10.7 completes the file rotation feature set by adding time-based rotation keywords. This closes the final DX gap with loguru for file rotation:

- **Story 10.5**: Size-based rotation + convenience function
- **Story 10.6**: Age-based retention
- **Story 10.7**: Time-based rotation keywords (this story)

Together, these three stories provide a complete, intuitive file rotation API that matches loguru's ease-of-use while maintaining fapilog's production-grade architecture.

**After Story 10.7**, fapilog will have **complete feature parity** with loguru for file rotation, with even more capabilities (combined size+time rotation, size-based retention).
