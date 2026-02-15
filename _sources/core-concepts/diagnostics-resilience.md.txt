# Diagnostics Resilience


# Diagnostics & Resilience

Fapilog is designed to contain errors and surface diagnostics without crashing applications.

## Internal diagnostics

- Enable with `FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true`.
- Emits WARN/DEBUG lines for worker errors, sink errors, backpressure drops, and serialization issues.
- Output goes to **stderr** by default (Unix convention), keeping diagnostics separate from application logs on stdout.
- Use `core.diagnostics_output="stdout"` for backward compatibility with older log pipelines.

## Error containment

- Enrichment, redaction, and sink errors are caught; offending entries may be dropped but do not raise into the app.
- Backpressure drops are counted and optionally logged.
- Error deduplication: identical ERROR/CRITICAL messages within a window (`core.error_dedupe_window_seconds`) are suppressed to reduce noise, with a summary emitted when the window rolls.

## Shutdown behavior

- `stop_and_drain()` signals the dedicated worker thread to stop and joins it with a timeout (`core.shutdown_timeout_seconds`) to avoid hangs.

## Resilience tips

- Keep `drop_on_full=True` for burst protection in latency-sensitive paths; monitor drops via metrics.
- Use redaction guardrails (`redaction_max_depth`, `redaction_max_keys_scanned`) to avoid pathological data structures.
- Enable internal diagnostics temporarily during investigations; keep it off in steady state if noisy.
