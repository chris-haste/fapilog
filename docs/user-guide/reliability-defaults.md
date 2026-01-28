# Reliability Defaults and Guardrails

This page summarizes the out-of-the-box behaviors that affect durability, backpressure, and data protection.

## Backpressure and drops
- Queue size: `core.max_queue_size=10000`
- Wait before drop: `core.backpressure_wait_ms=50`
- Drop policy: `core.drop_on_full=True` (wait up to 50 ms, then drop). **Set `core.drop_on_full=false` for production if you prefer waiting over dropping.**
- Batch flush: `core.batch_max_size=256`, `core.batch_timeout_seconds=0.25`

### Same-thread context behavior

When `SyncLoggerFacade` is called from the same thread as its internal worker loop, backpressure behavior differs from cross-thread calls:

- **Same-thread**: Events are dropped immediately if the queue is full, regardless of the `drop_on_full` setting
- **Cross-thread**: Events wait up to `backpressure_wait_ms` before dropping (respecting `drop_on_full`)

This is intentional—blocking on the same thread would cause a deadlock since the thread cannot wait on its own event loop. When a same-thread drop occurs with `drop_on_full=False`, a diagnostic warning is emitted to alert you that your backpressure configuration cannot be honored in that context.

**Recommendation**: In async contexts (FastAPI routes, asyncio code), use `AsyncLoggerFacade` to avoid same-thread semantics entirely. The async facade integrates with the event loop without blocking.

## Redaction defaults

- **With no preset**: URL credential redaction is **enabled by default** (`core.redactors=["url_credentials"]`). This provides secure defaults by automatically scrubbing credentials from URLs in log output.
- **With `preset="production"`, `preset="fastapi"`, or `preset="serverless"`**: Enables `field_mask`, `regex_mask`, and `url_credentials` in that order.
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
