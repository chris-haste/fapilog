# Enrichers

Plugins that add metadata to log entries before redaction and sinks.

## Contract

Implement `BaseEnricher.enrich(entry: dict) -> dict` (async). Return the updated entry; contain errors to avoid breaking the pipeline.

## Built-in enrichers

- **runtime-info**: adds service/env/version/host/pid/python.
- **context-vars**: adds `request_id`, `user_id` from ContextVar when present.

## Runtime control

- `logger.enable_enricher(enricher_instance)`
- `logger.disable_enricher("context_vars")`

Enrichers run per entry before redactors.*** End Patch
