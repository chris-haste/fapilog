# Core Concepts

Understand how fapilog works under the hood.

```{toctree}
:maxdepth: 2
:titlesonly:
:caption: Core Concepts

pipeline-architecture
envelope
context-binding
batching-backpressure
redaction
sinks
metrics
diagnostics-resilience
```

## Overview

fapilog is built around a few core concepts that make it fast, reliable, and developer-friendly:

- **Pipeline Architecture** - How messages flow through the system
- **Envelope** - The standardized log message format
- **Context Binding** - How context flows through your application
- **Batching & Backpressure** - Performance and resilience
- **Redaction** - Security and compliance
- **Sinks** - Where your logs go
- **Metrics** - Observability and monitoring
- **Diagnostics & Resilience** - Error handling and recovery

## Key Principles

### 1. Async-First Design

Everything in fapilog is async by default. This means:

- Logging never blocks your application
- High throughput with minimal resource usage
- Natural fit for modern Python applications

### 2. Zero-Copy Processing

Messages flow through the system without unnecessary copying:

- Memory-efficient processing
- Better performance under load
- Reduced garbage collection pressure

### 3. Structured by Default

All logs are structured data:

- Machine-readable JSON output
- Easy integration with log aggregation systems
- Consistent format across all outputs

### 4. Plugin Architecture

Extensible through plugins:

- Custom sinks, processors, and enrichers
- Easy integration with existing systems
- Community-driven ecosystem

## Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Application │───▶│   Context   │───▶│ Enrichers   │───▶│ Redactors   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                              │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│    Sinks    │◀───│    Queue    │◀───│ Processors  │◀───────┘
└─────────────┘    └─────────────┘    └─────────────┘
```

## What You'll Learn

1. **[Pipeline Architecture](pipeline-architecture.md)** - How messages flow through the system
2. **[Envelope](envelope.md)** - The standardized log message format
3. **[Context Binding](context-binding.md)** - How context flows through your application
4. **[Batching & Backpressure](batching-backpressure.md)** - Performance and resilience
5. **[Redaction](redaction.md)** - Security and compliance
6. **[Sinks](sinks.md)** - Where your logs go
7. **[Metrics](metrics.md)** - Observability and monitoring
8. **[Diagnostics & Resilience](diagnostics-resilience.md)** - Error handling and recovery

## Next Steps

After understanding the core concepts:

- **[User Guide](../user-guide/index.md)** - Learn practical usage patterns
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[Examples](../examples/index.md)** - Real-world usage patterns

---

_Understanding these core concepts will help you make the most of fapilog's capabilities._
