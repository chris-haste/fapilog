# Comparisons: fapilog vs stdlib, structlog, loguru

Why/when to pick fapilog, and what you give up or gain compared to common Python logging options.

## Quick matrix

| Capability | fapilog | stdlib logging | structlog | loguru |
| --- | --- | --- | --- | --- |
| Async/non-blocking pipeline | ✔️ Background worker, batching, backpressure | ❌ Synchronous | ❌ Synchronous (can wrap async sinks yourself) | ❌ Synchronous |
| Structured JSON out of the box | ✔️ Yes | ⚠️ Needs formatter/handler | ✔️ Yes | ⚠️ Needs serializer |
| Context binding (request/user) | ✔️ Built-in `bind`/`clear_context` with ContextVar inheritance | ⚠️ Needs Filters/adapters | ✔️ Yes (`bind_contextvars`) | ✔️ Yes (`contextualize`) |
| Redaction stage | ✔️ Field/regex/url redactors | ❌ | ❌ (plugins possible) | ❌ |
| Backpressure handling | ✔️ Bounded queue + drop/wait policy | ❌ | ❌ | ❌ |
| FastAPI/async DI helper | ✔️ `get_async_logger`, `runtime_async` | ❌ | ❌ (manual wiring) | ❌ |
| Metrics hooks | ✔️ Optional internal metrics | ❌ | ❌ | ❌ |
| Plugin model | ✔️ Enrichers/redactors/processors/sinks | ❌ | ⚠️ Extensible via processors/formatters | ⚠️ Sinks via handlers |
| Exception serialization | ✔️ Structured trace serialization | ⚠️ Basic `exc_info` text | ⚠️ Depends on renderer | ⚠️ Text traceback |

## When to use fapilog
- You need async/non-blocking logging under load or slow sinks.
- You want structured JSON with context binding and redaction guardrails.
- You need FastAPI/async support without hand-rolled adapters.
- You care about predictable backpressure (bounded queue + drop/wait).

## When stdlib/structlog/loguru may be enough
- Simple scripts/CLI where synchronous stdout/file is fine (stdlib/loguru).
- Lightweight structured logging without async pipeline; happy to wire sinks yourself (structlog).
- You prefer loguru’s ergonomic API and can tolerate sync I/O.

## Notes on alternatives
- **stdlib logging**: battle-tested, sync; structured output requires extra formatter/handler; no built-in context vars or backpressure.
- **structlog**: great for structured events and processors; still relies on stdlib handlers for I/O; async requires custom async-aware sinks; no queue/backpressure by default.
- **loguru**: friendly API and contextualize support; sync emission; JSON requires custom sink/serializer; no redaction/backpressure built in.

## Guidance
- **Services and FastAPI apps**: prefer fapilog async logger/runtime_async.
- **One-off scripts**: stdlib/loguru are fine; fapilog still works if you want JSON and redaction.
- **Existing structlog codebases**: keep structlog if its processors meet your needs; move to fapilog if you hit blocking sinks, want redaction/backpressure, or need async DI. 
