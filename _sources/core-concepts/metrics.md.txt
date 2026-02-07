# Metrics

Optional internal metrics for observability.

## Enabling

Set `core.enable_metrics=True` (env: `FAPILOG_CORE__ENABLE_METRICS=true`). Metrics are recorded asynchronously; exporting is left to the application.

## What is recorded

- Events submitted/dropped
- Queue high-watermark
- Backpressure waits
- Flush latency (per batch)
- Sink errors
- Priority queue evictions and drops

## Prometheus Metrics Reference

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `fapilog_events_submitted_total` | Counter | - | Events successfully enqueued |
| `fapilog_events_dropped_total` | Counter | `protected` | Events dropped due to backpressure |
| `fapilog_events_processed_total` | Counter | - | Events processed by workers |
| `fapilog_queue_high_watermark` | Gauge | - | Maximum queue depth observed |
| `fapilog_backpressure_waits_total` | Counter | - | Times backpressure was applied |
| `fapilog_flush_seconds` | Histogram | - | Batch flush latency |
| `fapilog_batch_size` | Histogram | - | Events per batch |
| `fapilog_sink_errors_total` | Counter | `sink` | Sink write failures |
| `fapilog_priority_evictions_total` | Counter | - | Evictions triggered by protected events |
| `fapilog_events_evicted_total` | Counter | `level` | Events evicted by log level |
| `fapilog_redacted_fields_total` | Counter | - | Total fields masked by redactors |
| `fapilog_policy_violations_total` | Counter | - | Policy violation flags from field_blocker |
| `fapilog_sensitive_fields_total` | Counter | - | Fields logged via `sensitive=`/`pii=` container |
| `fapilog_redaction_exceptions_total` | Counter | - | Redaction pipeline exceptions |

## Priority Queue Metrics

When using protected levels (default: ERROR, CRITICAL, FATAL), the queue tracks priority-based behavior:

```promql
# Priority protection effectiveness - how often eviction saved protected events
rate(fapilog_priority_evictions_total[5m])

# Protected events we failed to save (queue saturated with protected events)
rate(fapilog_events_dropped_total{protected="true"}[5m])

# What levels are being sacrificed to save errors?
topk(5, rate(fapilog_events_evicted_total[5m])) by (level)

# Ratio of protected vs unprotected drops
rate(fapilog_events_dropped_total{protected="true"}[5m])
  / rate(fapilog_events_dropped_total[5m])
```

### Alerting on Protection Failures

```yaml
# Alert when protected events are being dropped (queue saturated)
- alert: FapilogProtectedEventsDropped
  expr: rate(fapilog_events_dropped_total{protected="true"}[5m]) > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Protected log events being dropped - queue saturated"
```

(redaction-metrics)=
## Redaction Metrics

Redaction operational metrics are recorded automatically when `core.enable_metrics=True`. These counters track masking activity, policy enforcement, and pipeline health.

| Metric | What It Tracks |
|--------|----------------|
| `fapilog_redacted_fields_total` | Fields masked by any redactor (field_mask, regex_mask, string_truncate, etc.) |
| `fapilog_policy_violations_total` | Fields blocked by `field_blocker` (e.g., `body`, `payload`) |
| `fapilog_sensitive_fields_total` | Fields declared via `sensitive={}` or `pii={}` at log time |
| `fapilog_redaction_exceptions_total` | Unexpected exceptions in the redaction pipeline |

### PromQL Examples

```promql
# Redaction activity rate
rate(fapilog_redacted_fields_total[5m])

# Policy violations — are developers logging blocked fields?
rate(fapilog_policy_violations_total[5m])

# Sensitive container adoption — are developers using sensitive={}?
rate(fapilog_sensitive_fields_total[5m])

# Redaction pipeline health — any exceptions?
rate(fapilog_redaction_exceptions_total[5m])
```

### Alerting on Redaction Issues

```yaml
# Alert when redaction pipeline is throwing exceptions
- alert: FapilogRedactionExceptions
  expr: rate(fapilog_redaction_exceptions_total[5m]) > 0
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "Redaction pipeline exceptions detected"

# Alert on high policy violation rate (field_blocker blocking fields)
- alert: FapilogPolicyViolations
  expr: rate(fapilog_policy_violations_total[5m]) > 10
  for: 5m
  labels:
    severity: info
  annotations:
    summary: "High rate of policy violations — review blocked field usage"
```

## System Metrics

System metrics (CPU usage, memory, disk I/O) are provided by the `runtime_info` enricher when the `system` extra is installed.

> **Platform Note:** System metrics require `psutil`, which is only installed on Linux and macOS. On Windows, system metrics fields will not be populated.
>
> ```bash
> # Linux/macOS - psutil installed, system metrics available
> pip install fapilog[system]
>
> # Windows - psutil not installed, system metrics unavailable
> pip install fapilog[system]  # Installs fapilog but not psutil
> ```

## Usage

```python
from fapilog import Settings, get_logger

settings = Settings(core__enable_metrics=True)
logger = get_logger(settings=settings)
logger.info("metrics enabled")
```

Expose or scrape metrics from your application using your preferred exporter; fapilog does not start an HTTP metrics server itself.
