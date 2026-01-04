# Processors

Plugins that transform serialized log data (`memoryview`) after enrichment/redaction and before sinks.

## Contract

- `name: str`
- `async start(self) -> None` (optional)
- `async stop(self) -> None` (optional)
- `async process(self, view: memoryview) -> memoryview` (required)
- `async process_many(self, views: Iterable[memoryview]) -> list[memoryview]` (optional helper; default delegates to `process`)
- `async health_check(self) -> bool` (optional)

Errors should be contained by processors; callers isolate failures per processor.

## Usage and order

Processors run after serialization and before sinks. Configure via `core.processors` (e.g., `["gzip", "encrypt"]`). Order is preserved:

```
Event → Enrichers → Redactors → Serialize → Processor 1 → Processor 2 → Sinks
```

## When to use processors

- Compression for disk/network
- Encryption for at-rest/transport protection
- Format conversion (JSON → MessagePack/BSON)
- Checksums/MACs for integrity
- Framing or header injection for streaming protocols

If you need to add or inspect fields, use an enricher instead.

## Built-in processors

| Processor | Description |
| --- | --- |
| `zero_copy` | Pass-through processor (no transformation), useful for benchmarking |

## Example

```python
from fapilog.plugins import BaseProcessor


class GzipProcessor:
    name = "gzip"

    async def process(self, view: memoryview) -> memoryview:
        import gzip

        return memoryview(gzip.compress(bytes(view), compresslevel=6))
```
