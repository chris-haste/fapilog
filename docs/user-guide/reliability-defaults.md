# Reliability Defaults and Guardrails

This page summarizes the out-of-the-box behaviors that affect durability, backpressure, and data protection.

## Backpressure and drops
- Queue size: `core.max_queue_size=10000`
- Drop policy: `core.drop_on_full=True` (drop immediately when queue is full)
- Batch flush: `core.batch_max_size=256`, `core.batch_timeout_seconds=0.25`

### Non-blocking enqueue behavior

With the dedicated thread architecture, `try_enqueue()` is always non-blocking — it either succeeds or drops immediately. The `drop_on_full=False` setting cannot be honored because the caller thread cannot block waiting for queue space on the worker thread's loop.

When `drop_on_full=False` is configured with `SyncLoggerFacade`, a diagnostic warning is emitted at startup to alert you that blocking behavior is not supported.

**Recommendation**: Size your queue appropriately (`core.max_queue_size`) to handle burst traffic without dropping. Both `SyncLoggerFacade` and `AsyncLoggerFacade` use the same non-blocking enqueue path.

## Redaction defaults

- **With no preset**: URL credential redaction is **enabled by default** (`core.redactors=["url_credentials"]`). This provides secure defaults by automatically scrubbing credentials from URLs in log output.
- **With `preset="production"`, `preset="adaptive"`, or `preset="serverless"`**: Enables `field_mask`, `regex_mask`, and `url_credentials` in that order.
  - `field_mask`: Masks specific `data.*` fields (password, api_key, token, etc.)
  - `regex_mask`: Matches any field path containing sensitive keywords (password, secret, token, etc.)
  - `url_credentials`: Strips userinfo from URLs
- **With `dev` and `minimal` presets**: Redaction is **explicitly disabled** (`redactors: []`) for development visibility and debugging. Use `Settings()` without a preset or a production-grade preset if you need URL credential protection in these environments.
- **Opt-out**: Set `core.redactors=[]` to disable all redaction, or `core.enable_redactors=False` to disable the redactors stage entirely.
- Order when active: `field-mask` → `regex-mask` → `url-credentials`
- Guardrails: `core.redaction_max_depth=6`, `core.redaction_max_keys_scanned=5000`

See {ref}`guardrails` for complete details on how core and per-redactor guardrails interact, and [Redaction Behavior](../redaction/behavior.md) for what's redacted and **failure mode configuration** for production systems.

### Fallback raw output hardening

When the fallback sink cannot parse a serialized payload as JSON (e.g., binary data or malformed content), it writes raw bytes to stderr. This "safety net" path now includes additional protections:

- **Keyword scrubbing** (default enabled): Applies regex patterns to mask common secret formats like `password=value`, `token=value`, `api_key=value`, and `authorization: Bearer token` before output.
- **Optional truncation**: Set `core.fallback_raw_max_bytes` to limit raw output size, useful for preventing large payloads from flooding stderr.
- **Diagnostic metadata**: The warning includes `scrubbed`, `truncated`, and `original_size` fields for observability.

Settings:
- `core.fallback_scrub_raw=True` (default): Apply keyword scrubbing to raw fallback output
- `core.fallback_raw_max_bytes=None` (default): No truncation; set to a byte limit to truncate large payloads
- Set `FAPILOG_CORE__FALLBACK_SCRUB_RAW=false` to disable scrubbing for debugging

**Trade-offs**: Regex scrubbing targets key=value patterns and may not catch all sensitive data in arbitrary formats. For full PII protection, ensure JSON serialization succeeds or configure explicit redactors.

## Exceptions and diagnostics
- Exceptions serialized by default: `core.exceptions_enabled=True`
- Internal diagnostics are off by default: enable with `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` to see worker/sink warnings.
- Error dedupe: identical ERROR/CRITICAL messages suppressed for `core.error_dedupe_window_seconds=5.0`

## Recommended production toggles
- Set `FAPILOG_CORE__DROP_ON_FULL=false` to avoid drops under pressure.
- Enable metrics (`FAPILOG_CORE__ENABLE_METRICS=true`) plus Prometheus exporter (`fapilog[metrics]`) to watch queue depth, drops, and sink errors.
- Enable internal diagnostics during rollout to catch sink/enrichment issues early.
