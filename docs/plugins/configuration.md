# Plugin Configuration

This guide explains configuration-driven plugin wiring.

## Selecting Plugins

- Configure plugins via `Settings.core.*` lists:
  - `core.sinks`: sink names (default: env-driven fallback → `http` → `rotating_file` → `stdout_json`)
  - `core.enrichers`: default `runtime_info`, `context_vars`
  - `core.redactors`: empty disables; legacy `redactors_order` honored when empty and redactors enabled
  - `core.processors`: optional processors
  - `core.filters`: optional filters that run before enrichers
- Names accept hyphens or underscores; they are normalized internally (`field-mask` == `field_mask`). Built-ins register both forms.

## Per-Plugin Configuration

- Nested config blocks map to plugin names. Examples (env or code):
  - `sink_config.rotating_file`: directory, rotation, retention, compression
  - `sink_config.http`: endpoint, headers, retry, timeout
  - `sink_config.webhook`: endpoint, secret, headers, retry, timeout
  - `sink_config.loki`: url, labels, label_keys, batching, auth, circuit breaker
  - `sink_config.cloudwatch`: log group/stream, region, batching, retries, circuit breaker
  - `redactor_config.field_mask`: fields, mask string, guardrails
  - `redactor_config.regex_mask`: patterns, mask string, guardrails
  - `redactor_config.url_credentials`: max string length
  - `processor_config.zero_copy`: reserved for zero_copy options; third-party configs via `processor_config.extra`
  - `processor_config.size_guard`: `max_bytes`, `action`, and `preserve_fields` for the size_guard processor
  - `filter_config.level/sampling/adaptive_sampling/trace_sampling/first_occurrence/rate_limit`: built-in filters; third-party configs via `filter_config.extra`
  - Third-party plugins use `extra` maps (`sink_config.extra`, `enricher_config.extra`, `redactor_config.extra`, `processor_config.extra`) with arbitrary keys.

### Environment Examples

```bash
# Multiple sinks
FAPILOG_CORE__SINKS='["stdout_json","rotating_file"]'
FAPILOG_SINK_CONFIG__ROTATING_FILE__DIRECTORY="/var/log/app"

# Disable enrichers
FAPILOG_CORE__ENRICHERS='[]'

# Processors with config
FAPILOG_CORE__PROCESSORS='["gzip"]'
FAPILOG_PROCESSOR_CONFIG__EXTRA__GZIP='{\"level\":4}'

# Redactors via legacy order (still supported)
FAPILOG_CORE__ENABLE_REDACTORS=true
FAPILOG_CORE__REDACTORS_ORDER='["field-mask","regex-mask"]'
```

## Loader Behavior

- Built-ins register in the loader registry with aliases; third-party plugins discovered via entry points (`fapilog.sinks`, `fapilog.enrichers`, `fapilog.redactors`, `fapilog.processors`).
- `core.log_level` now gates events via an implicit `level` filter when no explicit `core.filters` are configured (set to `DEBUG` to allow everything).
- Allow/deny lists live under `Settings.plugins` and are respected for every plugin load.
- Missing or failing plugins emit diagnostics and are skipped; logging continues with remaining plugins.

## Integrity Wrapping

- Integrity plugins (e.g., `fapilog-tamper`) are applied **per sink**: each sink is wrapped individually for independent hash chains/manifests.
- Optional integrity enricher from the plugin is appended when provided.

```
[event] → enrichers → redactors → sink A (wrapped) && sink B (wrapped)
```

This per-sink approach keeps verification isolated and avoids a multiplexer becoming a single point of failure for integrity state.
