# File Sink Not Rotating



## Symptoms
- Log file grows without rotation
- No compressed archives appear
- Disk usage climbs

## Causes
- Rotation thresholds not set
- Directory not writable
- Low traffic not triggering size threshold

## Fixes
```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760   # 10MB
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

Checklist:
- Ensure `/var/log/myapp` exists and is writable by the app user.
- Lower `MAX_BYTES` for demos/tests to force rotation quickly.
- Check `FAPILOG_FILE__MODE` is `json` (default) unless you intentionally changed it.
