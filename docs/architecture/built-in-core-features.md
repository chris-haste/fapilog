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