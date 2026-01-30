# Performance Benchmarks

Indicative benchmark results comparing fapilog to Python stdlib logging. These results help contextualize [performance tuning](performance-tuning.md) recommendations.

## Methodology

| Parameter | Value |
|-----------|-------|
| Baseline | Python stdlib `logging` to file |
| Test | fapilog with rotating file sink |
| Metrics | Throughput (logs/sec), latency (μs), peak memory (bytes) |
| Warmup | 1,000 calls before measurement |
| Iterations | 20,000 (throughput/memory), 5,000 (latency) |
| Payload | ~256 bytes JSON |

Two scenarios are measured:

1. **Standard benchmark** - Raw log call rate with fast file I/O
2. **Slow sink benchmark** - Application-side latency when sink I/O is constrained (2ms simulated delay)

## Environment

| Component | Value |
|-----------|-------|
| Python | 3.13.7 |
| OS | macOS 24.6.0 (Darwin) |
| CPU | Apple M1 Max |
| Memory | 32 GB |
| fapilog | 0.3.6 |

## Results

### Standard Throughput

Raw log call throughput with fast file I/O:

| Logger | Logs/sec | Relative |
|--------|----------|----------|
| stdlib | 90,393 | 1.0x |
| fapilog | 3,295 | 0.04x |

**Interpretation:** For raw throughput to a fast local file, stdlib logging is faster. fapilog's async machinery (queue, batching, background flush) adds overhead that doesn't pay off when the sink is already fast.

### Standard Latency

Per-call latency with fast file I/O:

| Logger | Avg (μs) | Median (μs) | P95 (μs) |
|--------|----------|-------------|----------|
| stdlib | 24 | 12 | 91 |
| fapilog | 279 | 261 | 523 |

**Interpretation:** Similar to throughput, fapilog has higher per-call latency when sinks are fast. The async infrastructure has fixed costs regardless of sink speed.

### Slow Sink Latency (Enterprise Scenario)

Application-side latency when sink I/O is constrained (2ms simulated delay):

| Logger | Avg (μs) | Median (μs) | P95 (μs) |
|--------|----------|-------------|----------|
| stdlib | 2,037 | 2,014 | 2,040 |
| fapilog | 286 | 274 | 483 |

**Latency reduction: 86%**

**Interpretation:** When sink I/O is slow (network sinks, constrained disk, external services), fapilog's non-blocking design prevents the application from stalling. The log call returns immediately while the async backend handles I/O in the background. This is where fapilog's architecture provides value.

### Burst Absorption

Ability to absorb traffic bursts without blocking (20,000 log calls in rapid succession with 2ms sink delay):

| Metric | Value |
|--------|-------|
| Submitted | 22,000 |
| Processed | 12,362 |
| Dropped | 1,712 |
| Queue high-water mark | 10,000 |
| Flush latency | 5.0s |

**Interpretation:** With `drop_on_full=True`, fapilog absorbs bursts up to queue capacity, then gracefully drops overflow rather than blocking the application. Configure queue size based on expected burst patterns.

### Memory

Peak memory during throughput test:

| Logger | Peak (bytes) |
|--------|--------------|
| stdlib | 85,719 |
| fapilog | 10,670,043 |

**Interpretation:** fapilog uses more memory due to its queue, batching buffers, and async infrastructure. This is a deliberate trade-off for non-blocking behavior. Configure `max_queue_size` based on available memory.

### Worker Count Impact

The `worker_count` setting controls parallel flush processing and has the largest impact on fapilog throughput:

| Workers | Throughput | Relative |
|---------|------------|----------|
| 1 (default) | ~3,500/sec | 1.0x |
| 2 | ~105,000/sec | **30x** |
| 2 + redaction | ~89,000/sec | 26x |

**Key findings:**
- Workers are the bottleneck with `worker_count=1` (serializes all processing)
- 2 workers is optimal - more shows diminishing returns due to context switching
- Queue size has minimal impact - larger queues slightly hurt due to memory overhead
- Redaction cost is minimal (~15%) with proper worker count

**Recommendation:** Use 2 workers for production. Production-oriented presets (`production`, `fastapi`, `serverless`, `hardened`) default to 2 workers automatically.

```python
# Option 1: Use a production preset (recommended)
logger = get_logger(preset="production")

# Option 2: Explicitly set worker count
logger = LoggerBuilder().with_workers(2).build()
```

See [Performance Tuning](performance-tuning.md) for detailed configuration guidance.

## When to Use fapilog

Based on these benchmarks:

| Scenario | Recommendation |
|----------|----------------|
| Fast local file, low volume | stdlib may suffice |
| Network sinks (HTTP, cloud services) | fapilog recommended |
| High-volume with slow I/O | fapilog recommended |
| Latency-sensitive applications | fapilog recommended |
| Burst traffic patterns | fapilog with `drop_on_full=True` |

## Limitations

These results are indicative, not definitive:

- **Single machine** - Development laptop, not production hardware
- **Front-end measurement** - Measures log call latency, not end-to-end delivery
- **Environment-dependent** - Results vary with CPU, disk, Python version, workload
- **Not a substitute for load testing** - Test in your actual environment before deployment

## Reproducing These Results

```bash
python scripts/benchmarking.py --iterations 20000 --latency-iterations 5000
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--iterations` | 20000 | Throughput/memory test iterations |
| `--latency-iterations` | 5000 | Latency test iterations |
| `--payload-bytes` | 256 | Approximate payload size |
| `--slow-sink-ms` | 2.0 | Simulated sink delay for enterprise tests |
| `--burst` | 20000 | Burst size for absorption test |

## Related

- [Performance Tuning](performance-tuning.md) - Configuration recommendations
