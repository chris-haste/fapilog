# Rotating File Sink


Write logs to disk with size/time rotation.

## Enable via environment

```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760  # 10MB
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
# Optional time-based rotation (seconds)
export FAPILOG_FILE__INTERVAL_SECONDS=0
```

## Usage

```python
from fapilog import get_logger

logger = get_logger()
logger.info("to file", event="startup")
```

## What to expect

- Files named `fapilog.log`, `fapilog.log.1`, `fapilog.log.2.gz`, etc.
- Rotation by size (`max_bytes`); optional max file count and compression.

## Tips

- Ensure the directory exists and is writable by the app user.
- Set `FAPILOG_FILE__MODE` to `json` (default) for structured output.
- For containers, ensure volume mounts persist `/var/log/myapp`.
