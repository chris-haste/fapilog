# Processors

Processors transform **serialized** log data (memoryview) after enrichment/redaction and before sinks run.

## When to use processors

Use processors when you need to operate on bytes, not event dicts. Examples:

| Use case | Description |
| --- | --- |
| Compression | Compress JSON before writing to disk/network |
| Encryption | Encrypt serialized entries for storage or transport |
| Format conversion | Convert JSON to MessagePack/BSON/Avro |
| Checksums | Add integrity MAC/CRC for downstream verification |
| Framing | Add message boundaries/headers for streaming protocols |

### Processors vs. Enrichers

| Question | Use an enricher | Use a processor |
| --- | --- | --- |
| Need to add fields to the event dict? | ✅ | ❌ |
| Need to transform raw bytes? | ❌ | ✅ |
| Input type | `dict` | `memoryview` |
| Called | Before serialization | After serialization |

Rule of thumb: if you must inspect or add fields, use an enricher. If you only need to transform the serialized bytes, use a processor.

## Implementing a processor

```python
from fapilog.plugins import BaseProcessor


class GzipProcessor:
    """Compress serialized entries with gzip."""

    name = "gzip"

    def __init__(self, level: int = 6) -> None:
        self._level = level

    async def start(self) -> None:
        pass  # optional

    async def stop(self) -> None:
        pass  # optional

    async def process(self, view: memoryview) -> memoryview:
        import gzip

        compressed = gzip.compress(bytes(view), compresslevel=self._level)
        return memoryview(compressed)

    async def health_check(self) -> bool:
        return True
```

### Example: Encrypt before sinks

```python
from cryptography.fernet import Fernet


class EncryptProcessor:
    name = "encrypt"

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    async def process(self, view: memoryview) -> memoryview:
        encrypted = self._fernet.encrypt(bytes(view))
        return memoryview(encrypted)
```

### Example: Convert JSON to MessagePack

```python
import json
import msgpack


class MsgPackProcessor:
    name = "msgpack"

    async def process(self, view: memoryview) -> memoryview:
        data = json.loads(bytes(view))
        packed = msgpack.packb(data)
        return memoryview(packed)


### Batch processing

Implement `process_many(self, views: Iterable[memoryview]) -> list[memoryview]`
when batching improves performance (shared compression dictionary, reused crypto
context, etc.). The default implementation simply calls `process()` for each
view and returns the processed results in order.
```

## Built-in processors

| Processor | Description |
| --- | --- |
| `zero_copy` | Pass-through processor for benchmarking (no transformation) |

## Registration

- Declare an entry point under `fapilog.processors` in `pyproject.toml`.
- Include `PLUGIN_METADATA` with `plugin_type: "processor"` and compatible API version.

## Configuration and order

Configure processors via settings (`core.processors`) or env (`FAPILOG_CORE__PROCESSORS`). Per-processor kwargs live under `processor_config` (e.g., `processor_config.extra.gzip = {"level": 5}`). They run in order:

```
Event → Enrichers → Redactors → Serialize → Processor 1 → Processor 2 → Sinks
```

Keep processors async, contain errors, and consider CPU/I/O cost since they run on every log write.
