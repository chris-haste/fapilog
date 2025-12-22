# Glossary

**Backpressure** — Behavior when the queue is full; fapilog can wait or drop based on `drop_on_full` and `backpressure_wait_ms`.

**Batch** — Group of log entries drained together, bounded by `batch_max_size` or `batch_timeout_seconds`.

**Correlation ID** — Identifier (e.g., `request_id`) used to trace logs for a request/task.

**Enricher** — Plugin that adds metadata to a log entry before redaction/sinks.

**Envelope** — Structured log payload (level, message, logger, timestamp, correlation_id, metadata).

**Redactor** — Plugin that masks/removes sensitive data (field, regex, URL credentials).

**Sink** — Output destination for logs (stdout, file, HTTP, etc.).

**Runtime** — Context manager (`runtime` / `runtime_async`) that starts and drains the logger.

**ContextVar** — Python mechanism used to store bound context per task/thread.
