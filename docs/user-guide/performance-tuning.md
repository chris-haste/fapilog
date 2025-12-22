# Performance Tuning

Adjust throughput, latency, and sampling to fit your workload.

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
