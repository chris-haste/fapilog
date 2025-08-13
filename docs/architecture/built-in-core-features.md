# Built-in Core Features

Fapilog v3 includes essential features **out of the box** to ensure immediate productivity without requiring any plugins. These built-in components provide a complete logging solution while serving as reference implementations for the plugin ecosystem.

## Core Sinks (Built-in)

**Essential output destinations included in core library:**

- `StdoutJsonSink` (default)
  - Emits one JSON object per line to stdout
  - Uses zero-copy serialization helpers
  - Non-blocking writes using `asyncio.to_thread(...)` to avoid event loop stalls
  - Intended as a dev/default sink; production deployments typically add file/HTTP/cloud sinks via plugins
  - Includes `correlation_id` (when present in context) in the emitted JSON
  - Errors are contained and never crash the app; see Internal Diagnostics below

## Internal Diagnostics (Optional)

- Controlled by `core.internal_logging_enabled` in `Settings`
- When enabled, non-fatal internal failures (e.g., worker loop errors, sink flush errors) emit structured WARN diagnostics to stdout with `[fapilog][...]` prefixes
- Diagnostics never raise to user code and are safe to enable in development environments

## Default Enrichers (Built-in)

Two enrichers run by default before serialization and sink write:

- RuntimeInfoEnricher (`runtime_info`)
  - Adds: `service`, `env`, `version`, `host`, `pid`, `python`
  - `service`, `env`, and `version` are sourced from environment variables when present:
    - `FAPILOG_SERVICE`, `FAPILOG_ENV` (or `ENV`), `FAPILOG_VERSION`

- ContextVarsEnricher (`context_vars`)
  - Adds: `request_id` (from async context), `user_id` (if set), and optionally `trace_id`/`span_id` when OpenTelemetry context is available
  - Preserves `tenant_id` if already provided in the event payload

Behavior:
- Enrichment is best-effort and resilient; failures are contained and do not block log emission
- Enrichers are treated like built-in plugins and can be toggled at runtime

Runtime toggles:
- Disable by name: `logger.disable_enricher("context_vars")`
- Enable/append instance: `logger.enable_enricher(RuntimeInfoEnricher())`
