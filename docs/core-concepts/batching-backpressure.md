# Batching & Backpressure

Control throughput and behavior under load with queue, batch, and backpressure settings.

## Queue and batching

- `core.max_queue_size` (env: `FAPILOG_CORE__MAX_QUEUE_SIZE`): ring buffer capacity.
- `core.batch_max_size` (env: `FAPILOG_CORE__BATCH_MAX_SIZE`): max entries per flush.
- `core.batch_timeout_seconds` (env: `FAPILOG_CORE__BATCH_TIMEOUT_SECONDS`): time trigger for partial batches.

## Backpressure policy

- `core.backpressure_wait_ms` (env: `FAPILOG_CORE__BACKPRESSURE_WAIT_MS`): wait for space before dropping.
- `core.drop_on_full` (env: `FAPILOG_CORE__DROP_ON_FULL`): when True, drop after wait timeout; when False, keep waiting.

## Tuning examples

```bash
# Favor throughput, tolerate a bit more latency
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.25
export FAPILOG_CORE__DROP_ON_FULL=false

# Favor low latency, bounded memory
export FAPILOG_CORE__MAX_QUEUE_SIZE=5000
export FAPILOG_CORE__BATCH_MAX_SIZE=64
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.1
export FAPILOG_CORE__DROP_ON_FULL=true
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=10
```

## Metrics and diagnostics

When `core.enable_metrics=True`, fapilog records queue high-watermark, drops, flush latency, and sink errors. Internal diagnostics (if enabled) log WARN/DEBUG messages when backpressure drops occur.
