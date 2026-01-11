# Story 10.6: Age-Based File Retention

**Epic**: Epic 10 - Developer Experience & Ergonomics Improvements
**Status**: Implementation-Ready
**Priority**: High (Phase 2: API Improvements)
**Estimated Complexity**: Low (2-3 days)

---

## User Story

**As a** developer,
**I want** to retain log files based on age (e.g., "keep 30 days"),
**So that** I can meet compliance requirements, control storage costs, and match loguru's retention DX.

---

## Business Value

### Current Pain Points:
1. **No age-based retention**: Can only keep N files (`max_files`), not "files from last 30 days"
2. **DX gap vs loguru**: Loguru supports `retention="1 week"`, fapilog doesn't
3. **Compliance issues**: Regulations often require "keep logs for 90 days", not "keep 90 files"
4. **Cost control**: Can't say "delete logs older than 7 days to save disk space"
5. **Missing production pattern**: Time-based retention is standard for logging systems

### Current Capabilities:
```python
# Fapilog HAS (already works):
✅ Count-based: max_files=7 (keep 7 most recent files)
✅ Size-based: max_total_bytes="100 MB" (keep max 100 MB total)

# Fapilog MISSING:
❌ Age-based: "delete files older than 30 days"
```

### After This Story:

**Loguru:**
```python
logger.add("file.log", retention="1 week")  # Delete files > 1 week old
```

**Fapilog (Story 10.6):**
```python
from fapilog.sinks import rotating_file

logger = get_logger(sinks=[
    rotating_file("app.log", retention="30 days")  # Same DX as loguru!
])
```

**Production Use Case:**
```python
# Compliance: Keep 90 days of logs
rotating_file("audit.log", rotation="10 MB", retention="90 days")

# Cost control: Keep last week only
rotating_file("debug.log", rotation="daily", retention="7 days")

# Combined: Keep 30 files OR 30 days OR 1 GB (whichever hits first)
rotating_file("app.log", retention={"count": 30, "age": "30 days", "size": "1 GB"})
```

---

## Scope

### In Scope:
- Add `max_age_seconds` to `RotatingFileSinkConfig`
- Implement age-based cleanup in `_enforce_retention()`
- Human-readable age strings via Story 10.4 parsers ("30 days", "1 week")
- Update `RotatingFileSettings` to use `OptionalDurationField`
- Update `rotating_file()` convenience function to accept age strings
- Combined retention: count + age + size (all can be used together)
- Use file `mtime` (modification time) to determine age

### Out of Scope (Deferred):
- Time-based rotation keywords ("daily", "hourly") - **Story 10.7** (separate concern)
- Absolute time rotation ("at midnight") - **Story 10.7** (complex, maybe not needed)
- Custom retention callables - **Future** (enterprise feature)
- Multi-timezone age calculations - Use system timezone only
- Metadata files for tracking - Keep it simple, use `mtime`

### Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides `_parse_duration()` parser)
- **Story 10.5**: Simplified File Sink Configuration (provides `rotating_file()` function)
- **Existing**: `_enforce_retention()` method in `RotatingFileSink`

---

## API Design Decision

### Decision 1: Age Calculation - mtime vs Filename Parsing vs Metadata

**Options Considered:**

**Option A: File modification time (mtime)**
```python
age_seconds = time.time() - path.stat().st_mtime
if age_seconds > max_age_seconds:
    delete(path)
```
**Pros**: Standard, simple, no parsing needed, works immediately
**Cons**: mtime can be changed by external tools, file moves

**Option B: Parse timestamp from filename**
```python
# Filename: app-20250111-120000.log
timestamp = parse_timestamp_from_filename(path.name)
age_seconds = time.time() - timestamp
```
**Pros**: Immune to mtime changes, accurate rotation time
**Cons**: Requires standardized filename format, parsing complexity

**Option C: Metadata file tracking rotation times**
```python
# Create .fapilog-metadata.json with rotation timestamps
metadata = {"app-20250111.log": 1736596800}
age_seconds = time.time() - metadata[filename]
```
**Pros**: Most accurate, immune to file operations
**Cons**: Adds complexity, extra file management, over-engineered

**Decision**: **Option A** (use `mtime`)

**Rationale**:
1. **Standard practice**: Python's `TimedRotatingFileHandler` uses `mtime`
2. **Simple**: One line of code, no parsing needed
3. **Good enough**: Edge cases (manual file touch) are rare and acceptable
4. **Logging library**: Keep it simple, don't over-engineer
5. **Works with existing files**: No migration needed

**Trade-offs**:
- ✅ Simple, standard, works immediately
- ✅ No parsing or metadata complexity
- ⚠️ User manually touching files can affect age (acceptable edge case)

---

### Decision 2: Retention Parameter Design - Backward Compatibility

**Options Considered:**

**Option A: Union type (int | str | dict)**
```python
def rotating_file(path, retention=None):
    # retention can be:
    # - int: file count
    # - str: age ("30 days")
    # - dict: {"count": 7, "age": "30 days", "size": "100 MB"}
```

**Option B: Separate parameters**
```python
def rotating_file(path, retention_count=None, retention_age=None, retention_size=None):
    ...
```

**Option C: Dict only**
```python
def rotating_file(path, retention={"count": 7, "age": "30 days"}):
    ...
```

**Decision**: **Option A** (Union type with backward compatibility)

**Rationale**:
1. **Backward compatible**: Existing `retention=7` (int) still works
2. **Matches loguru**: Loguru uses single `retention` parameter
3. **Progressive disclosure**: Simple case (int/str) → advanced case (dict)
4. **Type validation**: Pydantic handles union validation
5. **Clean API**: One parameter, not three

**Implementation**:
```python
def rotating_file(path, retention=None):
    if isinstance(retention, int):
        # Count-based (existing behavior)
        max_files = retention
    elif isinstance(retention, str):
        # Age-based (NEW)
        max_age_seconds = _parse_duration(retention)
    elif isinstance(retention, dict):
        # Combined (NEW)
        max_files = retention.get("count")
        max_age_seconds = _parse_duration(retention["age"]) if "age" in retention else None
        max_total_bytes = _parse_size(retention["size"]) if "size" in retention else None
```

**Trade-offs**:
- ✅ Best DX (matches loguru)
- ✅ Fully backward compatible
- ✅ Supports simple and advanced use cases
- ⚠️ Union type slightly complex (but Pydantic handles it)

---

### Decision 3: Retention Order - Which Policy Runs First?

**Question**: If user sets `retention={"count": 7, "age": "30 days", "size": "100 MB"}`, what order do we apply them?

**Options Considered:**

**Option A: Age → Count → Size (delete oldest first, then apply limits)**
```python
# 1. Delete files older than 30 days
for f in files:
    if age(f) > 30 days: delete(f)

# 2. Keep only 7 newest files
if len(files) > 7: delete_oldest_until(count=7)

# 3. Keep total size under 100 MB
if total_size > 100 MB: delete_oldest_until(size=100MB)
```

**Option B: Independent (all policies apply independently)**
```python
# Delete if ANY condition met (OR logic)
for f in files:
    if age(f) > 30 days OR count_exceeded OR size_exceeded:
        delete(f)
```

**Option C: Sequential as configured (count, then age, then size)**
```python
# Apply in order: max_files, max_age_seconds, max_total_bytes
```

**Decision**: **Option A** (Age → Count → Size)

**Rationale**:
1. **Most intuitive**: Delete expired files first, then apply count/size limits
2. **Compliance first**: Age-based retention often regulatory, should run first
3. **Loguru compatibility**: Matches loguru's behavior
4. **Predictable**: Clear execution order, easy to reason about
5. **Already implemented order**: Existing code does max_files then max_total_bytes

**Execution Order** (in `_enforce_retention()`):
```python
async def _enforce_retention(self):
    candidates = self._list_rotated_files()

    # Step 1: Age-based (delete expired files)
    if max_age_seconds is not None:
        candidates = delete_files_older_than(candidates, max_age_seconds)

    # Step 2: Count-based (keep N newest)
    if max_files is not None:
        candidates = keep_newest_n_files(candidates, max_files)

    # Step 3: Size-based (keep max total bytes)
    if max_total_bytes is not None:
        delete_oldest_until_size_under(candidates, max_total_bytes)
```

**Trade-offs**:
- ✅ Intuitive, predictable
- ✅ Compliance-first (age runs first)
- ✅ Matches existing implementation order
- ⚠️ Combined policies can interact (age deletes files, then count deletes more)

---

### Decision 4: Settings Schema - New Field vs Reuse Existing

**Question**: Should we add `max_age_seconds` as a new field, or extend `interval_seconds`?

**Options Considered:**

**Option A: New field `max_age_seconds`**
```python
class RotatingFileSinkConfig:
    max_files: int | None = None
    max_total_bytes: int | None = None
    max_age_seconds: float | None = None  # NEW
```

**Option B: Reuse `interval_seconds` for retention**
```python
# Use interval_seconds for both rotation AND retention?
# (Confusing, don't do this)
```

**Decision**: **Option A** (new field)

**Rationale**:
1. **Clear separation**: Rotation vs retention are different concerns
2. **Explicit > implicit**: Clear field name, no confusion
3. **Matches pattern**: `max_files`, `max_total_bytes`, `max_age_seconds` (parallel structure)
4. **No overlap**: `interval_seconds` is for rotation, `max_age_seconds` for retention

**Trade-offs**:
- ✅ Clear, explicit, no confusion
- ✅ Parallel naming pattern
- ⚠️ Adds one more field (but that's fine)

---

## Implementation Guide

### Files to Create/Modify

#### 1. `src/fapilog/plugins/sinks/rotating_file.py` (MODIFY)

**Add `max_age_seconds` to config:**

```python
@dataclass
class RotatingFileSinkConfig:
    """Configuration for `RotatingFileSink`.

    Attributes:
        directory: Target directory for log files. Created if missing.
        filename_prefix: Prefix for created files.
        mode: 'json' for JSONL output, 'text' for deterministic key=value lines.
        max_bytes: Rotate when current file size plus next record would exceed this.
        interval_seconds: Optional time-based rotation period.
        max_files: Optional retention cap on number of rotated files.
        max_total_bytes: Optional retention cap on cumulative bytes for rotated files.
        max_age_seconds: Optional retention cap on age of rotated files.  # NEW
        compress_rotated: If True, compress closed (rotated) files to .gz.
    """

    directory: Path
    filename_prefix: str = "fapilog"
    mode: str = "json"
    max_bytes: int = 10 * 1024 * 1024
    interval_seconds: int | None = None
    max_files: int | None = None
    max_total_bytes: int | None = None
    max_age_seconds: float | None = None  # NEW: Delete files older than N seconds
    compress_rotated: bool = False
```

**Update `_enforce_retention()` method:**

```python
async def _enforce_retention(self) -> None:
    """Enforce retention policies: age, count, and size.

    Policies are applied in order:
    1. Age-based: Delete files older than max_age_seconds
    2. Count-based: Keep only max_files newest files
    3. Size-based: Keep total size under max_total_bytes
    """
    try:
        # Gather rotated files that match prefix and extension (including .gz)
        candidates: list[Path] = await asyncio.to_thread(self._list_rotated_files)

        if not candidates:
            return

        # Policy 1: Enforce max_age_seconds (delete old files) - NEW
        if self._cfg.max_age_seconds is not None and self._cfg.max_age_seconds >= 0:
            now = time.time()
            age_threshold = self._cfg.max_age_seconds

            survivors: list[Path] = []
            for path in candidates:
                try:
                    mtime = await asyncio.to_thread(lambda: path.stat().st_mtime)
                    age_seconds = now - mtime

                    if age_seconds > age_threshold:
                        # File is too old, delete it
                        try:
                            await asyncio.to_thread(path.unlink)
                        except Exception:
                            # If deletion fails, keep in candidates (don't block other policies)
                            survivors.append(path)
                    else:
                        # File is young enough, keep it
                        survivors.append(path)
                except Exception:
                    # If stat fails, keep the file (safer than deleting)
                    survivors.append(path)

            candidates = survivors

        # Policy 2: Enforce max_files (existing code)
        if self._cfg.max_files is not None and self._cfg.max_files >= 0:
            # Sort by modified time ascending (oldest first)
            candidates.sort(key=lambda p: p.stat().st_mtime)
            while len(candidates) > self._cfg.max_files:
                victim = candidates.pop(0)
                try:
                    await asyncio.to_thread(victim.unlink)
                except Exception:
                    pass

        # Policy 3: Enforce max_total_bytes (existing code)
        if self._cfg.max_total_bytes is not None and self._cfg.max_total_bytes >= 0:
            # Recompute sizes and delete oldest until within budget
            def _sizes(
                paths: Iterable[Path],
            ) -> tuple[list[tuple[Path, int]], int]:
                sized: list[tuple[Path, int]] = []
                total = 0
                for p in paths:
                    try:
                        sz = p.stat().st_size
                    except Exception:
                        sz = 0
                    sized.append((p, sz))
                    total += sz
                sized.sort(key=lambda t: t[0].stat().st_mtime)
                return sized, total

            sized, total = await asyncio.to_thread(_sizes, candidates)
            idx = 0
            while total > self._cfg.max_total_bytes and idx < len(sized):
                victim, vsz = sized[idx]
                try:
                    await asyncio.to_thread(victim.unlink)
                    total -= vsz
                except Exception:
                    pass
                idx += 1
    except Exception:
        # Retention must never break writes
        return None
```

#### 2. `src/fapilog/core/settings.py` (MODIFY)

**Update `RotatingFileSettings` to use Story 10.4 parsers:**

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
    interval_seconds: OptionalDurationField = Field(  # CHANGED: Use parser
        default=None,
        description="Rotation interval in seconds. Accepts '1h', 'daily', or 3600."
    )
    max_files: int | None = Field(
        default=None, description="Max number of rotated files to keep"
    )
    max_total_bytes: OptionalSizeField = Field(
        default=None,
        description="Max total bytes across all rotated files. Accepts '100 MB' or 104857600."
    )
    max_age_seconds: OptionalDurationField = Field(  # NEW: Age-based retention
        default=None,
        description="Max age of rotated files in seconds. Accepts '30 days', '1 week', or 2592000."
    )
    compress_rotated: bool = Field(
        default=False, description="Compress rotated log files with gzip"
    )
```

#### 3. `src/fapilog/sinks/__init__.py` (MODIFY)

**Update `rotating_file()` function to accept age-based retention:**

```python
def rotating_file(
    path: str,
    *,
    rotation: str | int | None = None,
    retention: int | str | dict | None = None,  # CHANGED: Now accepts str and dict
    compression: bool = False,
    mode: Literal["json", "text"] = "json",
) -> RotatingFileSink:
    """
    Create a rotating file sink with human-readable configuration.

    Args:
        path: File path (e.g., "logs/app.log"). Parent directory must exist.
        rotation: Size-based rotation. Examples: "10 MB", "50MB", 10485760 (bytes).
                 None = 10 MB default.
        retention: File retention policy. Can be:
                  - int: Keep N most recent files (e.g., 7)
                  - str: Keep files younger than age (e.g., "30 days", "1 week")
                  - dict: Combined policies (e.g., {"count": 7, "age": "30 days", "size": "100 MB"})
                  None = unlimited retention.
        compression: If True, compress rotated files with gzip.
        mode: Output format - "json" (default) or "text".

    Returns:
        RotatingFileSink instance ready to pass to get_logger(sinks=[...])

    Example (age-based):
        >>> from fapilog import get_logger
        >>> from fapilog.sinks import rotating_file
        >>>
        >>> logger = get_logger(sinks=[
        ...     rotating_file("logs/app.log", retention="30 days")
        ... ])
        >>> logger.info("Logs older than 30 days are automatically deleted")

    Example (combined retention):
        >>> logger = get_logger(sinks=[
        ...     rotating_file(
        ...         "logs/app.log",
        ...         rotation="10 MB",
        ...         retention={"count": 7, "age": "30 days", "size": "1 GB"}
        ...     )
        ... ])
    """
    # Parse path to directory + prefix
    path_obj = Path(path)
    directory = path_obj.parent
    filename_prefix = path_obj.stem

    # Parse rotation size (default to 10 MB if None)
    if rotation is None:
        max_bytes = 10 * 1024 * 1024
    else:
        max_bytes = _parse_size(rotation)

    # Parse retention parameter (NEW: support int, str, dict)
    max_files = None
    max_age_seconds = None
    max_total_bytes = None

    if retention is not None:
        if isinstance(retention, int):
            # Count-based (existing behavior)
            max_files = retention
        elif isinstance(retention, str):
            # Age-based (NEW)
            max_age_seconds = _parse_duration(retention)
        elif isinstance(retention, dict):
            # Combined policies (NEW)
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
        max_files=max_files,
        max_total_bytes=max_total_bytes,
        max_age_seconds=max_age_seconds,  # NEW
        compress_rotated=compression,
    )

    return RotatingFileSink(config)
```

#### 4. `src/fapilog/sinks/__init__.py` (ADD IMPORT)

```python
from ..core.types import _parse_size, _parse_duration  # Add _parse_duration
```

---

## Test Specification

### Unit Tests (`tests/unit/test_age_based_retention.py`)

```python
import pytest
import time
from pathlib import Path
from fapilog.sinks import rotating_file
from fapilog.plugins.sinks.rotating_file import RotatingFileSinkConfig


class TestAgeBas edRetentionConfig:
    """Test max_age_seconds configuration."""

    def test_max_age_seconds_field_exists(self):
        """Test max_age_seconds field is available."""
        config = RotatingFileSinkConfig(
            directory=Path("logs"),
            max_age_seconds=86400.0,  # 1 day
        )
        assert config.max_age_seconds == 86400.0

    def test_max_age_seconds_none_default(self):
        """Test max_age_seconds defaults to None (unlimited)."""
        config = RotatingFileSinkConfig(directory=Path("logs"))
        assert config.max_age_seconds is None


class TestRotatingFileSettings:
    """Test Settings with age-based retention."""

    def test_max_age_seconds_string(self):
        """Test max_age_seconds accepts human-readable string."""
        from fapilog.core.settings import RotatingFileSettings

        settings = RotatingFileSettings(max_age_seconds="30 days")
        assert settings.max_age_seconds == 30 * 24 * 3600  # 2592000 seconds

    def test_max_age_seconds_int(self):
        """Test max_age_seconds accepts integer seconds."""
        from fapilog.core.settings import RotatingFileSettings

        settings = RotatingFileSettings(max_age_seconds=3600)
        assert settings.max_age_seconds == 3600

    def test_max_age_seconds_env_var(self):
        """Test max_age_seconds from environment variable."""
        import os
        from fapilog import Settings

        os.environ["FAPILOG_FILE__MAX_AGE_SECONDS"] = "7 days"
        settings = Settings()
        assert settings.file.max_age_seconds == 7 * 24 * 3600


class TestRotatingFileFactoryAgeRetention:
    """Test rotating_file() with age-based retention."""

    def test_retention_string_age(self):
        """Test retention with age string."""
        sink = rotating_file("logs/app.log", retention="30 days")
        assert sink._cfg.max_age_seconds == 30 * 24 * 3600
        assert sink._cfg.max_files is None  # Not set

    def test_retention_int_count(self):
        """Test retention with int (backward compatible)."""
        sink = rotating_file("logs/app.log", retention=7)
        assert sink._cfg.max_files == 7
        assert sink._cfg.max_age_seconds is None  # Not set

    def test_retention_dict_combined(self):
        """Test retention with combined policies."""
        sink = rotating_file(
            "logs/app.log",
            retention={"count": 7, "age": "30 days", "size": "100 MB"}
        )
        assert sink._cfg.max_files == 7
        assert sink._cfg.max_age_seconds == 30 * 24 * 3600
        assert sink._cfg.max_total_bytes == 100 * 1024 * 1024

    def test_retention_dict_age_only(self):
        """Test retention dict with only age."""
        sink = rotating_file("logs/app.log", retention={"age": "7 days"})
        assert sink._cfg.max_age_seconds == 7 * 24 * 3600
        assert sink._cfg.max_files is None
        assert sink._cfg.max_total_bytes is None

    def test_retention_none(self):
        """Test retention None (unlimited)."""
        sink = rotating_file("logs/app.log")
        assert sink._cfg.max_files is None
        assert sink._cfg.max_age_seconds is None
        assert sink._cfg.max_total_bytes is None

    def test_retention_invalid_type(self):
        """Test retention with invalid type raises error."""
        with pytest.raises(ValueError, match="Invalid retention type"):
            rotating_file("logs/app.log", retention=[1, 2, 3])


class TestEnforceRetentionAgeLogic:
    """Test _enforce_retention() age-based logic."""

    @pytest.mark.asyncio
    async def test_age_retention_deletes_old_files(self, tmp_path):
        """Test that files older than max_age_seconds are deleted."""
        from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig

        # Create sink with 1 second age limit
        config = RotatingFileSinkConfig(
            directory=tmp_path,
            filename_prefix="test",
            max_age_seconds=1.0,  # 1 second
        )
        sink = RotatingFileSink(config)

        # Create old file
        old_file = tmp_path / "test-20250101-000000.log"
        old_file.write_text("old log")

        # Set mtime to 2 seconds ago
        old_mtime = time.time() - 2.0
        import os
        os.utime(old_file, (old_mtime, old_mtime))

        # Create recent file
        recent_file = tmp_path / "test-20250111-120000.log"
        recent_file.write_text("recent log")

        # Run retention
        await sink._enforce_retention()

        # Old file should be deleted, recent file should remain
        assert not old_file.exists()
        assert recent_file.exists()

    @pytest.mark.asyncio
    async def test_age_retention_keeps_young_files(self, tmp_path):
        """Test that files younger than max_age_seconds are kept."""
        from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig

        config = RotatingFileSinkConfig(
            directory=tmp_path,
            filename_prefix="test",
            max_age_seconds=3600.0,  # 1 hour
        )
        sink = RotatingFileSink(config)

        # Create recent file (5 seconds old)
        recent_file = tmp_path / "test-20250111-120000.log"
        recent_file.write_text("recent log")

        recent_mtime = time.time() - 5.0
        import os
        os.utime(recent_file, (recent_mtime, recent_mtime))

        # Run retention
        await sink._enforce_retention()

        # File should still exist
        assert recent_file.exists()

    @pytest.mark.asyncio
    async def test_combined_retention_age_then_count(self, tmp_path):
        """Test combined retention: age deletes expired, then count limits."""
        from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig

        config = RotatingFileSinkConfig(
            directory=tmp_path,
            filename_prefix="test",
            max_age_seconds=2.0,  # 2 seconds
            max_files=2,  # Keep only 2 files
        )
        sink = RotatingFileSink(config)

        # Create 3 old files (> 2 seconds)
        for i in range(3):
            old_file = tmp_path / f"test-old-{i}.log"
            old_file.write_text(f"old {i}")
            old_mtime = time.time() - 3.0
            import os
            os.utime(old_file, (old_mtime, old_mtime))

        # Create 3 recent files
        for i in range(3):
            recent_file = tmp_path / f"test-recent-{i}.log"
            recent_file.write_text(f"recent {i}")

        # Run retention
        await sink._enforce_retention()

        # All old files deleted (age policy)
        assert not (tmp_path / "test-old-0.log").exists()
        assert not (tmp_path / "test-old-1.log").exists()
        assert not (tmp_path / "test-old-2.log").exists()

        # Only 2 recent files kept (count policy)
        recent_files = list(tmp_path.glob("test-recent-*.log"))
        assert len(recent_files) == 2


### Integration Tests (`tests/integration/test_age_retention_integration.py`)

```python
import pytest
import time
import os
from pathlib import Path
from fapilog import get_logger
from fapilog.sinks import rotating_file


class TestAgeRetentionIntegration:
    """Integration tests for age-based retention."""

    @pytest.mark.asyncio
    async def test_age_retention_with_logger(self, tmp_path):
        """Test age-based retention with actual logger."""
        log_path = tmp_path / "app.log"

        # Create logger with 1 second retention
        logger = get_logger(sinks=[
            rotating_file(str(log_path), rotation="100 bytes", retention="1s")
        ])

        # Write logs to trigger rotation
        for i in range(10):
            logger.info(f"Message {i}")

        # Get rotated files
        rotated_files = list(tmp_path.glob("app-*.log"))
        assert len(rotated_files) > 0

        # Age the files
        for f in rotated_files:
            old_mtime = time.time() - 2.0  # 2 seconds ago
            os.utime(f, (old_mtime, old_mtime))

        # Write more logs to trigger rotation (which triggers retention)
        for i in range(10):
            logger.info(f"New message {i}")

        # Old files should be deleted
        # (Note: actual test would need to wait for rotation to trigger retention)

    def test_compliance_use_case_90_days(self, tmp_path):
        """Test compliance use case: keep 90 days of logs."""
        logger = get_logger(sinks=[
            rotating_file(
                str(tmp_path / "audit.log"),
                rotation="10 MB",
                retention="90 days"
            )
        ])

        logger.info("Compliance log entry")

        # Verify config
        # (Actual test would verify files are deleted after 90 days)

    def test_cost_control_use_case_7_days(self, tmp_path):
        """Test cost control: keep only last week."""
        logger = get_logger(sinks=[
            rotating_file(
                str(tmp_path / "debug.log"),
                rotation="daily",
                retention="7 days"
            )
        ])

        logger.debug("Debug info")

    def test_combined_retention_production(self, tmp_path):
        """Test production use case with combined retention."""
        logger = get_logger(sinks=[
            rotating_file(
                str(tmp_path / "app.log"),
                rotation="50 MB",
                retention={"count": 30, "age": "30 days", "size": "1 GB"}
            )
        ])

        logger.info("Production log")
```

---

## Definition of Done

### Code Complete:
- [ ] `max_age_seconds` field added to `RotatingFileSinkConfig`
- [ ] Age-based cleanup logic added to `_enforce_retention()`
- [ ] `RotatingFileSettings.max_age_seconds` uses `OptionalDurationField`
- [ ] `rotating_file()` accepts `retention` as str and dict
- [ ] Import `_parse_duration` in `fapilog.sinks`

### Tests Complete:
- [ ] Unit tests for `max_age_seconds` field
- [ ] Unit tests for `retention` parameter (int, str, dict)
- [ ] Unit tests for `_enforce_retention()` age logic
- [ ] Integration tests for age-based retention with logger
- [ ] Tests for combined retention policies (age + count + size)
- [ ] Edge case tests (mtime edge cases, empty directory, etc.)

### Documentation Complete:
- [ ] Update `rotating-file-sink.md` with age retention examples
- [ ] API reference for `retention` parameter
- [ ] Docstring updates for `rotating_file()`
- [ ] Examples for compliance, cost control use cases

### Quality Gates:
- [ ] Type hints pass mypy strict mode
- [ ] Code coverage ≥ 90% for new code
- [ ] No regressions in existing tests
- [ ] Backward compatibility: `retention=7` (int) still works

### User Acceptance:
- [ ] Can use age-based retention: `retention="30 days"`
- [ ] Can use combined retention: `retention={"count": 7, "age": "30 days", "size": "100 MB"}`
- [ ] Settings accept human-readable age strings
- [ ] Matches loguru DX for retention parameter
- [ ] Files older than threshold are automatically deleted

---

## Examples

### Example 1: Age-Based Retention (Compliance)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Keep 90 days of audit logs for compliance
logger = get_logger(sinks=[
    rotating_file(
        "logs/audit.log",
        rotation="10 MB",
        retention="90 days",  # Delete files older than 90 days
        compression=True,
    )
])

logger.info("Compliance event logged")
```

### Example 2: Cost Control (Keep Last Week)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Keep only last week of debug logs to save disk space
logger = get_logger(sinks=[
    rotating_file(
        "logs/debug.log",
        rotation="daily",
        retention="7 days",  # Delete files older than 7 days
    )
])

logger.debug("Debug info that will be deleted after 7 days")
```

### Example 3: Combined Retention (Production)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Production: Keep max 30 files OR 30 days OR 1 GB (whichever hits first)
logger = get_logger(sinks=[
    rotating_file(
        "logs/app.log",
        rotation="50 MB",
        retention={
            "count": 30,      # Max 30 files
            "age": "30 days", # Max 30 days old
            "size": "1 GB"    # Max 1 GB total
        },
        compression=True,
    )
])

logger.info("Production log with multi-policy retention")
```

### Example 4: Settings with Age-Based Retention

```python
from fapilog import get_logger, Settings

settings = Settings()
settings.file.directory = "logs"
settings.file.filename_prefix = "api"
settings.file.max_bytes = "100 MB"
settings.file.max_age_seconds = "30 days"  # Human-readable!
settings.file.max_files = 10
settings.file.compress_rotated = True

logger = get_logger(settings=settings)
logger.info("Using Settings with age-based retention")
```

### Example 5: Environment Variables

```bash
export FAPILOG_FILE__DIRECTORY=logs
export FAPILOG_FILE__MAX_BYTES="50 MB"
export FAPILOG_FILE__MAX_AGE_SECONDS="30 days"  # Age-based retention
export FAPILOG_FILE__MAX_FILES=7
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

```python
from fapilog import get_logger

# Automatically picks up env vars
logger = get_logger()
logger.info("Configured via environment with age-based retention")
```

---

## Non-Goals

1. Time-based rotation keywords ("daily", "hourly") - **Story 10.7** (separate concern)
2. Absolute time rotation ("at midnight") - **Story 10.7** (complex scheduler)
3. Custom retention callables - **Future** (enterprise feature)
4. Parse timestamp from filename - Use `mtime` (simpler)
5. Metadata files for age tracking - Over-engineered
6. Multi-timezone age calculations - System timezone only

---

## Dependencies

### Story Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides `_parse_duration()` parser)
- **Story 10.5**: Simplified File Sink Configuration (provides `rotating_file()` function)

### External Dependencies:
- None (uses existing Python stdlib)

### Internal Dependencies:
- `RotatingFileSink` implementation (exists)
- `_enforce_retention()` method (exists, extend with age logic)
- `Settings` validation (exists)

---

## Risks & Mitigations

### Risk 1: mtime Unreliable
**Risk**: User manually touches files, changing mtime and affecting age calculation
**Likelihood**: Low
**Impact**: Low (file deleted early or late)
**Mitigation**: Document that age is based on mtime, acceptable edge case for logging library

### Risk 2: Clock Skew / Time Changes
**Risk**: System clock changes (NTP sync, manual adjustment) affect age calculation
**Likelihood**: Low
**Impact**: Low (files deleted early or late)
**Mitigation**: Use monotonic increasing mtime from filesystem, acceptable edge case

### Risk 3: Combined Retention Complexity
**Risk**: Users confused by interaction of count + age + size policies
**Likelihood**: Medium
**Impact**: Low (documentation issue)
**Mitigation**: Clear documentation, examples, predictable execution order (age → count → size)

### Risk 4: Performance (stat syscalls)
**Risk**: Checking mtime for every file adds latency
**Likelihood**: Low
**Impact**: Low
**Mitigation**: Retention only runs at rotation time (not on every write), already doing stats for count/size

---

## Migration Path

### No Migration Needed (Fully Backward Compatible)

**Existing Code (Continues to Work)**:
```python
from fapilog.sinks import rotating_file

# Count-based retention (existing)
logger = get_logger(sinks=[
    rotating_file("app.log", retention=7)  # Still works!
])
```

**New Capability (Additive)**:
```python
# Age-based retention (NEW)
logger = get_logger(sinks=[
    rotating_file("app.log", retention="30 days")  # NEW!
])

# Combined retention (NEW)
logger = get_logger(sinks=[
    rotating_file("app.log", retention={"count": 7, "age": "30 days"})  # NEW!
])
```

---

## Future Enhancements (Out of Scope)

1. **Story 10.7**: Time-based rotation keywords ("daily", "hourly")
2. **Custom retention callables**: `retention=lambda files: ...`
3. **Parse timestamp from filename**: More accurate age tracking
4. **Metadata files**: Most accurate rotation time tracking
5. **Multi-timezone support**: Rotate at midnight in specific timezone

---

## Success Metrics

### DX Parity with Loguru:

**Loguru:**
```python
logger.add("file.log", retention="1 week")
```

**Fapilog (Story 10.6):**
```python
from fapilog.sinks import rotating_file
logger = get_logger(sinks=[rotating_file("file.log", retention="1 week")])
```

✅ **Same capability, similar DX**

### Metrics:
- ✅ Age-based retention: "30 days" instead of calculating 2592000 seconds
- ✅ Compliance use case: "Keep 90 days of logs" (regulatory requirement)
- ✅ Cost control: "Delete logs older than 7 days" (disk space management)
- ✅ Combined policies: count + age + size (production flexibility)
- ✅ Backward compatible: Existing `retention=7` (int) still works
- ✅ Low complexity: 2-3 day implementation, reuses existing patterns

---

## Conclusion

Story 10.6 closes the critical DX gap between fapilog and loguru by adding age-based file retention. This is a high-value, low-complexity feature that:

- **Matches loguru**: Same `retention="1 week"` syntax
- **Enables compliance**: "Keep 90 days of logs" requirement
- **Controls costs**: "Delete old logs" for disk space management
- **Low risk**: Extends existing `_enforce_retention()`, uses `mtime` (standard)
- **Leverages Story 10.4**: Reuses `_parse_duration()` parser
- **Ships fast**: 2-3 days implementation

After Story 10.6, fapilog will have **feature parity** with loguru for file retention, maintaining its position as a best-in-class logging library.
