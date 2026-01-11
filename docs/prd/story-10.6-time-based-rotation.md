# Story 10.6: Time-Based Rotation & Advanced Retention (Placeholder)

**Epic**: Epic 10 - Developer Experience & Ergonomics Improvements
**Status**: Placeholder (NOT Implementation-Ready)
**Priority**: Medium (Phase 2: API Improvements)
**Estimated Complexity**: High (5-7 days)

---

## User Story

**As a** developer,
**I want** to rotate log files based on time intervals (daily, hourly, at specific times),
**So that** I can organize logs by time periods and implement time-based retention policies.

---

## Business Value

Extends Story 10.5's size-based rotation with time-based rotation strategies commonly needed in production:
- Daily rotation at midnight for compliance/audit logs
- Hourly rotation for high-volume services
- Rotation at specific times (e.g., "at 00:00", "at 09:00")
- Age-based retention ("keep 30 days")
- Size-based retention ("keep 100 MB total")
- Combined retention policies

---

## Scope

### In Scope:
- Time-based rotation keywords: "daily", "hourly", "weekly", "monthly"
- Specific time rotation: "at 00:00", "at 09:00", etc.
- Age-based retention: "keep 30 days", "keep 7 days"
- Size-based retention: "keep 100 MB", "keep 1 GB"
- Combined retention: `{"count": 7, "age": "30 days", "size": "100 MB"}`
- Extend `rotation` parameter to accept time strings
- Extend `retention` parameter to accept duration/size strings

### Out of Scope:
- Cron expression support (e.g., "0 0 * * *") - too complex for v1
- Custom rotation predicates/callbacks
- Rotation based on log content/conditions
- Multi-timezone support (uses system timezone)

### Dependencies:
- **Story 10.4**: Human-Readable Config Strings (provides duration parsers)
- **Story 10.5**: Simplified File Rotation API (provides add_file() foundation)

---

## Critical Open Questions

Before this story becomes implementation-ready, the following questions MUST be answered:

### Question 1: Time-Based Rotation Semantics - Interval vs Absolute Time

**Question**: Should "daily" mean "every 24 hours from logger start" or "at midnight every day"?

**Options**:
- **Option A**: Interval-based ("daily" = every 24 hours from first log)
  - Simpler to implement
  - Predictable for testing
  - May not align with human time boundaries

- **Option B**: Absolute time ("daily" = at midnight system time)
  - Aligns with human expectations
  - Requires timezone handling
  - More complex scheduler implementation

**Implications**:
- Affects rotation trigger implementation
- Affects how "hourly", "weekly", "monthly" work
- Affects user expectations and documentation

**Recommendation Needed**: Which semantic should we use? Or support both?

---

### Question 2: Rotation Scheduler Architecture

**Question**: How should we implement time-based rotation triggers?

**Options**:
- **Option A**: Background thread with sleep loop
  ```python
  while True:
      time.sleep(check_interval)
      if should_rotate():
          rotate()
  ```

- **Option B**: Schedule at next rotation time
  ```python
  next_rotation = calculate_next_midnight()
  schedule_task(next_rotation, rotate)
  ```

- **Option C**: Check on each log write
  ```python
  def write_log(event):
      if time.time() > next_rotation_time:
          rotate()
      write(event)
  ```

**Implications**:
- Option A: Simple, but wastes CPU
- Option B: Efficient, but complex scheduler needed
- Option C: Zero overhead until rotation needed, but adds latency to writes

**Recommendation Needed**: Which approach balances simplicity and performance?

---

### Question 3: Age-Based Retention - Age Definition

**Question**: What does "keep 30 days" mean exactly?

**Options**:
- **Option A**: File modification time (mtime)
  - Standard approach
  - Works if files aren't touched externally

- **Option B**: Parse timestamp from filename
  - More reliable
  - Requires standardized filename format

- **Option C**: Metadata file tracking rotation times
  - Most accurate
  - Adds complexity

**Edge Cases**:
- User manually touches log file (updates mtime)
- Log file moved/copied (mtime changes)
- Clock skew / timezone changes

**Recommendation Needed**: Which approach is most robust?

---

### Question 4: Size-Based Retention - Calculation Strategy

**Question**: How should "keep 100 MB total" be calculated and enforced?

**Options**:
- **Option A**: Delete oldest until total < threshold
  ```python
  while total_size() > max_size:
      delete_oldest_file()
  ```

- **Option B**: Pre-calculate how many files fit in threshold
  ```python
  max_files = max_size / avg_file_size
  keep_n_newest(max_files)
  ```

- **Option C**: Reserve threshold for current file
  ```python
  rotated_files_limit = max_size * 0.9  # 90% for old files, 10% for current
  ```

**Implications**:
- Option A: Most accurate, but expensive (many file stats)
- Option B: Fast, but fails if file sizes vary
- Option C: Conservative, may delete files early

**Recommendation Needed**: Which strategy is best for production use?

---

### Question 5: Combined Retention - Policy Composition

**Question**: How should combined retention policies be applied?

**Scenario**:
```python
logger.add_file(
    "app.log",
    rotation="daily",
    retention={"count": 7, "age": "30 days", "size": "100 MB"}
)
```

**Options**:
- **Option A**: AND logic (keep if ALL conditions met)
  - Keep files that are: <= 7 files AND <= 30 days AND <= 100 MB total
  - Most restrictive

- **Option B**: OR logic (delete if ANY condition exceeded)
  - Delete files if: > 7 files OR > 30 days OR > 100 MB total
  - Most aggressive

- **Option C**: Priority order (count, then age, then size)
  - Apply count limit first, then age, then size
  - Predictable but complex

**Edge Cases**:
- What if count=7 keeps 30 days of logs, but age="7 days"?
- What if size="100 MB" requires deleting files < 30 days old?

**Recommendation Needed**: Which logic makes most sense to users?

---

### Question 6: Rotation Filename Format

**Question**: What filename format should time-based rotated files use?

**Current (from RotatingFileSink)**:
- app.log → app.log.1, app.log.2, app.log.3 (numbered)

**Options for Time-Based**:
- **Option A**: Keep numbered format (app.log.1, app.log.2)
  - Consistent with size-based rotation
  - Doesn't show rotation time

- **Option B**: Timestamp suffix (app.log.2025-01-11, app.log.2025-01-10)
  - Shows when log was rotated
  - Easier to find specific day's logs

- **Option C**: ISO timestamp (app.log.2025-01-11T00:00:00)
  - Most precise
  - Longer filenames

- **Option D**: User-configurable format string
  - Flexible
  - Adds complexity

**Implications**:
- Affects age-based retention implementation (Question 3)
- Affects user's ability to find logs by date
- Affects sorting and cleanup logic

**Recommendation Needed**: Which format should be default? Should it be configurable?

---

## Placeholder API Design

**Note**: This API is TENTATIVE and subject to change based on answers to open questions above.

### Extended `add_file()` Signature:

```python
def add_file(
    self,
    path: str,
    *,
    rotation: str | int | None = None,  # NEW: Accepts time keywords
    retention: int | str | dict | None = None,  # NEW: Accepts age/size strings or dict
    compression: bool = False,
    level: str | None = None,
    format: Literal["json", "text"] = "json",
) -> str:
    """
    Add a file sink with optional rotation and retention.

    Args:
        rotation: Size or time-based rotation:
            - Size: "10 MB", "50MB", 10485760 (bytes) [Story 10.5]
            - Time: "daily", "hourly", "weekly", "monthly" [Story 10.6]
            - Specific: "at 00:00", "at 09:00" [Story 10.6]

        retention: File count, age, size, or combined:
            - Count: 7 keeps 7 most recent files [Story 10.5]
            - Age: "30 days", "7d", "1 week" [Story 10.6]
            - Size: "100 MB", "1 GB" [Story 10.6]
            - Combined: {"count": 7, "age": "30d", "size": "100MB"} [Story 10.6]

    Returns:
        Sink ID for later removal.

    Examples:
        # Time-based rotation
        logger.add_file("app.log", rotation="daily", retention="30 days")

        # Hourly with size limit
        logger.add_file("app.log", rotation="hourly", retention="1 GB")

        # Combined retention
        logger.add_file(
            "app.log",
            rotation="daily",
            retention={"count": 7, "age": "30 days", "size": "100 MB"}
        )
    """
```

---

## Example Use Cases (Tentative)

### Example 1: Daily Rotation with Age-Based Retention

```python
from fapilog import get_logger

logger = get_logger("api")

# Rotate daily at midnight, keep 30 days
logger.add_file(
    "app.log",
    rotation="daily",
    retention="30 days",
    compression=True,
)
```

### Example 2: Hourly Rotation for High-Volume Service

```python
from fapilog import get_logger

logger = get_logger("api")

# Rotate every hour, keep 24 files (1 day)
logger.add_file(
    "api.log",
    rotation="hourly",
    retention=24,
)
```

### Example 3: Combined Retention Policy

```python
from fapilog import get_logger

logger = get_logger("api")

# Rotate daily, keep max 7 files OR 30 days OR 100 MB (whichever hits first)
logger.add_file(
    "app.log",
    rotation="daily",
    retention={"count": 7, "age": "30 days", "size": "100 MB"},
    compression=True,
)
```

### Example 4: Rotation at Specific Time

```python
from fapilog import get_logger

logger = get_logger("api")

# Rotate at 9 AM every day (business hours start)
logger.add_file(
    "business.log",
    rotation="at 09:00",
    retention="90 days",
)
```

---

## Technical Challenges

### Challenge 1: Scheduler Implementation
- Need efficient time-based trigger mechanism
- Must work with both sync and async loggers
- Must handle clock changes (DST, manual clock adjustment)

### Challenge 2: Timezone Handling
- Should rotation use UTC or local time?
- How to handle DST transitions?
- Should timezone be configurable?

### Challenge 3: Retention Policy Enforcement
- When to check retention (after every rotation? background thread?)
- How to handle slow file I/O (stat, delete) without blocking logs
- What if file deletion fails (permissions, locks)?

### Challenge 4: Backward Compatibility
- Must not break Story 10.5's size-based rotation
- Union types (`int | str | dict`) must validate correctly
- Clear error messages when mixing incompatible options

---

## Success Criteria (Tentative)

- [ ] Daily/hourly/weekly/monthly rotation works as expected
- [ ] Age-based retention deletes files older than threshold
- [ ] Size-based retention keeps total size under limit
- [ ] Combined retention policies apply correctly
- [ ] Rotation happens at correct times (midnight for "daily", etc.)
- [ ] No breaking changes to Story 10.5 API
- [ ] Performance overhead < 5% vs size-based rotation
- [ ] Clear error messages for invalid time/retention formats

---

## Next Steps to Make Implementation-Ready

1. **Answer Critical Questions**: Team/stakeholder decision on 6 open questions above
2. **Prototype Scheduler**: Spike on rotation scheduler architecture (Options A/B/C in Question 2)
3. **Define Filename Format**: Decide on rotated file naming convention
4. **Update Story 10.4**: Add time-of-day parsing if needed ("at 09:00")
5. **Write Detailed Implementation Guide**: Once questions answered, flesh out like Story 10.5
6. **Define Test Spec**: Edge cases for time-based rotation (DST, clock skew, etc.)

---

## Related Stories

- **Story 10.4**: Human-Readable Config Strings (provides duration parsers)
- **Story 10.5**: Simplified File Rotation API (provides add_file() foundation)
- **Story 10.7**: Enhanced Default Behaviors (may auto-detect rotation strategy)

---

## Non-Goals

- Cron expression support (e.g., "0 0 * * *")
- Multi-timezone rotation (e.g., rotate at midnight in all timezones)
- Custom rotation predicates/callbacks
- Rotation based on log content (e.g., rotate when ERROR threshold hit)
- Per-sink rotation schedulers (all sinks share scheduler)

---

## References

- loguru rotation: https://loguru.readthedocs.io/en/stable/api/logger.html#loguru._logger.Logger.add
- Python logging.handlers.TimedRotatingFileHandler: https://docs.python.org/3/library/logging.handlers.html#timedrotatingfilehandler
- Story 10.5: Size-based rotation implementation
