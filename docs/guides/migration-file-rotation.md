---
orphan: true
---

# Migration Guide: Simplified Rotating File Setup

This guide shows how to migrate from the verbose `RotatingFileSinkConfig` pattern
to the new `fapilog.sinks.rotating_file()` convenience factory.

## Before (Verbose Configuration)

```python
from fapilog import get_logger
from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig
from pathlib import Path

config = RotatingFileSinkConfig(
    directory=Path("logs"),
    filename_prefix="app",
    max_bytes=10485760,
    max_files=7,
    compress_rotated=True,
)
sink = RotatingFileSink(config)
logger = get_logger(sinks=[sink])
```

## After (Convenience Factory)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

logger = get_logger(
    sinks=[rotating_file("logs/app.log", rotation="10 MB", retention=7, compression=True)]
)
```

## Notes

- The factory parses the path into directory + filename prefix automatically.
- Rotation values accept human-readable strings (e.g., `"10 MB"`).
- Behavior is additive; the old configuration path still works.

## Settings Alternative

```python
from fapilog import Settings, get_logger
from fapilog.core.settings import RotatingFileSettings

settings = Settings(
    sink_config=Settings.SinkConfig(
        rotating_file=RotatingFileSettings(
            directory="logs",
            filename_prefix="app",
            max_bytes="10 MB",
            max_files=7,
            compress_rotated=True,
        )
    )
)
logger = get_logger(settings=settings)
```
