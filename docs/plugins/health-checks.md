# Plugin Health Checks

fapilog plugins can expose an async `health_check()` method to report readiness. Base protocols return `True` by default, so existing plugins stay compatible.

## Checking health from code

```python
from fapilog import get_logger

logger = get_logger()
health = await logger.check_health()

if health.all_healthy:
    print("All plugins healthy")
else:
    for plugin in health.plugins:
        if not plugin.healthy:
            print(f"{plugin.plugin_type}:{plugin.name} unhealthy: {plugin.last_error}")
```

## Implementing in a custom plugin

```python
class MySink:
    async def write(self, entry: dict) -> None:
        ...

    async def health_check(self) -> bool:
        try:
            return await self._client.ping() == 200
        except Exception:
            return False
```

Built-ins now provide sensible checks:
- `StdoutJsonSink`: verifies stdout is writable
- `RotatingFileSink`: verifies directory exists/writable and file handle open
- `MemoryMappedPersistence`: ensures mmap/file is open
