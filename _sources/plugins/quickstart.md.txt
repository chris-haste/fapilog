# Plugin Author Quickstart

Create custom fapilog plugins in 10 minutes.

## Overview

Fapilog supports five plugin types:

| Type | Purpose | Method |
|------|---------|--------|
| **Sink** | Output destinations (file, HTTP, cloud) | `write()` |
| **Enricher** | Add context/metadata to events | `enrich()` |
| **Processor** | Transform serialized data | `process()` |
| **Redactor** | Mask sensitive data | `redact()` |
| **Filter** | Drop/pass events | `filter()` |

All plugin methods are **async**. Lifecycle methods (`start`, `stop`) are optional but recommended.

## Minimal Sink Plugin

Here's a complete sink plugin in ~20 lines:

```python
# my_sink.py
from typing import Any


class MySink:
    """Minimal sink that prints events."""

    name = "my_sink"  # Required: unique plugin name

    async def start(self) -> None:
        """Called when logger starts."""
        print("MySink started")

    async def stop(self) -> None:
        """Called when logger stops."""
        print("MySink stopped")

    async def write(self, entry: dict[str, Any]) -> None:
        """Write a log event."""
        print(f"LOG: {entry.get('message', entry)}")
```

### Using Your Plugin

```python
import fapilog
from my_sink import MySink

logger = fapilog.get_logger(sinks=[MySink()])
logger.info("Hello from my sink!")
```

## Registering via Entry Points

For distributable plugins, register via `pyproject.toml`:

```toml
[project]
name = "fapilog-my-sink"
version = "1.0.0"
dependencies = ["fapilog>=0.7.0"]

[project.entry-points."fapilog.sinks"]
my_sink = "my_sink:MySink"
```

### Entry Point Groups

| Plugin Type | Entry Point Group |
|-------------|-------------------|
| Sink | `fapilog.sinks` |
| Enricher | `fapilog.enrichers` |
| Processor | `fapilog.processors` |
| Redactor | `fapilog.redactors` |
| Filter | `fapilog.filters` |

## Plugin Validation Modes

Fapilog validates plugins at load time. Configure validation strictness:

```python
from fapilog import Settings

# Modes: "disabled", "warn", "strict"
settings = Settings(plugins={"validation_mode": "warn"})
```

| Mode | Invalid Plugin Behavior |
|------|------------------------|
| `disabled` | Load anyway, may fail at runtime |
| `warn` | Load with diagnostic warning |
| `strict` | Reject plugin, raise error |

### What Gets Validated

- Required `name` attribute exists and is a string
- Required methods exist and are async (`write`, `enrich`, etc.)
- Method signatures have correct parameters
- Optional lifecycle methods are async if present

## Plugin Protocols

### Sink Protocol

```python
from typing import Any, Protocol

class SinkProtocol(Protocol):
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def write(self, entry: dict[str, Any]) -> None: ...

    # Optional: fast path for pre-serialized data
    async def write_serialized(self, view: "SerializedView") -> None: ...

    # Optional: health check
    async def health_check(self) -> bool: ...
```

### Enricher Protocol

```python
from typing import Any, Protocol

class EnricherProtocol(Protocol):
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]: ...
```

### Redactor Protocol

```python
from typing import Any, Protocol

class RedactorProtocol(Protocol):
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def redact(self, event: dict[str, Any]) -> dict[str, Any]: ...
```

### Filter Protocol

```python
from typing import Any, Protocol

class FilterProtocol(Protocol):
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def filter(self, event: dict[str, Any]) -> dict[str, Any] | None: ...
```

Filters return the event to pass it through, or `None` to drop it.

### Processor Protocol

```python
from typing import Any, Protocol

class ProcessorProtocol(Protocol):
    name: str

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, data: bytes) -> bytes: ...
```

## Security Considerations

### For Plugin Authors

1. **Never log secrets** - Don't log API keys, tokens, or credentials
2. **Validate inputs** - Don't trust event data blindly
3. **Handle errors gracefully** - Don't crash the logger; use diagnostics
4. **Document dependencies** - Declare all requirements in `pyproject.toml`
5. **Pin fapilog version** - Use `fapilog>=X.Y.Z,<X+1.0.0`

```python
# Good: Error handling with diagnostics
async def write(self, entry: dict[str, Any]) -> None:
    try:
        await self._send(entry)
    except Exception as exc:
        from fapilog.core.diagnostics import warn
        warn("my-sink", "delivery failed", error=str(exc))
```

### For Plugin Users

1. **Use allowlist for external plugins**:
   ```python
   settings = Settings(plugins={
       "allow_external": True,
       "allowlist": ["trusted-plugin"],
   })
   ```

2. **Review plugin code** before installing third-party plugins

3. **Use strict validation** in production:
   ```python
   settings = Settings(plugins={"validation_mode": "strict"})
   ```

## Testing Your Plugin

Use fapilog's testing utilities:

```python
import pytest
from fapilog.testing import validate_sink, ValidationResult


def test_my_sink_protocol():
    """Validate your sink follows the protocol."""
    from my_sink import MySink

    sink = MySink()
    result: ValidationResult = validate_sink(sink)
    assert result.valid, f"Protocol violations: {result.errors}"


@pytest.mark.asyncio
async def test_my_sink_writes():
    """Test your sink receives events."""
    from my_sink import MySink

    sink = MySink()
    await sink.start()

    # Write a test event
    await sink.write({"message": "Test", "level": "INFO"})

    await sink.stop()
```

### Available Validators

```python
from fapilog.testing import (
    validate_sink,
    validate_enricher,
    validate_redactor,
    validate_filter,
    validate_processor,
    validate_plugin_lifecycle,  # Tests start/stop actually work
)
```

## Example: HTTP Webhook Sink

A more complete example with configuration, retries, and health checks:

```python
from typing import Any
import httpx


class WebhookSink:
    """Send logs to a webhook endpoint."""

    name = "webhook"

    def __init__(self, url: str, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._last_error: str | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def write(self, entry: dict[str, Any]) -> None:
        if not self._client:
            return

        try:
            await self._client.post(self.url, json=entry)
            self._last_error = None
        except httpx.HTTPError as e:
            self._last_error = str(e)
            # Log errors via diagnostics, don't raise
            from fapilog.core.diagnostics import warn
            warn("webhook-sink", "delivery failed", error=str(e))

    async def health_check(self) -> bool:
        return self._client is not None and self._last_error is None
```

## Example: Sampling Filter

A filter that randomly samples events:

```python
import random
from typing import Any


class SamplingFilter:
    """Probabilistic sampling filter."""

    name = "sampling"

    def __init__(self, rate: float = 1.0, seed: int | None = None):
        self._rate = rate
        if seed is not None:
            random.seed(seed)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def filter(self, event: dict[str, Any]) -> dict[str, Any] | None:
        if self._rate >= 1.0:
            return event
        if self._rate <= 0.0:
            return None
        return event if random.random() < self._rate else None

    async def health_check(self) -> bool:
        return True
```

## Plugin Metadata (Optional)

Add metadata for discovery and tooling:

```python
PLUGIN_METADATA = {
    "name": "my_sink",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "my_package.my_sink:MySink",
    "description": "Short description of what this plugin does.",
    "author": "Your Name",
    "compatibility": {"min_fapilog_version": "0.7.0"},
    "api_version": "1.0",
}
```

## Next Steps

- [Plugin Authoring Guide](authoring.md) - Detailed authoring guidance
- [Plugin Testing](testing.md) - Comprehensive testing patterns
- [Plugin Catalog](../plugin-guide.md) - Reference implementations
- [Error Handling](error-handling.md) - Graceful failure patterns
