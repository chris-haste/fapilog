# Sinks



Output plugins that deliver serialized log entries to destinations.

## Contract

Implement `BaseSink` methods:

- `async start(self) -> None`: optional initialization.
- `async write(self, entry: dict) -> None`: required; receives enriched/redacted envelope.
- `async stop(self) -> None`: optional teardown.

Errors should be contained; do not raise into the pipeline.

### Optional methods

#### write_serialized

```python
async def write_serialized(self, view: SerializedView) -> None
```

Fast path when `Settings.core.serialize_in_flush=True`. If present, fapilog pre-serializes entries once and calls this method instead of `write()` for sinks that consume bytes. If absent, fapilog automatically falls back to `write()`.

`SerializedView` exposes:

```python
@dataclass
class SerializedView:
    data: memoryview

    def __bytes__(self) -> bytes:
        return bytes(self.data)
```

## Built-in sinks

- **stdout_json**: default sink, JSON lines to stdout.
- **rotating_file**: size/time-based rotation with optional compression.
- **http**: POST log entries to an HTTP endpoint.
- **webhook**: POST log entries to a webhook with optional signing.

## Configuration (env)

Rotating file:
```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

HTTP sink:
```bash
export FAPILOG_HTTP__ENDPOINT=https://logs.example.com/ingest
export FAPILOG_HTTP__TIMEOUT_SECONDS=5
export FAPILOG_HTTP__RETRY_MAX_ATTEMPTS=3
export FAPILOG_HTTP__BATCH_SIZE=100
export FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS=5
export FAPILOG_HTTP__BATCH_FORMAT=array   # array|ndjson|wrapped
export FAPILOG_HTTP__BATCH_WRAPPER_KEY=logs
```

## Building Blocks

### MemoryMappedPersistence

A low-level memory-mapped file writer for building custom zero-copy sinks.

**Note:** `MemoryMappedPersistence` is **not a sink itself**—it does not implement
the `BaseSink` protocol. Instead, it provides efficient byte-level append operations
that you can use to build performance-critical custom sinks.

```python
from fapilog.plugins.sinks import BaseSink, MemoryMappedPersistence
import json


class MyMmapSink:
    """Example custom sink using MemoryMappedPersistence."""
    
    name = "my_mmap"

    def __init__(self, path: str):
        self._mmap = MemoryMappedPersistence(path)

    async def start(self) -> None:
        await self._mmap.open()

    async def write(self, entry: dict) -> None:
        data = json.dumps(entry).encode()
        await self._mmap.append_line(data)

    async def stop(self) -> None:
        await self._mmap.close()

    async def health_check(self) -> bool:
        return await self._mmap.health_check()
```

See the `MemoryMappedPersistence` class documentation for full API details including
configuration options for initial size, growth factor, and sync behavior.
