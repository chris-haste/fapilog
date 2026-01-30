# Performance Tuning

Adjust throughput, latency, and sampling to fit your workload. For indicative performance numbers, see [Benchmarks](benchmarks.md). For protecting latency under slow sinks, see [Non-blocking Async Logging](../cookbook/non-blocking-async-logging.md).

## Worker count (most impactful)

The `worker_count` setting controls parallel flush processing and has the largest impact on throughput:

| Configuration | Throughput | vs Default |
|---------------|------------|------------|
| 1 worker (default) | ~3,500/sec | baseline |
| 2 workers | ~105,000/sec | **+30x faster** |
| 2 workers + redaction | ~89,000/sec | +26x |

**Recommendation:** Use 2 workers for production workloads. Production-oriented presets (`production`, `fastapi`, `serverless`, `hardened`) default to 2 workers automatically.

```python
from fapilog import LoggerBuilder

# Option 1: Use a production preset (recommended)
logger = LoggerBuilder().with_preset("production").build()

# Option 2: Explicitly set worker count
logger = LoggerBuilder().with_workers(2).build()
```

```bash
# Via environment variable
export FAPILOG_CORE__WORKER_COUNT=2
```

**Why 2 workers is optimal:**
- More than 2 workers shows diminishing returns due to context switching
- Queue size barely matters - larger queues actually hurt slightly (memory overhead)
- Workers are the bottleneck with `worker_count=1` (serializes all processing)

**When to use 1 worker:**
- Development/debugging (simpler log ordering)
- Dev preset uses 1 worker by default for this reason

## Queue and batch tuning

```bash
# Throughput-friendly
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.25

# Latency-sensitive
export FAPILOG_CORE__MAX_QUEUE_SIZE=5000
export FAPILOG_CORE__BATCH_MAX_SIZE=64
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.1
export FAPILOG_CORE__DROP_ON_FULL=true
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=10
```

## Sampling low-severity logs

Use `observability.logging.sampling_rate` to drop a fraction of DEBUG/INFO logs:

```bash
export FAPILOG_OBSERVABILITY__LOGGING__SAMPLING_RATE=0.2  # keep 20% of DEBUG/INFO
```

## Serialization fast-path

Enable `core.serialize_in_flush=true` when sinks support `write_serialized` to reduce per-entry serialization overhead in sinks.

## Metrics

Enable internal metrics to monitor queue depth, drops, flush latency:

```bash
export FAPILOG_CORE__ENABLE_METRICS=true
```
