# Processors

Transform or filter log entries between enrichment and queue/sink stages. Implement `BaseProcessor`.

## Implementing a processor

```python
from fapilog.plugins import BaseProcessor

class SamplingProcessor(BaseProcessor):
    name = "sampling-processor"

    async def process(self, entry: dict) -> dict | None:
        # Return None to drop, or a modified entry to continue
        return entry
```

## Registering a processor

- Declare an entry point under `fapilog.processors` in `pyproject.toml`.
- Provide `PLUGIN_METADATA` with `plugin_type: "processor"` and compatible API version.

## Built-in processors

- Core pipeline currently runs without custom processors by default; processors are reserved for advanced transforms/filters.

## Usage

Processors execute after enrichers and redactors but before queueing/sink emission when configured. Ensure they are non-blocking and handle errors internally to avoid disrupting the pipeline.
