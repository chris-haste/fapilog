# Logs Dropped Under Load



## Symptoms
- Missing log lines during traffic spikes
- Backpressure/drop warnings in diagnostics
- High queue utilization

## Causes
- Queue too small for burst load
- Sinks slower than producers
- Backpressure policy set to drop quickly
- Too few workers for sink latency

## Fixes

### Increase queue and batch sizes
```bash
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.25
```

### Add workers for slow sinks
If your sink has I/O latency (network, database, cloud APIs), adding workers parallelizes flush operations:
```bash
export FAPILOG_CORE__WORKER_COUNT=4  # Default is 1
```

Worker scaling guidance:
- **1 worker** (default): Sufficient for fast sinks (stdout, local file)
- **2-4 workers**: Good for sinks with 1-5ms latency (HTTP, cloud APIs)
- **4-8 workers**: For high-latency sinks (>5ms) or high throughput requirements
- **>8 workers**: Rarely needed; diminishing returns and increased memory usage

### Adjust backpressure policy
```bash
export FAPILOG_CORE__DROP_ON_FULL=false        # wait instead of drop
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=25
```

### Enable metrics to monitor drops
```bash
export FAPILOG_CORE__ENABLE_METRICS=true
```

If latency is critical, keep `DROP_ON_FULL=true` but monitor drops via metrics/diagnostics and raise batch size or worker count cautiously.
