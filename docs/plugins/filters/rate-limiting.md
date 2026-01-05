# Rate Limiting Filter

The `rate_limit` filter applies a token-bucket limit before enrichment. It now supports bounded bucket counts, configurable overflow handling, and diagnostics when nearing capacity.

## Configuration

```yaml
core:
  filters: ["rate_limit"]
filter_config:
  rate_limit:
    config:
      capacity: 10            # tokens per bucket
      refill_rate_per_sec: 5  # tokens/second
      key_field: user_id      # optional per-key isolation
      max_keys: 10000         # bounded bucket count (LRU eviction)
      overflow_action: drop   # drop | mark
```

- **capacity / refill_rate_per_sec**: classic token-bucket controls.
- **key_field**: partitions buckets (e.g., per user, tenant, API key). Omit for a global bucket.
- **max_keys**: bounds memory; oldest buckets evict when the limit is reached.
- **overflow_action**: set to `mark` to keep the event but annotate it with `rate_limited=True` instead of dropping.

## Health & diagnostics

- `health_check()` returns `False` when tracked keys exceed 90% of `max_keys` and emits a diagnostic warning.
- Gauge `fapilog_rate_limit_keys_tracked` reports current bucket count when metrics are enabled.
- Drops still increment `fapilog_events_filtered_total`.
