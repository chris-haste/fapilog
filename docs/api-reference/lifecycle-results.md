# Lifecycle & Results

Runtime management helpers and the `DrainResult` structure returned when stopping loggers.

## DrainResult {#drainresult}

```python
@dataclass
class DrainResult:
    submitted: int
    processed: int
    dropped: int
    retried: int
    queue_depth_high_watermark: int
    flush_latency_seconds: float
    adaptive: AdaptiveDrainSummary | None = None
```

Returned by `AsyncLoggerFacade.drain()` / `stop_and_drain()` and the sync logger's `stop_and_drain()` (which you can run via `asyncio.run`).

The `adaptive` field is `None` when the adaptive pipeline is not enabled. When using `preset="adaptive"` or `with_adaptive(enabled=True)`, it contains an `AdaptiveDrainSummary` with metrics about what the adaptive system did during the logger's lifetime.

### Example (async)

```python
from fapilog import get_async_logger

logger = await get_async_logger("worker")
await logger.info("shutting down")
result = await logger.drain()
print(f"processed={result.processed} dropped={result.dropped}")
```

### Example (sync)

```python
import asyncio
from fapilog import get_logger

logger = get_logger("cli")
logger.info("done")
result = asyncio.run(logger.stop_and_drain())
print(result.queue_depth_high_watermark)
```

## AdaptiveDrainSummary {#adaptivedrainsummary}

```python
@dataclass(frozen=True)
class AdaptiveDrainSummary:
    peak_pressure_level: PressureLevel
    escalation_count: int
    deescalation_count: int
    time_at_level: dict[PressureLevel, float]
    filters_swapped: int
    workers_scaled: int
    peak_workers: int
    batch_resize_count: int
    queue_growth_count: int
    peak_queue_capacity: int
```

Available on `DrainResult.adaptive` when the adaptive pipeline is enabled. Provides a post-drain summary of adaptive pipeline activity.

| Field | Description |
|-------|-------------|
| `peak_pressure_level` | Highest pressure level reached during the session |
| `escalation_count` | Number of upward pressure transitions (e.g., NORMAL to ELEVATED) |
| `deescalation_count` | Number of downward pressure transitions |
| `time_at_level` | Wall-clock seconds spent at each `PressureLevel` |
| `filters_swapped` | Number of times filters were tightened or restored |
| `workers_scaled` | Number of worker scaling events |
| `peak_workers` | Maximum concurrent workers reached |
| `batch_resize_count` | Number of adaptive batch size changes |
| `queue_growth_count` | Number of queue capacity expansions |
| `peak_queue_capacity` | Maximum queue capacity reached |

### Example

```python
from fapilog import get_async_logger
from fapilog.core.pressure import PressureLevel

logger = await get_async_logger(preset="adaptive")
# ... application work ...
result = await logger.drain()

if result.adaptive is not None:
    summary = result.adaptive
    print(f"Peak pressure: {summary.peak_pressure_level.value}")
    print(f"Escalations: {summary.escalation_count}")
    print(f"Time at NORMAL: {summary.time_at_level[PressureLevel.NORMAL]:.1f}s")
    print(f"Peak workers: {summary.peak_workers}")
```

## Context managers

Prefer `runtime()` / `runtime_async()` to manage startup and shutdown automatically:

```python
from fapilog import runtime, runtime_async

with runtime() as logger:
    logger.info("sync work")

async def main():
    async with runtime_async() as logger:
        await logger.info("async work")
```

## Shutdown timeout

`Settings.core.shutdown_timeout_seconds` controls how long the shutdown path will wait for the background worker thread to complete. Configure via env var `FAPILOG_CORE__SHUTDOWN_TIMEOUT_SECONDS`.

---

_Use the lifecycle helpers to ensure buffered logs are flushed before your app exits._
