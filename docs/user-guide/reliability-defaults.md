# Reliability Defaults and Guardrails

This page summarizes the out-of-the-box behaviors that affect durability, backpressure, and data protection.

## Backpressure and drops
- Queue size: `core.max_queue_size=10000`
- Wait before drop: `core.backpressure_wait_ms=50`
- Drop policy: `core.drop_on_full=True` (wait up to 50 ms, then drop). **Set `core.drop_on_full=false` for production if you prefer waiting over dropping.**
- Batch flush: `core.batch_max_size=256`, `core.batch_timeout_seconds=0.25`

## Redaction defaults
- Redactors enabled: `core.enable_redactors=True`
- Order: `field-mask` → `regex-mask` → `url-credentials`
- Patterns: regex-mask uses a broad secret matcher (password/pass/secret/api key/token/authorization/set-cookie/ssn/email).
- Guardrails: `core.redaction_max_depth=6`, `core.redaction_max_keys_scanned=5000`

## Exceptions and diagnostics
- Exceptions serialized by default: `core.exceptions_enabled=True`
- Internal diagnostics are off by default: enable with `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true` to see worker/sink warnings.
- Error dedupe: identical ERROR/CRITICAL messages suppressed for `core.error_dedupe_window_seconds=5.0`

## Recommended production toggles
- Set `FAPILOG_CORE__DROP_ON_FULL=false` to avoid drops under pressure.
- Enable metrics (`FAPILOG_CORE__ENABLE_METRICS=true`) plus Prometheus exporter (`fapilog[metrics]`) to watch queue depth, drops, and sink errors.
- Enable internal diagnostics during rollout to catch sink/enrichment issues early.
