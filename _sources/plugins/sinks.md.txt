# Sinks

Output destinations for serialized log entries. Implement `BaseSink`.

## Implementing a sink

```python
from fapilog.plugins import BaseSink

class MySink(BaseSink):
    name = "my_sink"

    async def start(self) -> None:
        ...

    async def write(self, entry: dict) -> None:
        # entry is a dict log envelope; emit to your target
        ...

    async def stop(self) -> None:
        ...
```

## Registering a sink

- Declare an entry point under `fapilog.sinks` in `pyproject.toml`.
- Add a `PLUGIN_METADATA` dict with `plugin_type: "sink"` and an API version compatible with `fapilog.plugins.versioning.PLUGIN_API_VERSION`.

## Built-in sinks (code-supported)

- `stdout_json` (default)
- `rotating_file` (size/time rotation)
- `http` (HTTP POST)
- `webhook` (JSON webhook with optional batching)
- `cloudwatch` (AWS CloudWatch Logs; optional `fapilog[aws]`)
- `mmap_persistence` (experimental; local persistence)

```{toctree}
:maxdepth: 1
:titlesonly:

sinks/cloudwatch
```

### HTTP sink batching

`HttpSink` now supports sink-level batching to reduce request volume:

- `batch_size` (default: 1 for backward compatibility; set >1 to enable batching)
- `batch_timeout_seconds` (default: 5.0) flush partial batches on timeout
- `batch_format`: `array` (JSON array), `ndjson` (newline-delimited), `wrapped` (`{"logs": [...]}`)
- `batch_wrapper_key`: wrapper key when `batch_format="wrapped"` (default: `logs`)

Examples:

```bash
export FAPILOG_HTTP__ENDPOINT=https://logs.example.com/ingest
export FAPILOG_HTTP__BATCH_SIZE=100
export FAPILOG_HTTP__BATCH_TIMEOUT_SECONDS=2.0
export FAPILOG_HTTP__BATCH_FORMAT=ndjson
```

```python
from fapilog.plugins.sinks.http_client import HttpSink, HttpSinkConfig, BatchFormat

sink = HttpSink(
    HttpSinkConfig(
        endpoint="https://logs.example.com/ingest",
        batch_size=100,
        batch_timeout_seconds=2.0,
        batch_format=BatchFormat.NDJSON,
    )
)
```

### Webhook sink batching

`WebhookSink` supports the same `batch_size` and `batch_timeout_seconds` fields to batch webhook POSTs (default `batch_size=1` for compatibility).

## Usage

Sinks are discovered via entry points when plugin discovery is enabled. You can also wire custom sinks programmatically by passing them into the container/settings before creating a logger.

## Optional: write_serialized fast path

For sinks that operate on bytes (files, sockets, HTTP), implement `write_serialized()` to accept a pre-serialized payload and avoid redundant JSON encoding when `Settings.core.serialize_in_flush=True`:

```python
from fapilog.core.serialization import SerializedView

class MyFastSink:
    name = "my_fast_sink"

    async def write(self, entry: dict) -> None:
        # Fallback path: serialize yourself
        data = json.dumps(entry).encode()
        await self._send(data)

    async def write_serialized(self, view: SerializedView) -> None:
        # Fast path: fapilog already serialized; avoid extra work
        await self._send(bytes(view.data))
```

When to implement:
- You already need serialized bytes
- You do not need to inspect/modify the dict entry
- Performance or allocation reduction is important

If `write_serialized` is absent, fapilog automatically calls `write()` instead. The `SerializedView` wrapper exposes a memoryview via `data` and `__bytes__` for convenience; treat it as read-only.
