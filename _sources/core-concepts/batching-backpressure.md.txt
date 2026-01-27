# Batching & Backpressure

Control what happens when logs arrive faster than your sinks can handle them. You decide: drop logs to protect latency, or wait to guarantee delivery.

## Queue and batching

- `core.max_queue_size` (env: `FAPILOG_CORE__MAX_QUEUE_SIZE`): ring buffer capacity.
- `core.batch_max_size` (env: `FAPILOG_CORE__BATCH_MAX_SIZE`): max entries per flush.
- `core.batch_timeout_seconds` (env: `FAPILOG_CORE__BATCH_TIMEOUT_SECONDS`): time trigger for partial batches.

## Backpressure policy

- `core.backpressure_wait_ms` (env: `FAPILOG_CORE__BACKPRESSURE_WAIT_MS`): wait for space before dropping.
- `core.drop_on_full` (env: `FAPILOG_CORE__DROP_ON_FULL`): when True, drop after wait timeout; when False, keep waiting.

## When to tune

**Favor throughput (never lose logs)** if:
- You're legally required to capture every log (PCI, HIPAA, SOC2)
- A traffic spike is acceptable as long as logs aren't lost
- You have memory to spare for a larger queue

**Favor low latency (protect response times)** if:
- Your SLA is strict on request latency (e.g., < 100ms p99)
- You can tolerate occasional log drops during extreme spikes
- Memory is constrained (edge deployments, serverless)

## Tuning examples

```bash
# Favor throughput: never lose logs, tolerate brief latency during spikes
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.25
export FAPILOG_CORE__DROP_ON_FULL=false

# Favor low latency: protect response times, accept occasional drops
export FAPILOG_CORE__MAX_QUEUE_SIZE=5000
export FAPILOG_CORE__BATCH_MAX_SIZE=64
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.1
export FAPILOG_CORE__DROP_ON_FULL=true
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=10
```

## Metrics and diagnostics

When `core.enable_metrics=True`, fapilog records queue high-watermark, drops, flush latency, and sink errors. Internal diagnostics (if enabled) log WARN/DEBUG messages when backpressure drops occur.
