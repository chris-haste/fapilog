# Envelope

The envelope is the structured log payload emitted by fapilog before serialization.

## Shape (v1.1 Schema)

Every log entry follows the v1.1 schema with semantic field groupings:

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "message": "User action",
  "logger": "app",
  "context": {
    "message_id": "550e8400-e29b-41d4-a716-446655440000",
    "correlation_id": "req-123",
    "request_id": "abc-456",
    "user_id": "user-789"
  },
  "diagnostics": {
    "service": "api",
    "env": "production",
    "host": "web-01",
    "pid": 12345
  },
  "data": {
    "action": "login",
    "duration_ms": 42
  }
}
```

### Core Fields

- `timestamp`: RFC3339 UTC string with millisecond precision (e.g., `"2024-01-15T10:30:00.123Z"`).
- `level`: one of DEBUG/INFO/WARNING/ERROR/CRITICAL.
- `message`: the message string passed to the logger method.
- `logger`: logger name (`get_logger(name=...)`).

### Semantic Groupings

- `context`: Request/trace identifiers. These identify WHO and WHAT request is being logged.
  - `message_id`: Unique UUID for each log entry. Always present, auto-generated.
  - `correlation_id`: Shared identifier across related log entries. Only present when explicitly set via context variable (e.g., `request_id_var`). Use this for request-level tracing.
  - `request_id`, `user_id`, `tenant_id`, `trace_id`, `span_id`: Optional trace context fields.
- `diagnostics`: Runtime/operational data (service, env, host, pid, exception). These identify WHERE the log originated and system state.
- `data`: User-provided structured data from extra kwargs and bound context (excluding context fields).

#### message_id vs correlation_id

- **message_id**: Uniquely identifies each individual log entry. A new UUID is generated for every log call. Use this when you need to reference a specific log line.
- **correlation_id**: Groups related log entries together. Only present when you explicitly set it via `request_id_var.set()` or when using FastAPI integration (which sets it automatically per request). Use this for tracing all logs from a single HTTP request or operation.

```python
from fapilog import get_logger
from fapilog.core.context import request_id_var

logger = get_logger()

# Without context - only message_id present
logger.info("standalone log")  # {"context": {"message_id": "aaa-111"}}

# With context - both message_id and correlation_id present
token = request_id_var.set("req-123")
logger.info("first")   # {"context": {"message_id": "bbb-222", "correlation_id": "req-123"}}
logger.info("second")  # {"context": {"message_id": "ccc-333", "correlation_id": "req-123"}}
request_id_var.reset(token)
```

## Exceptions

When `exc_info=True` or `exc` is provided, the envelope includes structured exception data in the `diagnostics.exception` field:

```json
{
  "diagnostics": {
    "exception": {
      "exception_type": "ValueError",
      "exception_message": "bad input",
      "stack": "... trimmed stack trace ...",
      "frames": [
        {"filename": "app.py", "lineno": 10, "function": "handle", "context_line": "..."}
      ]
    }
  }
}
```

Serialization respects `exceptions_max_frames` and `exceptions_max_stack_chars` from settings.

## Redaction and serialization

- Redactors (if enabled) run on the envelope after enrichment, before the sink.
- When `serialize_in_flush=True` and the sink supports `write_serialized`, the envelope is serialized once per entry in the flush path.

## Where to see it

- Default stdout sink emits JSON lines preserving the envelope structure. The `context`, `diagnostics`, and `data` fields remain nested.
- File/HTTP sinks receive the same envelope structure before serialization.
