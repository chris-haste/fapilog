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
```

### Batch processing

Implement `process_many(self, views: Iterable[memoryview]) -> list[memoryview]`
when batching improves performance (shared compression dictionary, reused crypto
context, etc.). The default implementation simply calls `process()` for each
view and returns the processed results in order.

## SizeGuardProcessor

`size_guard` enforces a maximum serialized payload size before sinks run. It is
designed for destinations with hard limits (CloudWatch 256 KB, Loki 256 KB, many
HTTP gateways around 1 MB).

- **Actions:** `truncate` (default), `drop`, or `warn`
- **Default limit:** `max_bytes=256000` (CloudWatch safe)
- **Truncation:** Marks payloads with `_truncated` and `_original_size`, trims
  `message` first, then prunes metadata, and finally falls back to preserved
  fields only (`level`, `timestamp`, `logger`, `correlation_id` by default).
- **Diagnostics:** Emits a WARN diagnostic with original size and limit (rate
  limited). Metrics counters increment for truncated/dropped events when metrics
  are enabled.

Enable it in settings:

```python
from fapilog import Settings

settings = Settings()
settings.core.processors = ["size_guard"]
settings.processor_config.size_guard.max_bytes = 256_000
settings.processor_config.size_guard.action = "truncate"  # or "drop"/"warn"
settings.processor_config.size_guard.preserve_fields = [
    "level",
    "timestamp",
    "logger",
    "correlation_id",
]
```

Environment shortcuts:

```bash
export FAPILOG_CORE__PROCESSORS='["size_guard"]'
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__MAX_BYTES=200000
export FAPILOG_PROCESSOR_CONFIG__SIZE_GUARD__ACTION=drop
# Short aliases for ops overrides
export FAPILOG_SIZE_GUARD__MAX_BYTES=180000
export FAPILOG_SIZE_GUARD__ACTION=warn
```

## Built-in processors

| Processor | Description |
| --- | --- |
| `size_guard` | Enforces maximum payload size with truncate/drop/warn actions |
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

Processors operate on serialized bytes, so enable `core.serialize_in_flush` when
using sinks that support `write_serialized` to ensure the processor stage is
invoked.
