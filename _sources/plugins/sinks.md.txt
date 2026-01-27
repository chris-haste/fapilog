# Sinks

Output destinations for serialized log entries. Implement `BaseSink`.

## Implementing a sink

```python
from fapilog.plugins import BaseSink

class MySink(BaseSink):
    name = "my_sink"

    async def start(self) -> None:
        ...

    async def write(self, entry: dict) -> bool | None:
        # entry is a dict log envelope; emit to your target
        # Return None/True for success, False for failure
        ...

    async def stop(self) -> None:
        ...
```

### Return value semantics

| Return | Meaning | Core action |
| --- | --- | --- |
| `None` / no return | Success | None |
| `True` | Success | None |
| `False` | Failure | Trigger fallback, increment circuit breaker |
| `SinkWriteError` raised | Failure | Trigger fallback, increment circuit breaker |

For detailed error handling patterns, see [Plugin Error Handling](error-handling.md).

## Registering a sink

- Declare an entry point under `fapilog.sinks` in `pyproject.toml`.
- Add a `PLUGIN_METADATA` dict with `plugin_type: "sink"` and an API version compatible with `fapilog.plugins.versioning.PLUGIN_API_VERSION`.

## Built-in sinks (code-supported)

- `stdout_json` (structured JSON)
- `stdout_pretty` (human-readable console output)
- `rotating_file` (size/time rotation)
- `http` (HTTP POST)
- `webhook` (JSON webhook with optional batching)
- `cloudwatch` (AWS CloudWatch Logs; optional `fapilog[aws]`)
- `mmap_persistence` (experimental; local persistence)

```{toctree}
:maxdepth: 1
:titlesonly:

sinks/cloudwatch
sinks/loki
sinks/postgres
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

### Error handling in write_serialized

**Important:** `write_serialized` must handle deserialization errors correctly to avoid silent data loss. Never replace invalid data with placeholder values like `{"message": "fallback"}`.

**Required pattern:**

```python
import json
from fapilog.core.diagnostics import warn
from fapilog.core.errors import SinkWriteError
from fapilog.core.serialization import SerializedView

async def write_serialized(self, view: SerializedView) -> None:
    """Fast path for pre-serialized payloads."""
    try:
        data = json.loads(bytes(view.data))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        warn(
            f"{self.name}-sink",
            "write_serialized deserialization failed",
            error=str(exc),
            data_size=len(view.data),
            _rate_limit_key=f"{self.name}-sink-deserialize",
        )
        raise SinkWriteError(
            f"Failed to deserialize payload in {self.name}.write_serialized",
            sink_name=self.name,
            cause=exc,
        ) from exc
    await self.write(data)
```

**Key requirements:**

1. **Catch specific exceptions** - Use `json.JSONDecodeError` and `UnicodeDecodeError`, not bare `except Exception:`
2. **Emit diagnostics** - Call `diagnostics.warn()` with context (sink name, error, data size)
3. **Raise SinkWriteError** - Signal failure to the core for fallback/circuit breaker handling
4. **Chain the cause** - Use `from exc` to preserve the original exception

See [Plugin Error Handling](error-handling.md) for more details on `SinkWriteError` and failure signaling.
