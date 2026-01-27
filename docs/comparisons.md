# Python Logging Library Comparison

This page compares five Python logging libraries that developers most commonly evaluate:

- **fapilog** - Async-first logging with backpressure and built-in redaction
- **structlog** - Structured logging with processor pipelines (since 2013)
- **loguru** - Developer-friendly logging with beautiful defaults (21k GitHub stars)
- **stdlib logging** - Python's built-in logging module
- **OpenTelemetry** - Unified observability for logs, traces, and metrics

*Last updated: January 2026*

## When to Use Each

### fapilog

**Best for:**

- **Microservices and distributed systems** - Request ID tracking, async-first, multiple cloud sinks
- **FastAPI/async applications** - Built-in middleware, non-blocking logging
- **High-throughput services** - Backpressure handling, won't impact request latency
- **Production services at scale** - Reliability features (circuit breaker, sink routing, batching)
- **Applications with compliance needs** - Built-in PII redaction (field/regex/URL)
- **Cloud-native applications** - Native CloudWatch, Loki, PostgreSQL sinks
- **Services with variable load patterns** - Backpressure policies handle bursts gracefully

**Example use case:** An API service handling 10k+ requests/second where a slow logging backend shouldn't cause request timeouts.

### structlog

**Best for:**

- Projects already using stdlib logging that want structured output without changing handlers
- Teams wanting the largest processor ecosystem and community extensions
- Multi-framework consistency (same patterns across Django, Flask, CLI)
- Libraries that need to work with whatever logger the consumer provides

**Example use case:** A Django monolith with existing stdlib logging infrastructure that needs structured JSON output without replacing handlers or changing deployment.

### loguru

**Best for:**

- Rapid prototyping and development
- Small to medium applications
- Projects prioritizing developer experience
- Scripts and CLI tools
- Teams wanting beautiful console output with zero setup

**Example use case:** A CLI tool or internal service where simplicity matters more than async performance.

### stdlib logging

**Best for:**

- Projects that cannot add dependencies
- Maximum compatibility requirements
- Educational purposes
- Simple applications with fast local sinks

**Example use case:** A library that must work everywhere without pulling in dependencies.

### OpenTelemetry

**Best for:**

- Comprehensive observability strategy (logs + traces + metrics unified)
- Microservices needing trace correlation across services
- Enterprise environments with existing OTel infrastructure
- Vendor-neutral telemetry requirements

**Example use case:** A distributed system where correlating logs with traces across 50+ services is essential for debugging.

## Feature Comparison

### Core Architecture

| Feature | fapilog | structlog | loguru | stdlib | OpenTelemetry |
|---------|---------|-----------|--------|--------|---------------|
| **Architecture** | Async pipeline | Processor chain | Single logger | Handler chain | Exporter bridge |
| **Concurrency model** | Background worker | Synchronous | Synchronous | Synchronous | Varies by exporter |
| **Queue type** | Bounded async | None | None | Optional QueueHandler | Batch exporter |
| **I/O model** | Non-blocking | Blocking | Blocking | Blocking | Depends on backend |
| **Backpressure policies** | ✅ drop/wait | ❌ | ❌ | ❌ | ❌ |

### Async Support

| Feature | fapilog | structlog | loguru | stdlib | OpenTelemetry |
|---------|---------|-----------|--------|--------|---------------|
| **Async-first design** | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **Non-blocking I/O** | ✅ Always | ❌ Manual | ❌ No | ⚠️ QueueHandler | ⚠️ Batch only |
| **Background worker** | ✅ Built-in | ❌ Manual | ❌ No | ⚠️ QueueListener | ⚠️ Collector |
| **Async API** | ✅ Native | ⚠️ Wrapper | ⚠️ Async sinks | ❌ No | ❌ No |

**Legend:** ✅ Full support | ⚠️ Partial/manual | ❌ Not available

### Structured Logging & Context

| Feature | fapilog | structlog | loguru | stdlib | OpenTelemetry |
|---------|---------|-----------|--------|--------|---------------|
| **JSON output** | ✅ Built-in | ✅ Built-in | ⚠️ Serializer | ⚠️ Formatter | ✅ OTLP |
| **Context binding** | ✅ `bind()` | ✅ `bind()` | ✅ `contextualize` | ⚠️ Filters | ✅ Resource attrs |
| **Request correlation** | ✅ Built-in | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual | ✅ Trace context |
| **Exception serialization** | ✅ Structured | ⚠️ Processor | ⚠️ Text | ⚠️ Text | ✅ Structured |

### Security & Redaction

| Feature | fapilog | structlog | loguru | stdlib | OpenTelemetry |
|---------|---------|-----------|--------|--------|---------------|
| **Built-in redaction** | ✅ Field/regex/URL | ❌ Custom processor | ❌ No | ❌ No | ❌ No |
| **PII masking** | ✅ Default patterns | ⚠️ Manual | ❌ Manual | ❌ Manual | ❌ Manual |
| **Credential stripping** | ✅ URL passwords | ❌ Manual | ❌ No | ❌ No | ❌ No |

### Framework Integration

| Feature | fapilog | structlog | loguru | stdlib | OpenTelemetry |
|---------|---------|-----------|--------|--------|---------------|
| **FastAPI** | ✅ Middleware | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual | ✅ Auto-instrument |
| **Django** | ⚠️ SyncFacade | ⚠️ Manual | ⚠️ Manual | ✅ Native | ✅ Auto-instrument |
| **Flask** | ⚠️ Manual | ⚠️ Manual | ⚠️ Manual | ✅ Native | ✅ Auto-instrument |

### Performance Characteristics

| Aspect | fapilog | structlog | loguru | stdlib | OpenTelemetry |
|--------|---------|-----------|--------|--------|---------------|
| **Throughput** | High (batching) | Medium | Medium | High | Medium |
| **Latency per call** | Very low (async) | Low | Low | Very low | Medium |
| **Memory** | Bounded queue | Low | Low | Low/unbounded | Medium |
| **Under slow sinks** | ✅ Non-blocking | ❌ Blocks | ❌ Blocks | ⚠️ QueueHandler | ⚠️ Collector |

## Architecture Comparison

### fapilog

```
Log Event → Enrichment → Redaction → Processing → Queue → Background Worker → Sinks
```

- **Log calls never block on I/O** - both sync and async APIs write to background workers
- Bounded queue with configurable overflow policies (slow sinks won't stall your app)
- Batching reduces I/O operations

### structlog

```
Log Event → Processor Chain → Renderer → Wrapped Logger (stdlib/other)
```

- Synchronous processor pipeline
- Wraps existing loggers for output
- Async requires manual QueueHandler setup

### loguru

```
Log Event → Format → Sinks (handlers)
```

- Single global logger instance
- Sinks can be async functions but emit is synchronous
- Thread-safe with locks

### stdlib + QueueHandler

```
Log Event → QueueHandler → Queue → QueueListener (thread) → Handlers
```

- Thread-based async pattern
- Requires manual setup and lifecycle management
- No backpressure (queue grows unbounded)

### OpenTelemetry

```
Log Event → stdlib bridge → OTLP Exporter → OTel Collector → Backend
```

- Bridges existing logging to OTLP format
- Requires external collector infrastructure
- Focused on observability correlation, not logging features

## Migration Considerations

### From stdlib to fapilog

**Effort:** Low-Medium

```python
# Before (stdlib)
import logging
logger = logging.getLogger(__name__)
logger.info("User logged in", extra={"user_id": "123"})

# After (fapilog)
from fapilog import get_logger
logger = get_logger()
logger.info("User logged in", user_id="123")
```

### From loguru to fapilog

**Effort:** Medium

```python
# Before (loguru)
from loguru import logger
logger.info("User logged in", user_id="123")

# After (fapilog)
from fapilog import get_logger
logger = get_logger()
logger.info("User logged in", user_id="123")
```

Key differences:
- fapilog uses factory pattern vs loguru's single global logger
- Context binding syntax is similar (`bind()`)
- Async API requires `await` with fapilog

### From structlog to fapilog

**Effort:** Medium-High

```python
# Before (structlog)
import structlog
logger = structlog.get_logger()
logger.info("user_logged_in", user_id="123")

# After (fapilog)
from fapilog import get_logger
logger = get_logger()
logger.info("User logged in", user_id="123")
```

Key differences:
- Different processor model (fapilog has separate enrichers, redactors, processors)
- Built-in async support vs manual setup
- Backpressure handling included

## Trade-offs Summary

| Library | Strengths | Limitations |
|---------|-----------|-------------|
| **fapilog** | Async-first, backpressure, redaction, FastAPI | Newer (2024), smaller community |
| **structlog** | Mature (2013), processor ecosystem, stdlib compat | No async pipeline, no backpressure |
| **loguru** | Best DX, beautiful defaults, zero config | Sync only, no redaction, performance at scale |
| **stdlib** | Zero deps, universal, battle-tested | Verbose, no structure, no async |
| **OpenTelemetry** | Industry standard, trace correlation | Complex setup, not logging-focused |

## Learn More

- **[Why Fapilog?](why-fapilog.md)** - Quick overview of fapilog's differentiators
- **[Getting Started](getting-started/index.md)** - Install and start logging
- **[Benchmarks](user-guide/benchmarks.md)** - Performance methodology and results
- **[Architecture](core-concepts/pipeline-architecture.md)** - How fapilog's async pipeline works
