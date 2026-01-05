# Logs Rejected by Destination Size Limits

Some destinations (CloudWatch, Loki, Datadog, Kafka) drop or reject events that
exceed strict size limits. Without guardrails you may see silent loss or hard
errors.

## Symptoms

- Events vanish when payloads are large (stack traces, verbose metadata)
- CloudWatch rejects batches with `DataAlreadyAcceptedException` or size errors
- Loki/HTTP gateways return 4xx/5xx on oversized log lines
- Kafka producers raise `RecordTooLargeException`

## Causes

- Serialized JSON exceeds the destination's per-event limit
- Unbounded `message` fields (tracebacks, large blobs)
- Large metadata maps attached to each event

## Resolution

1) **Enable SizeGuardProcessor**

```bash
export FAPILOG_CORE__PROCESSORS='["size_guard"]'
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES=256000   # CloudWatch/Loki
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION=truncate    # or drop/warn
```

Short aliases also work:

```bash
export FAPILOG_SIZE_GUARD__MAX_BYTES=200000
export FAPILOG_SIZE_GUARD__ACTION=warn
```

2) **Choose the right action**

- `truncate` (default): trims `message` first, prunes metadata if needed, adds
  `_truncated` and `_original_size` markers.
- `drop`: replaces payload with a small marker and `_dropped: true`.
- `warn`: passes through unchanged but emits diagnostics so you can tune limits.

3) **Monitor metrics and diagnostics**

- Metrics (when enabled): `processor_size_guard_truncated_total`,
  `processor_size_guard_dropped_total`.
- Enable internal diagnostics temporarily:
  `export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` to see WARN logs with the
  original size and configured limit.

## Quick checks

- Confirm `core.processors` includes `size_guard` and `serialize_in_flush` is
  enabled in your settings when using sinks that support serialized writes.
- Keep `preserve_fields` to a minimum to leave more room for truncation
  (defaults: `level`, `timestamp`, `logger`, `correlation_id`).

If issues persist after enabling `size_guard`, lower `max_bytes` slightly below
the destination's hard limit to allow for framing/headers added by the transport.
