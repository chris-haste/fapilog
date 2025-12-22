# Sinks

Output destinations for serialized log entries. Implement `BaseSink`.

## Implementing a sink

```python
from fapilog.plugins import BaseSink

class MySink(BaseSink):
    name = "my-sink"

    async def start(self) -> None:
        ...

    async def write(self, entry: dict) -> None:
        # entry is a dict log envelope; emit to your target
        ...

    async def write_serialized(self, view) -> None:
        # Optional fast-path when serialize_in_flush=True
        ...

    async def stop(self) -> None:
        ...
```

## Registering a sink

- Declare an entry point under `fapilog.sinks` in `pyproject.toml`.
- Add a `PLUGIN_METADATA` dict with `plugin_type: "sink"` and an API version compatible with `fapilog.plugins.versioning.PLUGIN_API_VERSION`.

## Built-in sinks (code-supported)

- `stdout-json` (default)
- `rotating-file` (size/time rotation)
- `http_client` (HTTP POST)
- `mmap_persistence` (experimental; local persistence)

## Usage

Sinks are discovered via entry points when plugin discovery is enabled. You can also wire custom sinks programmatically by passing them into the container/settings before creating a logger.
