# Sinks



Output plugins that deliver serialized log entries to destinations.

## Contract

Implement `BaseSink` methods:

- `async start(self) -> None`: optional initialization.
- `async write(self, entry: dict) -> None`: required; receives enriched/redacted envelope.
- `async write_serialized(self, view) -> None`: optional fast-path when `serialize_in_flush=True`.
- `async stop(self) -> None`: optional teardown.

Errors should be contained; do not raise into the pipeline.

## Built-in sinks

- **stdout-json**: default sink, JSON lines to stdout.
- **rotating-file**: size/time-based rotation with optional compression.
- **http_client**: POST log entries to an HTTP endpoint.
- **mmap_persistence**: experimental local persistence.

## Configuration (env)

Rotating file:
```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

HTTP sink:
```bash
export FAPILOG_HTTP__ENDPOINT=https://logs.example.com/ingest
export FAPILOG_HTTP__TIMEOUT_SECONDS=5
export FAPILOG_HTTP__RETRY_MAX_ATTEMPTS=3
```
