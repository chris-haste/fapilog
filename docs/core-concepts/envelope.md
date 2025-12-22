# Envelope



The envelope is the structured log payload emitted by fapilog before serialization.

## Shape

Every log entry is a mapping with core fields plus metadata:

```json
{
  "level": "INFO",
  "message": "User action",
  "logger": "app",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "correlation_id": "req-123",
  "metadata": {
    "user_id": "abc",
    "action": "login"
  }
}
```

- `level`: one of DEBUG/INFO/WARNING/ERROR.
- `message`: the message string passed to the logger method.
- `logger`: logger name (`get_logger(name=...)`).
- `timestamp`: ISO 8601 with milliseconds in UTC.
- `correlation_id`: auto-generated UUID or value derived from context vars.
- `metadata`: merged bound context + per-call kwargs + enrichment + serialized exceptions.

## Exceptions

When `exc_info=True` or `exc` is provided, the envelope includes structured exception data:

```json
{
  "exception_type": "ValueError",
  "exception_message": "bad input",
  "stack": "... trimmed stack trace ...",
  "frames": [
    {"filename": "app.py", "lineno": 10, "function": "handle", "context_line": "..."}
  ]
}
```

Serialization respects `exceptions_max_frames` and `exceptions_max_stack_chars` from settings.

## Redaction and serialization

- Redactors (if enabled) run on the envelope after enrichment, before the sink.
- When `serialize_in_flush=True` and the sink supports `write_serialized`, the envelope is serialized once per entry in the flush path.

## Where to see it

- Default stdout sink emits JSON lines with these fields flattened (metadata keys merged at top level).
- File/HTTP sinks receive the same envelope structure before serialization.
