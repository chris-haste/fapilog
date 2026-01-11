# Sinks



Destinations for log output.

## Built-in sinks

- **Stdout pretty**: human-readable console output (TTY).
- **Stdout JSON**: structured JSON lines to stdout.
- **Rotating file**: size/time-based rotation with optional compression.
- **HTTP client**: POST log entries to an HTTP endpoint.
- **MMAP persistence**: experimental local persistence sink.

## Selection logic

- If `FAPILOG_HTTP__ENDPOINT` is set, the HTTP sink is used.
- Else if `FAPILOG_FILE__DIRECTORY` is set, the rotating file sink is used.
- Otherwise, stdout auto is used (pretty in TTY, JSON when piped).

## Fast-path serialization

When `core.serialize_in_flush=True` and the sink supports `write_serialized`, envelopes are serialized once per batch entry in the flush path to reduce work in sinks.

## Configuring sinks

Rotating file (env):

```bash
export FAPILOG_FILE__DIRECTORY=/var/log/myapp
export FAPILOG_FILE__MAX_BYTES=10485760
export FAPILOG_FILE__MAX_FILES=5
export FAPILOG_FILE__COMPRESS_ROTATED=true
```

HTTP sink (env):

```bash
export FAPILOG_HTTP__ENDPOINT=https://logs.example.com/ingest
export FAPILOG_HTTP__TIMEOUT_SECONDS=5
export FAPILOG_HTTP__RETRY_MAX_ATTEMPTS=3
```

## Routing by level

Enable `sink_routing` to send different levels to different sinks:

```bash
export FAPILOG_SINK_ROUTING__ENABLED=true
export FAPILOG_SINK_ROUTING__RULES='[
  {"levels": ["ERROR", "CRITICAL"], "sinks": ["postgres"]},
  {"levels": ["DEBUG", "INFO"], "sinks": ["stdout_json"]}
]'
export FAPILOG_SINK_ROUTING__FALLBACK_SINKS='["rotating_file"]'
```

When disabled (default), all events fan out to all configured sinks.
