# Glossary

**Adaptive Pipeline** — Self-tuning pipeline that monitors queue pressure and automatically adjusts workers, batch sizes, and queue capacity. Configured via `with_adaptive()` or the `adaptive` preset.

**Backpressure** — Behavior when the queue is full; fapilog can wait or drop based on `drop_on_full` and `backpressure_wait_ms`.

**Batch** — Group of log entries drained together, bounded by `batch_max_size` or `batch_timeout_seconds`.

**Circuit Breaker** — Fault isolation mechanism for sinks. After consecutive failures exceed a threshold, the circuit "opens" and the sink is temporarily bypassed. Events can be routed to a fallback sink while the circuit is open.

**Correlation ID** — Identifier (e.g., `request_id`) used to trace logs for a request/task.

**ContextVar** — Python mechanism used to store bound context per task/thread.

**Enricher** — Plugin that adds metadata to a log entry before redaction/sinks.

**Envelope** — Structured log payload (level, message, logger, timestamp, correlation_id, metadata).

**Escalation State Machine** — Component within the adaptive pipeline that manages pressure levels (NORMAL, ELEVATED, HIGH, CRITICAL) with hysteresis to prevent oscillation between states.

**Fallback Sink** — A secondary sink that receives events when a primary sink's circuit breaker opens. Configured via `with_circuit_breaker(fallback_sink="rotating_file")`.

**Pressure Monitor** — Component that samples queue fill ratio at regular intervals and feeds the escalation state machine. Configurable via `check_interval_seconds` and `cooldown_seconds`.

**Redactor** — Plugin that masks/removes sensitive data (field, regex, URL credentials).

**Runtime** — Context manager (`runtime` / `runtime_async`) that starts and drains the logger.

**Sink** — Output destination for logs (stdout, file, HTTP, etc.).
