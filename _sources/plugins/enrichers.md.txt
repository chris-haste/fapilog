# Enrichers

Add contextual metadata to log entries. Implement `BaseEnricher`.

## Implementing an enricher

```python
from fapilog.plugins import BaseEnricher

class MyEnricher(BaseEnricher):
    name = "my-enricher"

    async def enrich(self, entry: dict) -> dict:
        entry["service"] = "billing"
        return entry
```

## Registering an enricher

- Declare an entry point under `fapilog.enrichers` in `pyproject.toml`.
- Provide `PLUGIN_METADATA` with `plugin_type: "enricher"` and compatible API version.

## Built-in enrichers

- `runtime-info` (host, pid, python, service/env/version)
- `context-vars` (request/user IDs from ContextVar)

## Usage

Enrichers run before redaction and sinks. You can enable/disable at runtime via `logger.enable_enricher` / `logger.disable_enricher` (sync/async facades).
