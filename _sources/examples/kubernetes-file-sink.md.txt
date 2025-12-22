# Kubernetes File Sink


Write logs to files inside containers with rotation.

```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

```python
from fapilog import get_logger

logger = get_logger()
logger.info("k8s log entry", pod="api-123", namespace="prod")
```

Notes:
- Mount a writable volume at `/var/log/myapp` to persist logs.
- Rotated files: `fapilog.log`, `fapilog.log.1`, `fapilog.log.2.gz`, etc.
- Use stdout sink for cluster-wide log collection if you aggregate stdout.
