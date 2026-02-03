# Features

A comprehensive overview of what fapilog offers.

## Core Logging

| Feature | Why It Matters |
|---------|----------------|
| **Sync and async loggers** | Use `get_logger()` in sync code or `get_async_logger()` in async code—both use the same non-blocking pipeline |
| **Context managers** | `runtime()` and `runtime_async()` automatically drain logs on exit, preventing lost messages |
| **Custom log levels** | Register domain-specific levels like `AUDIT` or `TRACE` with `register_level()` |
| **Logger caching** | Loggers are cached by name by default, so repeated `get_logger("app")` calls return the same instance |

## Configuration

| Feature | Why It Matters |
|---------|----------------|
| **Presets** | Start with `dev`, `production`, `serverless`, or `hardened`—sensible defaults for common scenarios |
| **Environment detection** | Automatically detects Lambda, Kubernetes, Docker, and CI environments to apply appropriate settings |
| **Builder API** | Fluent `LoggerBuilder` for programmatic configuration without YAML or config files |
| **Pydantic settings** | Configure via environment variables with type validation |

## Performance

| Feature | Why It Matters |
|---------|----------------|
| **Non-blocking writes** | Log calls enqueue and return immediately—I/O happens in background workers |
| **Lock-free queue** | `NonBlockingRingQueue` minimizes contention in high-throughput scenarios |
| **Backpressure handling** | Choose between dropping logs (protect latency) or blocking (protect durability) when the queue fills |
| **Batching** | Logs are batched before writing to reduce I/O overhead |
| **Zero-copy processing** | `ZeroCopyProcessor` avoids unnecessary memory copies during serialization |

## Structured Output

| Feature | Why It Matters |
|---------|----------------|
| **JSON Lines format** | Machine-parseable output for log aggregators and analysis tools |
| **Pretty-print mode** | Human-readable output for local development (auto-detected when running in a terminal) |
| **Structured envelope** | Every log includes `timestamp`, `level`, `message`, `context`, `diagnostics`, and `data` fields |
| **Origin tracking** | Logs are tagged as `native`, `stdlib`, or `third_party` so you know where they came from |

## Context and Correlation

| Feature | Why It Matters |
|---------|----------------|
| **Context binding** | Attach fields to a logger with `logger.bind(user_id="123")` and they appear on every subsequent log |
| **Context variables** | `bind_context()` sets values that propagate across async boundaries |
| **Request ID tracking** | Built-in `request_id`, `correlation_id`, `trace_id`, and `span_id` fields for distributed tracing |
| **Async context preservation** | `create_task_with_context()` and `@preserve_context` keep context intact across task boundaries |

## Redaction and Compliance

| Feature | Why It Matters |
|---------|----------------|
| **Field masking** | Redact specific fields like `password` or `data.credit_card` by path |
| **Regex patterns** | Match and redact patterns like SSNs, credit card numbers, or API keys |
| **URL credential scrubbing** | Automatically redact credentials embedded in database URLs or API endpoints |
| **Compliance presets** | Built-in presets for `GDPR_PII`, `HIPAA_PHI`, `PCI_DSS`, `CCPA_PII`, and `SOC2` |
| **Fail modes** | Choose `warn` (log and continue) or `closed` (drop the log) when redaction fails |

## Sinks

| Feature | Why It Matters |
|---------|----------------|
| **Multiple destinations** | Write to stdout, files, HTTP endpoints, or cloud services simultaneously |
| **Rotating files** | `RotatingFileSink` handles size-based rotation and optional compression |
| **Cloud-native sinks** | Direct integration with CloudWatch, Loki, and PostgreSQL |
| **Sink routing** | Route logs by level—send errors to a database while info goes to stdout |
| **Circuit breakers** | Failing sinks are temporarily disabled to prevent cascade failures |
| **Fallback sinks** | Specify a fallback destination when the primary sink trips its circuit breaker |

## Filtering

| Feature | Why It Matters |
|---------|----------------|
| **Level filtering** | Drop logs below a threshold |
| **Sampling** | Randomly sample a percentage of logs to reduce volume |
| **Rate limiting** | Limit logs per key (e.g., per endpoint or per user) to prevent floods |
| **Adaptive sampling** | Automatically increase sampling during error spikes to capture more context |
| **Trace sampling** | Sample entire request traces together so you don't get incomplete pictures |

## Enrichment

| Feature | Why It Matters |
|---------|----------------|
| **Runtime info** | Automatically add PID, hostname, and Python version to every log |
| **Kubernetes metadata** | Add pod name, namespace, and labels when running in K8s |
| **Custom enrichers** | Implement the enricher protocol to add your own fields |

## Exception Handling

| Feature | Why It Matters |
|---------|----------------|
| **Full traceback capture** | Exceptions include complete stack traces with configurable depth |
| **Exception chaining** | Chained exceptions (`raise ... from ...`) are preserved |
| **Unhandled exception capture** | Optionally log uncaught exceptions before they crash the process |
| **Stack truncation** | Limit stack trace size to prevent log bloat |

## FastAPI Integration

| Feature | Why It Matters |
|---------|----------------|
| **Builder pattern** | `FastAPIBuilder().with_preset("fastapi").build()` configures middleware and lifespan |
| **Request/response logging** | Automatic logging of incoming requests and outgoing responses |
| **Timing** | Request duration is captured and logged |
| **Context injection** | Use FastAPI dependencies to inject loggers with request context |

## Resilience

| Feature | Why It Matters |
|---------|----------------|
| **Plugin isolation** | A failing enricher or processor doesn't crash your logging—errors are captured in diagnostics |
| **Graceful shutdown** | `install_shutdown_handlers()` ensures logs are flushed on SIGTERM/SIGINT |
| **Drain operations** | Explicitly drain pending logs before shutdown |
| **Health checks** | Per-plugin health checks for monitoring |

## Observability

| Feature | Why It Matters |
|---------|----------------|
| **Prometheus metrics** | Export logging metrics (queue depth, batch sizes, errors) for monitoring |
| **Per-plugin timing** | Track how long each enricher, processor, and sink takes |
| **Diagnostics system** | Internal issues are logged with rate limiting to avoid log storms |

## Extensibility

| Feature | Why It Matters |
|---------|----------------|
| **Plugin architecture** | Add custom enrichers, redactors, filters, processors, and sinks |
| **Entry point discovery** | Plugins can be installed as packages and auto-discovered |
| **Allowlist/denylist** | Control which plugins are loaded in production |
| **Stdlib bridge** | Route Python's standard `logging` module through fapilog |

## Learn More

- **[Why Fapilog?](why-fapilog.md)** - When to choose fapilog over alternatives
- **[Getting Started](getting-started/index.md)** - Install and start logging
- **[Core Concepts](core-concepts/index.md)** - Understand the architecture
- **[Cookbook](cookbook/index.md)** - Recipes for common problems
