# Rotating File Sink


Write logs to disk with size/time rotation.

## Quick Start (Convenience Function)

```python
from fapilog import get_logger
from fapilog.sinks import rotating_file

# Simple file logging
logger = get_logger(sinks=[rotating_file("logs/app.log")])

# With rotation and retention
logger = get_logger(
    sinks=[
        rotating_file(
            "logs/app.log",
            rotation="10 MB",
            retention=7,
            compression=True,
        )
    ]
)
```

## Enable via environment

```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES="10 MB"
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
# Optional time-based rotation
export FAPILOG_FILE__INTERVAL_SECONDS="daily"
```

`"daily"`/`"hourly"`/`"weekly"` are fixed intervals (e.g., 24 hours), not wall-clock boundaries.

## Programmatic settings

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
logger.info("configured via Settings")
```

## Usage

```python
from fapilog import get_logger

logger = get_logger()
logger.info("to file", event="startup")
```

## Direct Class Usage

For full control, instantiate the sink class directly:

```python
from pathlib import Path
from fapilog.plugins.sinks.rotating_file import RotatingFileSink, RotatingFileSinkConfig

config = RotatingFileSinkConfig(
    directory=Path("./logs"),
    filename_prefix="app",
    max_bytes=10_000_000,  # 10 MB
    max_files=5,
    compress_rotated=True,
)
sink = RotatingFileSink(config)
```

Config fields: `directory`, `filename_prefix`, `mode`, `max_bytes`, `interval_seconds`, `max_files`, `max_total_bytes`, `compress_rotated`, `strict_envelope_mode`.

## Migration

See `docs/guides/migration-file-rotation.md` for a before/after conversion from
`RotatingFileSinkConfig` to the `rotating_file()` convenience factory.

## What to expect

- Files named like `fapilog-20250111-120000.jsonl` (or `.log` in text mode).
- Rotation by size (`max_bytes`) or interval; optional retention and compression.

## Tips

- Ensure the directory exists and is writable by the app user.
- Set `FAPILOG_FILE__MODE` to `json` (default) for structured output.
- For containers, ensure volume mounts persist `/var/log/myapp`.
