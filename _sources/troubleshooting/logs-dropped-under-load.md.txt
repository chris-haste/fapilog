# Logs Dropped Under Load



## Symptoms
- Missing log lines during traffic spikes
- Backpressure/drop warnings in diagnostics
- High queue utilization

## Causes
- Queue too small for burst load
- Sinks slower than producers
- Backpressure policy set to drop quickly

## Fixes
```bash
# Increase queue/batch
export FAPILOG_CORE__MAX_QUEUE_SIZE=20000
export FAPILOG_CORE__BATCH_MAX_SIZE=256
export FAPILOG_CORE__BATCH_TIMEOUT_SECONDS=0.25

# Adjust backpressure
export FAPILOG_CORE__DROP_ON_FULL=false        # wait instead of drop
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=25

# Enable metrics to monitor drops
export FAPILOG_CORE__ENABLE_METRICS=true
```

If latency is critical, keep `DROP_ON_FULL=true` but monitor drops via metrics/diagnostics and raise batch size cautiously.
