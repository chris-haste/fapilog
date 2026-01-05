# Handling Size-Limited Destinations

Many log backends enforce strict per-event limits (CloudWatch and Loki: 256 KB,
Datadog and Kafka defaults: ~1 MB). Use the built-in `size_guard` processor to
enforce these limits **before** data hits the sink.

## Enable size_guard

```python
from fapilog import Settings

settings = Settings()
settings.core.processors = ["size_guard"]
settings.processor_config.size_guard.max_bytes = 256_000  # CloudWatch safe default
settings.processor_config.size_guard.action = "truncate"  # or "drop" / "warn"
```

Env-based setup:

```bash
export FAPILOG_CORE__PROCESSORS='["size_guard"]'
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES=256000
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION=truncate
```

Short aliases work for ops overrides:

```bash
export FAPILOG_SIZE_GUARD__MAX_BYTES=200000
export FAPILOG_SIZE_GUARD__ACTION=drop
```

## CloudWatch and Loki (256 KB limit)

```bash
export FAPILOG_CORE__PROCESSORS='["size_guard"]'
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES=256000
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION=truncate
```

Notes:

- Truncation adds `_truncated: true` and `_original_size` for observability.
- `message` is trimmed first; metadata is pruned only if still too large.
- Diagnostics are rate-limited WARN logs; enable them with
  `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` during investigations.

## Kafka / HTTP gateways (~1 MB)

Kafka brokers and many HTTP gateways use ~1 MB defaults. Set a higher threshold:

```bash
export FAPILOG_CORE__PROCESSORS='["size_guard"]'
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES=1000000
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION=warn
```

In `warn` mode the payload passes through unchanged but diagnostics flag the
oversize condition so you can tune producers.

## Metrics and troubleshooting

- Metrics (when enabled): `processor_size_guard_truncated_total`,
  `processor_size_guard_dropped_total`.
- Diagnostics include `original_size` and `max_bytes`; search for component
  `processor` and message prefix `size_guard`.
- For hard failures from a destination, set `action=drop` to emit a tiny marker
  payload instead of losing the log entirely.
