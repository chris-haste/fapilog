# Story 10.5: Simplified File Rotation API

**Epic**: Epic 10 - Developer Experience & Ergonomics Improvements
**Status**: Implementation-Ready
**Priority**: High (Phase 2: API Improvements)
**Estimated Complexity**: Medium (3-5 days)

---

## User Story

**As a** developer,
**I want** a simple method to add file rotation to my logger,
**So that** I don't need to create Settings objects or understand the full configuration model for basic file logging.

---

## Business Value

### Current Pain Points:
1. Adding file rotation requires understanding Settings, RotatingFileSinkConfig, sink registration
2. Minimum 15-20 lines of configuration for basic file logging
3. No dynamic sink addition after logger creation
4. File rotation is hidden behind complex configuration objects

### After This Story:
```python
# Before (20+ lines with Settings objects)
settings = Settings(
    sink_config=SinkConfig(
        rotating_file=RotatingFileSettings(
            enabled=True,
            path="app.log",
            max_bytes=10485760,  # Need to calculate bytes
            max_files=7,
        )
    )
)
logger = get_logger("api", settings=settings)

# After (1 line with human-readable config)
logger = get_logger("api")
logger.add_file("app.log", rotation="10 MB", retention=7)
```

**Lines Reduced**: 20+ → 2 (90% reduction)
**Cognitive Load**: High → Low (no Settings objects needed)
**Discovery**: Hidden in Settings → Discoverable via IDE autocomplete

---

## Scope

### In Scope:
- `add_file()` method on logger facades (Logger, AsyncLogger)
- Size-based rotation using human-readable strings from Story 10.4
- File count-based retention (keep N most recent files)
- Compression option for rotated files
- Per-file log level filtering
- Return sink ID for removal
- `remove_sink(id)` method for dynamic sink management

### Out of Scope (Deferred to Story 10.6):
- Time-based rotation ("daily", "hourly", "at 00:00")
- Cron-like rotation scheduling
- Age-based retention ("keep 30 days")
- Size-based retention ("keep 100 MB total")
- Combined retention policies

### Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides SizeField parser)
- **Existing**: RotatingFileSink implementation
- **Existing**: Sink registration and removal infrastructure

---

## API Design Decision

### Decision 1: Method Location - Instance Method vs Module Function

**Options Considered:**

**Option A: Instance method on logger**
```python
logger = get_logger("api")
sink_id = logger.add_file("app.log", rotation="10 MB")
```

**Option B: Module-level function**
```python
from fapilog import get_logger, add_file_sink
logger = get_logger("api")
sink_id = add_file_sink(logger, "app.log", rotation="10 MB")
```

**Option C: Sink manager object**
```python
logger = get_logger("api")
sink_id = logger.sinks.add_file("app.log", rotation="10 MB")
```

**Decision**: **Option A** (instance method)

**Rationale**:
1. **Fluent API**: Matches fluent builder pattern, feels natural
2. **Discovery**: IDE autocomplete shows `logger.add_file()` immediately
3. **Simplicity**: No additional imports or manager objects needed
4. **Precedent**: Loguru uses `logger.add()` instance method successfully
5. **Type Safety**: Method signature enforces correct logger type

**Trade-offs**:
- ✅ Best developer experience (most intuitive)
- ✅ Most discoverable via autocomplete
- ⚠️ Adds surface area to logger facade classes
- ⚠️ May complicate type hints (but manageable)

---

### Decision 2: Rotation Parameter Design - String vs Dedicated Parameter

**Options Considered:**

**Option A: Single rotation parameter (string or int)**
```python
logger.add_file("app.log", rotation="10 MB")  # Size-based
logger.add_file("app.log", rotation=10485760) # Size-based (bytes)
# Time-based deferred to Story 10.6
```

**Option B: Separate parameters for each rotation type**
```python
logger.add_file("app.log", rotation_size="10 MB")
logger.add_file("app.log", rotation_time="daily")  # Story 10.6
logger.add_file("app.log", rotation_size="10 MB", rotation_time="daily")  # Both
```

**Option C: Rotation object**
```python
from fapilog import SizeRotation, TimeRotation
logger.add_file("app.log", rotation=SizeRotation("10 MB"))
logger.add_file("app.log", rotation=TimeRotation("daily"))  # Story 10.6
```

**Decision**: **Option A** (single `rotation` parameter)

**Rationale**:
1. **Simplicity**: Single parameter is more intuitive for Story 10.5
2. **Forward Compatibility**: Can extend in Story 10.6 to accept "daily", "hourly"
3. **Type Safety**: Union type `str | int` is simple and Pydantic-friendly
4. **Matches Story 10.4**: Uses same human-readable string pattern
5. **Less Verbose**: No need to import rotation classes

**Implementation**:
```python
# Story 10.5 - accepts size strings only
rotation: str | int | None = None  # e.g., "10 MB" or 10485760

# Story 10.6 - extends to accept time keywords
rotation: str | int | None = None  # e.g., "10 MB", "daily", "00:00"
```

**Trade-offs**:
- ✅ Simplest API for size-based rotation
- ✅ Easy to extend in Story 10.6
- ⚠️ Slightly ambiguous ("10 MB" vs "daily" - but parser will validate)

---

### Decision 3: Retention Parameter Design - Int vs String vs Dict

**Options Considered:**

**Option A: Simple integer (file count only for Story 10.5)**
```python
logger.add_file("app.log", retention=7)  # Keep 7 files
```

**Option B: Union type (int or string)**
```python
logger.add_file("app.log", retention=7)           # File count
logger.add_file("app.log", retention="7 days")    # Story 10.6
logger.add_file("app.log", retention="100 MB")    # Story 10.6
```

**Option C: Dict for combined policies**
```python
logger.add_file("app.log", retention={"count": 7, "age": "30d", "size": "100MB"})
```

**Decision**: **Option A for Story 10.5** (int only), **Option B for Story 10.6** (extend to str)

**Rationale**:
1. **Progressive Disclosure**: Start simple (count only), extend later
2. **Type Safety**: `retention: int | None` is clear for Story 10.5
3. **Story 10.6 Extension**: Can change to `int | str | None` when adding time/size retention
4. **Backward Compatibility**: Adding `str` support doesn't break existing `int` usage
5. **Validation**: Simple integer validation for Story 10.5

**Story 10.5 Signature**:
```python
def add_file(
    self,
    path: str,
    *,
    rotation: str | int | None = None,  # Size-based only
    retention: int | None = None,       # File count only
    compression: bool = False,
    level: str | None = None,
    format: Literal["json", "text"] = "json",
) -> str:  # Returns sink ID
    ...
```

**Story 10.6 Extension**:
```python
def add_file(
    self,
    path: str,
    *,
    rotation: str | int | None = None,  # Size OR time-based
    retention: int | str | None = None, # Count OR age OR size
    compression: bool = False,
    level: str | None = None,
    format: Literal["json", "text"] = "json",
) -> str:
    ...
```

**Trade-offs**:
- ✅ Clear and simple for Story 10.5
- ✅ Easy to extend in Story 10.6
- ✅ Type signatures evolve naturally
- ⚠️ May need better docs to explain which strings are valid

---

### Decision 4: Return Value - Sink ID vs Sink Object vs None

**Options Considered:**

**Option A: Return sink ID (string UUID)**
```python
sink_id = logger.add_file("app.log", rotation="10 MB")
logger.remove_sink(sink_id)  # Later removal
```

**Option B: Return sink object**
```python
sink = logger.add_file("app.log", rotation="10 MB")
sink.remove()
sink.pause()
sink.resume()
```

**Option C: Return None (fire-and-forget)**
```python
logger.add_file("app.log", rotation="10 MB")
# No removal mechanism
```

**Decision**: **Option A** (return sink ID)

**Rationale**:
1. **Removal Support**: Enables `logger.remove_sink(id)` for dynamic management
2. **Simplicity**: String ID is simple to store and pass around
3. **No State Leaks**: ID doesn't hold references to internal sink state
4. **Testability**: Easy to verify sink was added and removed
5. **Forward Compatible**: Can add sink introspection later if needed

**API**:
```python
sink_id = logger.add_file("app.log", rotation="10 MB")
# Returns: "550e8400-e29b-41d4-a716-446655440000" (UUID)

logger.remove_sink(sink_id)
# Gracefully stops and removes the sink
```

**Trade-offs**:
- ✅ Enables dynamic sink management
- ✅ Simple string ID is easy to work with
- ⚠️ User must store ID if they want to remove later (but optional)
- ⚠️ No built-in sink introspection (list sinks, get status) - can add later

---

### Decision 5: Format Parameter - String Literal vs Enum

**Options Considered:**

**Option A: String literal type**
```python
format: Literal["json", "text"] = "json"
```

**Option B: Enum**
```python
from fapilog import OutputFormat
format: OutputFormat = OutputFormat.JSON
```

**Option C: String without type hint**
```python
format: str = "json"
```

**Decision**: **Option A** (Literal type)

**Rationale**:
1. **Type Safety**: Literal catches typos at type-check time
2. **IDE Autocomplete**: IDEs suggest "json" | "text" options
3. **No Imports**: Users don't need to import OutputFormat enum
4. **Simplicity**: Strings are more intuitive than enum values
5. **Pydantic Friendly**: Literal works seamlessly with Pydantic validation

**Trade-offs**:
- ✅ Best type safety with minimal imports
- ✅ Clear autocomplete suggestions
- ⚠️ Limited to two formats (but sufficient for Story 10.5)

---

### Decision 6: Internal Implementation - Direct vs Settings Adapter

**Options Considered:**

**Option A: Create Settings objects internally**
```python
def add_file(self, path, rotation=None, ...):
    settings = RotatingFileSettings(
        path=path,
        max_bytes=_parse_size(rotation) if rotation else None,
        max_files=retention,
        ...
    )
    sink_id = self._add_sink(settings)
    return sink_id
```

**Option B: Direct sink creation (bypass Settings)**
```python
def add_file(self, path, rotation=None, ...):
    sink = RotatingFileSink(
        path=path,
        max_bytes=_parse_size(rotation) if rotation else None,
        ...
    )
    sink_id = self._register_sink(sink)
    return sink_id
```

**Decision**: **Option A** (create Settings objects)

**Rationale**:
1. **Reuse Validation**: Settings objects already have validation logic
2. **Consistency**: Settings is the single source of truth for configuration
3. **Less Duplication**: Don't duplicate validation in add_file()
4. **Maintainability**: Changes to Settings automatically flow to add_file()
5. **Type Safety**: Settings enforce correct types via Pydantic

**Trade-offs**:
- ✅ Reuses existing validation infrastructure
- ✅ Consistent with rest of codebase
- ⚠️ Slight overhead creating Settings objects (negligible)

---

## Implementation Guide

### Files to Create/Modify

#### 1. `src/fapilog/core/logger_base.py` (MODIFY)
Add shared implementation for add_file() and remove_sink():

```python
from __future__ import annotations

import uuid
from typing import Literal
from pathlib import Path

from .types import SizeField, _parse_size
from .settings import RotatingFileSettings, SinkConfig


class LoggerBase:
    """Shared functionality for Logger and AsyncLogger facades."""

    def __init__(self, name: str, worker: LogWorker):
        self._name = name
        self._worker = worker
        self._dynamic_sinks: dict[str, str] = {}  # sink_id -> internal_id

    def add_file(
        self,
        path: str,
        *,
        rotation: str | int | None = None,
        retention: int | None = None,
        compression: bool = False,
        level: str | None = None,
        format: Literal["json", "text"] = "json",
    ) -> str:
        """
        Add a file sink with optional rotation and retention.

        Args:
            path: File path (relative or absolute). Parent directory must exist.
            rotation: Size-based rotation. Examples: "10 MB", "50MB", 10485760 (bytes).
                     None = no rotation (single file grows unbounded).
            retention: Number of rotated files to keep (default: unlimited).
                      Examples: 7 keeps 7 most recent files.
            compression: If True, compress rotated files with gzip.
            level: Minimum log level for this sink (None = inherit logger level).
            format: Output format - "json" (default) or "text".

        Returns:
            Sink ID (UUID string) for later removal via remove_sink().

        Raises:
            ValueError: If rotation/retention format is invalid.
            FileNotFoundError: If parent directory doesn't exist.

        Example:
            >>> logger = get_logger("api")
            >>> sink_id = logger.add_file("app.log", rotation="10 MB", retention=7)
            >>> # Later: logger.remove_sink(sink_id)
        """
        # Validate path exists
        path_obj = Path(path)
        if not path_obj.parent.exists():
            raise FileNotFoundError(
                f"Parent directory does not exist: {path_obj.parent}. "
                f"Create it first: mkdir -p {path_obj.parent}"
            )

        # Parse rotation parameter
        max_bytes: int | None = None
        if rotation is not None:
            max_bytes = _parse_size(rotation)
            if max_bytes <= 0:
                raise ValueError(f"Rotation size must be positive, got: {rotation}")

        # Validate retention
        if retention is not None and retention < 1:
            raise ValueError(f"Retention must be >= 1, got: {retention}")

        # Create Settings object
        settings = RotatingFileSettings(
            enabled=True,
            path=str(path),
            max_bytes=max_bytes,
            max_files=retention,
            compression=compression if max_bytes else False,  # Only compress if rotating
            level=level,
            format=format,
        )

        # Register sink with worker
        sink_id = str(uuid.uuid4())
        internal_id = self._worker.register_sink("rotating_file", settings)
        self._dynamic_sinks[sink_id] = internal_id

        return sink_id

    def remove_sink(self, sink_id: str, timeout: float = 5.0) -> None:
        """
        Remove a dynamically added sink.

        Args:
            sink_id: Sink ID returned from add_file() or other add_* methods.
            timeout: Max seconds to wait for graceful drain (default: 5.0).

        Raises:
            KeyError: If sink_id not found (already removed or invalid).

        Example:
            >>> sink_id = logger.add_file("app.log")
            >>> logger.remove_sink(sink_id)
        """
        if sink_id not in self._dynamic_sinks:
            raise KeyError(
                f"Sink ID not found: {sink_id}. "
                f"Either already removed or invalid ID."
            )

        internal_id = self._dynamic_sinks.pop(sink_id)
        self._worker.unregister_sink(internal_id, timeout=timeout)
```

#### 2. `src/fapilog/core/logger.py` (MODIFY)
Inherit from LoggerBase:

```python
from .logger_base import LoggerBase


class Logger(LoggerBase):
    """Synchronous logger facade."""

    def __init__(self, name: str, worker: LogWorker):
        super().__init__(name, worker)

    # Existing methods (info, error, etc.) unchanged
    # add_file() and remove_sink() inherited from LoggerBase
```

#### 3. `src/fapilog/core/async_logger.py` (MODIFY)
Inherit from LoggerBase:

```python
from .logger_base import LoggerBase


class AsyncLogger(LoggerBase):
    """Async logger facade."""

    def __init__(self, name: str, worker: AsyncLogWorker):
        super().__init__(name, worker)

    # Existing methods (ainfo, aerror, etc.) unchanged
    # add_file() and remove_sink() inherited from LoggerBase
```

#### 4. `src/fapilog/core/worker.py` (MODIFY)
Add sink registration/unregistration:

```python
class LogWorker:
    """Existing worker with new sink management methods."""

    def register_sink(self, sink_type: str, settings: BaseModel) -> str:
        """
        Register a new sink dynamically.

        Args:
            sink_type: Sink type (e.g., "rotating_file", "cloudwatch").
            settings: Sink-specific settings (e.g., RotatingFileSettings).

        Returns:
            Internal sink ID for unregistration.
        """
        # Create sink instance
        sink = self._create_sink(sink_type, settings)

        # Start sink
        sink.start()

        # Add to active sinks
        internal_id = str(uuid.uuid4())
        self._sinks[internal_id] = sink

        return internal_id

    def unregister_sink(self, internal_id: str, timeout: float = 5.0) -> None:
        """
        Unregister and gracefully stop a sink.

        Args:
            internal_id: Internal sink ID from register_sink().
            timeout: Max seconds to wait for drain.
        """
        if internal_id not in self._sinks:
            return  # Already removed

        sink = self._sinks.pop(internal_id)

        # Graceful shutdown
        try:
            sink.drain(timeout=timeout)
            sink.stop()
        except Exception as e:
            # Log error but don't raise (best effort removal)
            logger.warning(f"Error draining sink {internal_id}: {e}")

    def _create_sink(self, sink_type: str, settings: BaseModel):
        """Create sink instance from type and settings."""
        if sink_type == "rotating_file":
            from ..sinks.rotating_file import RotatingFileSink
            return RotatingFileSink(settings)
        # ... other sink types
        raise ValueError(f"Unknown sink type: {sink_type}")
```

#### 5. `src/fapilog/core/settings.py` (MODIFY - if needed)
Ensure RotatingFileSettings supports all parameters:

```python
from .types import OptionalSizeField


class RotatingFileSettings(BaseModel):
    """Settings for rotating file sink."""

    enabled: bool = True
    path: str = Field(description="File path")
    max_bytes: OptionalSizeField = Field(
        default=None,
        description="Max bytes before rotation (None = no rotation). Accepts '10 MB' or 10485760."
    )
    max_files: int | None = Field(
        default=None,
        description="Number of rotated files to keep (None = unlimited)."
    )
    compression: bool = Field(
        default=False,
        description="Compress rotated files with gzip."
    )
    level: str | None = Field(
        default=None,
        description="Minimum log level for this sink (None = inherit)."
    )
    format: Literal["json", "text"] = Field(
        default="json",
        description="Output format."
    )
```

---

## Test Specification

### Unit Tests (`tests/unit/test_add_file.py`)

```python
import pytest
from pathlib import Path
from fapilog import get_logger, get_async_logger


class TestAddFileBasics:
    """Basic add_file() functionality."""

    def test_add_file_minimal(self, tmp_path):
        """Test add_file with just path."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        sink_id = logger.add_file(str(log_path))

        assert isinstance(sink_id, str)
        assert len(sink_id) == 36  # UUID length
        logger.info("Test message")

        assert log_path.exists()
        content = log_path.read_text()
        assert "Test message" in content

    def test_add_file_with_rotation(self, tmp_path):
        """Test add_file with size-based rotation."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        sink_id = logger.add_file(
            str(log_path),
            rotation="10 KB",
            retention=3,
        )

        # Write enough to trigger rotation
        for i in range(100):
            logger.info("x" * 200)  # 200 byte messages

        # Check rotated files exist
        assert log_path.exists()
        rotated = list(tmp_path.glob("app.log.*"))
        assert len(rotated) <= 3  # Retention limit

    def test_add_file_with_compression(self, tmp_path):
        """Test compression of rotated files."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(
            str(log_path),
            rotation="1 KB",
            retention=2,
            compression=True,
        )

        # Trigger rotation
        for i in range(50):
            logger.info("x" * 100)

        # Check .gz files exist
        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) > 0

    def test_add_file_with_level_filter(self, tmp_path):
        """Test per-sink level filtering."""
        log_path = tmp_path / "errors.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), level="ERROR")

        logger.info("Info message")
        logger.error("Error message")

        content = log_path.read_text()
        assert "Info message" not in content
        assert "Error message" in content

    def test_add_file_format_json(self, tmp_path):
        """Test JSON format output."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), format="json")
        logger.info("Test", key="value")

        content = log_path.read_text()
        assert "{" in content  # JSON object
        assert '"key": "value"' in content or '"key":"value"' in content

    def test_add_file_format_text(self, tmp_path):
        """Test text format output."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), format="text")
        logger.info("Test message")

        content = log_path.read_text()
        assert "Test message" in content
        assert "{" not in content  # Not JSON


class TestAddFileValidation:
    """Validation and error handling."""

    def test_add_file_invalid_rotation_format(self, tmp_path):
        """Test invalid rotation format raises clear error."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        with pytest.raises(ValueError, match="Invalid size format"):
            logger.add_file(str(log_path), rotation="10 XB")

    def test_add_file_negative_rotation(self, tmp_path):
        """Test negative rotation raises error."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        with pytest.raises(ValueError, match="must be positive"):
            logger.add_file(str(log_path), rotation=-1)

    def test_add_file_zero_retention(self, tmp_path):
        """Test zero retention raises error."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        with pytest.raises(ValueError, match="must be >= 1"):
            logger.add_file(str(log_path), retention=0)

    def test_add_file_parent_not_exists(self, tmp_path):
        """Test missing parent directory raises helpful error."""
        log_path = tmp_path / "nonexistent" / "app.log"
        logger = get_logger("test")

        with pytest.raises(FileNotFoundError, match="Parent directory does not exist"):
            logger.add_file(str(log_path))


class TestRemoveSink:
    """Sink removal functionality."""

    def test_remove_sink_stops_logging(self, tmp_path):
        """Test remove_sink stops further logging."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        sink_id = logger.add_file(str(log_path))
        logger.info("Before removal")

        logger.remove_sink(sink_id)
        initial_size = log_path.stat().st_size

        logger.info("After removal")
        final_size = log_path.stat().st_size

        assert final_size == initial_size  # No new logs

    def test_remove_sink_invalid_id(self, tmp_path):
        """Test removing invalid sink ID raises error."""
        logger = get_logger("test")

        with pytest.raises(KeyError, match="Sink ID not found"):
            logger.remove_sink("invalid-uuid")

    def test_remove_sink_already_removed(self, tmp_path):
        """Test removing same sink twice raises error."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        sink_id = logger.add_file(str(log_path))
        logger.remove_sink(sink_id)

        with pytest.raises(KeyError, match="Sink ID not found"):
            logger.remove_sink(sink_id)

    def test_remove_sink_graceful_drain(self, tmp_path):
        """Test remove_sink waits for pending logs to flush."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        sink_id = logger.add_file(str(log_path))

        # Queue many logs
        for i in range(1000):
            logger.info(f"Message {i}")

        # Remove should wait for drain
        logger.remove_sink(sink_id, timeout=5.0)

        # All logs should be written
        content = log_path.read_text()
        assert "Message 999" in content


class TestMultipleSinks:
    """Multiple file sinks."""

    def test_add_multiple_files(self, tmp_path):
        """Test adding multiple file sinks."""
        logger = get_logger("test")

        info_path = tmp_path / "info.log"
        error_path = tmp_path / "errors.log"

        info_id = logger.add_file(str(info_path), level="INFO")
        error_id = logger.add_file(str(error_path), level="ERROR")

        logger.info("Info message")
        logger.error("Error message")

        # Info file has both
        info_content = info_path.read_text()
        assert "Info message" in info_content
        assert "Error message" in info_content

        # Error file has only errors
        error_content = error_path.read_text()
        assert "Info message" not in error_content
        assert "Error message" in error_content

    def test_remove_one_of_multiple_sinks(self, tmp_path):
        """Test removing one sink doesn't affect others."""
        logger = get_logger("test")

        file1 = tmp_path / "file1.log"
        file2 = tmp_path / "file2.log"

        id1 = logger.add_file(str(file1))
        id2 = logger.add_file(str(file2))

        logger.info("Before removal")
        logger.remove_sink(id1)
        logger.info("After removal")

        # file1 should not have "After removal"
        content1 = file1.read_text()
        assert "Before removal" in content1
        assert "After removal" not in content1

        # file2 should have both
        content2 = file2.read_text()
        assert "Before removal" in content2
        assert "After removal" in content2


class TestAsyncAddFile:
    """Async logger add_file() tests."""

    @pytest.mark.asyncio
    async def test_async_add_file(self, tmp_path):
        """Test add_file on AsyncLogger."""
        log_path = tmp_path / "async.log"
        logger = await get_async_logger("test")

        sink_id = logger.add_file(str(log_path))
        await logger.ainfo("Async message")

        content = log_path.read_text()
        assert "Async message" in content

    @pytest.mark.asyncio
    async def test_async_remove_sink(self, tmp_path):
        """Test remove_sink on AsyncLogger."""
        log_path = tmp_path / "async.log"
        logger = await get_async_logger("test")

        sink_id = logger.add_file(str(log_path))
        await logger.ainfo("Message")

        logger.remove_sink(sink_id)

        # Should still have the message
        content = log_path.read_text()
        assert "Message" in content
```

### Integration Tests (`tests/integration/test_add_file_integration.py`)

```python
import pytest
import time
from pathlib import Path
from fapilog import get_logger


class TestRotationIntegration:
    """Integration tests for rotation behavior."""

    def test_rotation_creates_numbered_files(self, tmp_path):
        """Test rotation creates .1, .2, .3 files."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), rotation="1 KB", retention=5)

        # Write 5KB of logs
        for i in range(100):
            logger.info("x" * 100)

        # Check numbered files exist
        assert log_path.exists()
        assert (tmp_path / "app.log.1").exists()
        assert (tmp_path / "app.log.2").exists()

    def test_retention_deletes_old_files(self, tmp_path):
        """Test retention policy deletes oldest files."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), rotation="500 bytes", retention=3)

        # Write enough to create 5+ rotations
        for i in range(100):
            logger.info("x" * 50)

        # Should have at most 3 rotated files + current
        all_files = list(tmp_path.glob("app.log*"))
        assert len(all_files) <= 4  # app.log + 3 rotated

    def test_compression_reduces_file_size(self, tmp_path):
        """Test compression actually compresses files."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), rotation="1 KB", compression=True)

        # Write compressible data
        for i in range(100):
            logger.info("a" * 100)  # Highly compressible

        # Find .gz file
        gz_files = list(tmp_path.glob("*.gz"))
        assert len(gz_files) > 0

        gz_size = gz_files[0].stat().st_size
        assert gz_size < 1024  # Should be much smaller than 1KB


class TestConcurrency:
    """Concurrent logging tests."""

    def test_concurrent_writes_no_corruption(self, tmp_path):
        """Test multiple threads writing doesn't corrupt file."""
        import threading

        log_path = tmp_path / "concurrent.log"
        logger = get_logger("test")
        logger.add_file(str(log_path))

        def write_logs(thread_id):
            for i in range(100):
                logger.info(f"Thread {thread_id} message {i}")

        threads = [threading.Thread(target=write_logs, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 1000 messages should be in file
        content = log_path.read_text()
        lines = [l for l in content.split("\n") if l.strip()]
        assert len(lines) == 1000


class TestEdgeCases:
    """Edge case tests."""

    def test_add_file_exact_rotation_boundary(self, tmp_path):
        """Test rotation triggers exactly at boundary."""
        log_path = tmp_path / "app.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), rotation=100)  # 100 bytes

        # Write exactly 100 bytes
        logger.info("x" * 80)  # With JSON overhead = ~100 bytes

        # Next log should trigger rotation
        logger.info("Next")

        rotated = list(tmp_path.glob("app.log.*"))
        assert len(rotated) >= 1

    def test_add_file_unicode_content(self, tmp_path):
        """Test Unicode characters logged correctly."""
        log_path = tmp_path / "unicode.log"
        logger = get_logger("test")

        logger.add_file(str(log_path))
        logger.info("Hello 世界 🌍")

        content = log_path.read_text(encoding="utf-8")
        assert "世界" in content
        assert "🌍" in content

    def test_add_file_very_long_message(self, tmp_path):
        """Test very long messages don't break rotation."""
        log_path = tmp_path / "long.log"
        logger = get_logger("test")

        logger.add_file(str(log_path), rotation="10 KB")

        # Write message larger than rotation size
        logger.info("x" * 20000)  # 20KB message

        # Should still work
        assert log_path.exists()
        content = log_path.read_text()
        assert "x" * 20000 in content
```

### Performance Tests (`tests/performance/test_add_file_perf.py`)

```python
import pytest
from fapilog import get_logger


class TestAddFilePerformance:
    """Performance benchmarks."""

    def test_add_file_overhead(self, tmp_path, benchmark):
        """Benchmark add_file() call overhead."""
        logger = get_logger("test")

        def add_file():
            sink_id = logger.add_file(str(tmp_path / "bench.log"))
            logger.remove_sink(sink_id)

        result = benchmark(add_file)
        assert result < 0.01  # Should take < 10ms

    def test_logging_with_rotation_overhead(self, tmp_path, benchmark):
        """Benchmark logging with rotation enabled."""
        log_path = tmp_path / "bench.log"
        logger = get_logger("test")
        logger.add_file(str(log_path), rotation="10 MB")

        def log_message():
            logger.info("Benchmark message", key="value")

        result = benchmark(log_message)
        assert result < 0.001  # Should take < 1ms
```

---

## Definition of Done

### Code Complete:
- [ ] `LoggerBase` class created with `add_file()` and `remove_sink()` methods
- [ ] `Logger` and `AsyncLogger` inherit from `LoggerBase`
- [ ] `LogWorker.register_sink()` and `unregister_sink()` implemented
- [ ] `RotatingFileSettings` updated with all necessary fields
- [ ] Human-readable rotation strings use `_parse_size()` from Story 10.4

### Tests Complete:
- [ ] All unit tests pass (30+ test cases)
- [ ] All integration tests pass (rotation, retention, compression)
- [ ] Performance benchmarks meet targets (< 1ms per log)
- [ ] Async tests pass for AsyncLogger
- [ ] Edge cases covered (unicode, long messages, exact boundaries)

### Documentation Complete:
- [ ] API reference for `add_file()` and `remove_sink()`
- [ ] Docstrings with examples for both methods
- [ ] README updated with add_file() examples
- [ ] Migration guide from Settings-based file configuration

### Quality Gates:
- [ ] Type hints pass mypy strict mode
- [ ] Code coverage ≥ 90% for new code
- [ ] No regressions in existing tests
- [ ] Performance benchmarks show < 5% overhead vs direct Settings usage

### User Acceptance:
- [ ] Can add file sink in 1 line: `logger.add_file("app.log", rotation="10 MB")`
- [ ] Can remove sink dynamically: `logger.remove_sink(sink_id)`
- [ ] Multiple file sinks work independently
- [ ] Rotation and retention work as documented
- [ ] Clear error messages for invalid inputs

---

## Examples

### Example 1: Basic File Logging

```python
from fapilog import get_logger

logger = get_logger("api")
logger.add_file("app.log")

logger.info("Application started")
logger.error("An error occurred", exc_info=True)
```

### Example 2: Size-Based Rotation with Retention

```python
from fapilog import get_logger

logger = get_logger("api")

# Keep last 7 files, rotate every 10 MB
logger.add_file(
    "app.log",
    rotation="10 MB",
    retention=7,
    compression=True,
)

# Heavy logging - rotation happens automatically
for i in range(10000):
    logger.info(f"Processing item {i}", item_id=i)
```

### Example 3: Multiple Sinks with Different Levels

```python
from fapilog import get_logger

logger = get_logger("api")

# All logs to app.log
logger.add_file("app.log", level="DEBUG", rotation="50 MB")

# Only errors to errors.log
logger.add_file("errors.log", level="ERROR", rotation="10 MB", retention=30)

# Only critical to critical.log (no rotation)
logger.add_file("critical.log", level="CRITICAL")

logger.debug("Debug info")      # → app.log only
logger.info("Info message")     # → app.log only
logger.error("Error occurred")  # → app.log, errors.log
logger.critical("Critical!")    # → all three files
```

### Example 4: Dynamic Sink Management

```python
from fapilog import get_logger
import time

logger = get_logger("api")

# Add temporary debug sink
debug_sink = logger.add_file("debug.log", level="DEBUG")

# Debug for 60 seconds
time.sleep(60)

# Remove debug sink
logger.remove_sink(debug_sink)
```

### Example 5: FastAPI Integration with add_file()

```python
from fastapi import FastAPI
from fapilog import get_async_logger

app = FastAPI()

@app.on_event("startup")
async def startup():
    logger = await get_async_logger("api")

    # Add rotating file logs
    logger.add_file(
        "api.log",
        rotation="10 MB",
        retention=7,
        format="json",
    )

    await logger.ainfo("API started")

@app.get("/")
async def root():
    logger = await get_async_logger("api")
    await logger.ainfo("Request received")
    return {"status": "ok"}
```

### Example 6: Using with Presets (Story 10.1)

```python
from fapilog import get_logger

# Development preset + custom file sink
logger = get_logger("api", preset="dev")
logger.add_file("debug.log", level="DEBUG", retention=1)  # Keep today's debug log

# Production preset + custom error file
logger = get_logger("api", preset="production")
logger.add_file("critical.log", level="CRITICAL")  # Never rotate critical logs
```

---

## Open Questions

1. **Sink ID Format**: Should we use UUID strings or shorter IDs (e.g., "file-1", "file-2")?
   - **Recommendation**: UUID for uniqueness and safety (no collisions)

2. **Remove Timeout Default**: Is 5.0 seconds a good default timeout for remove_sink()?
   - **Recommendation**: Yes, matches typical logger drain timeouts

3. **Compression Format**: Should we support formats other than gzip (e.g., bz2, xz)?
   - **Recommendation**: Defer to future story; gzip is sufficient for Story 10.5

4. **Format Parameter**: Should "text" format be human-readable (like StdoutPrettySink) or simple text?
   - **Recommendation**: Simple text for Story 10.5 (timestamp + message), defer pretty to Story 10.7

---

## Non-Goals

1. Time-based rotation ("daily", "hourly") - **Story 10.6**
2. Age-based retention ("keep 30 days") - **Story 10.6**
3. Size-based retention ("keep 100 MB total") - **Story 10.6**
4. Cron-like rotation ("at 00:00") - **Story 10.6**
5. Combined retention policies - **Story 10.6**
6. Custom rotation predicates - **Future**
7. Sink introspection (list_sinks(), get_sink_status()) - **Future**
8. Sink pause/resume - **Future**
9. Dynamic reconfiguration of existing sinks - **Future**

---

## Dependencies

### Story Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides `_parse_size()` parser)

### External Dependencies:
- None (uses existing fapilog infrastructure)

### Internal Dependencies:
- `RotatingFileSink` implementation (exists)
- `LogWorker` sink management (needs register/unregister methods)
- `Settings` validation (exists)

---

## Risks & Mitigations

### Risk 1: Sink ID Collisions
**Risk**: UUID collisions could cause sink removal bugs
**Likelihood**: Very Low
**Impact**: Medium
**Mitigation**: Use uuid4() (collision probability ~1 in 10^36)

### Risk 2: File Handle Leaks
**Risk**: remove_sink() doesn't properly close file handles
**Likelihood**: Medium
**Impact**: High (production issue)
**Mitigation**: Comprehensive integration tests, timeout enforcement, graceful drain

### Risk 3: Performance Overhead
**Risk**: Dynamic sink registration adds latency
**Likelihood**: Low
**Impact**: Medium
**Mitigation**: Performance benchmarks, reuse existing Settings validation

### Risk 4: Thread Safety
**Risk**: Concurrent add_file/remove_sink calls cause race conditions
**Likelihood**: Medium
**Impact**: High
**Mitigation**: Worker lock on sink registration/unregistration, concurrency tests

---

## Migration Path

### From Settings-Based File Configuration:

**Before (Settings object)**:
```python
from fapilog import get_logger, Settings, SinkConfig, RotatingFileSettings

settings = Settings(
    sink_config=SinkConfig(
        rotating_file=RotatingFileSettings(
            enabled=True,
            path="app.log",
            max_bytes=10485760,
            max_files=7,
            compression=True,
        )
    )
)
logger = get_logger("api", settings=settings)
```

**After (add_file() method)**:
```python
from fapilog import get_logger

logger = get_logger("api")
logger.add_file("app.log", rotation="10 MB", retention=7, compression=True)
```

**Migration Strategy**:
1. Both approaches work (no breaking changes)
2. Settings-based configuration still recommended for complex setups
3. add_file() recommended for simple file logging
4. Can mix both: Settings for base config + add_file() for dynamic sinks

---

## Future Enhancements (Out of Scope)

1. **Story 10.6**: Time-based rotation and advanced retention
2. **add_cloudwatch()**: CloudWatch sink with one-liner API
3. **add_postgres()**: PostgreSQL sink with one-liner API
4. **add_webhook()**: Webhook sink with one-liner API
5. **list_sinks()**: Introspection API to list active sinks
6. **pause_sink(id)** / **resume_sink(id)**: Dynamic sink control
7. **reconfigure_sink(id, **kwargs)**: Update sink settings without removal

---

## Success Metrics

### Before Story 10.5:
```python
# 20+ lines with Settings objects
settings = Settings(
    sink_config=SinkConfig(
        rotating_file=RotatingFileSettings(
            enabled=True,
            path="app.log",
            max_bytes=10485760,
            max_files=7,
            compression=True,
        )
    )
)
logger = get_logger("api", settings=settings)
```

### After Story 10.5:
```python
# 2 lines
logger = get_logger("api")
logger.add_file("app.log", rotation="10 MB", retention=7, compression=True)
```

**Metrics**:
- ✅ Lines of code: 20+ → 2 (90% reduction)
- ✅ Cognitive load: High (Settings objects) → Low (single method)
- ✅ IDE discovery: Hidden in Settings → Autocomplete shows add_file()
- ✅ Human-readable config: "10 MB" instead of 10485760
- ✅ Dynamic sink management: Enabled (add/remove at runtime)

---

## Conclusion

Story 10.5 delivers a significant DX improvement by providing a simple, discoverable API for file rotation. By focusing on size-based rotation and file count retention (deferring time-based features to Story 10.6), we can ship a valuable feature quickly while maintaining high quality and type safety.

The `add_file()` method integrates seamlessly with Story 10.4's human-readable strings and provides a foundation for future `add_*()` methods (CloudWatch, PostgreSQL, webhooks).
