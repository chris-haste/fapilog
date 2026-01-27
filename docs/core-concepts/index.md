# Core Concepts

Understand what fapilog does for you and how it keeps your app fast and reliable.

```{toctree}
:maxdepth: 2
:titlesonly:
:caption: Core Concepts

pipeline-architecture
envelope
context-binding
batching-backpressure
sinks
metrics
diagnostics-resilience
```

## Overview

fapilog is built around a few core concepts that make it fast, reliable, and developer-friendly:

- **Pipeline Architecture** - Why your log calls return immediately while I/O happens in the background
- **Envelope** - How logs are structured so they're easy to query and alert on
- **Context Binding** - How to add request_id once and see it in every log automatically
- **Batching & Backpressure** - What happens during traffic spikes (you choose: drop or wait)
- **Redaction** - How secrets stay out of your logs without extra code
- **Sinks** - Send logs anywhere—stdout, files, CloudWatch, databases
- **Metrics** - See queue depth and dropped logs before problems hit production
- **Diagnostics & Resilience** - How fapilog recovers from errors without crashing your app

## Key Principles

Fapilog isn't a thin wrapper over existing logging libraries—it's an async-first logging pipeline designed to keep your app responsive under slow or bursty log sinks, with backpressure policies, redaction, and first-class FastAPI integration built in.

### 1. Your App Stays Fast

Log calls return immediately—they never wait for disk or network I/O:

- A slow CloudWatch API won't slow down your API responses
- Traffic spikes don't cause thread stalls
- Works the same whether you use `get_logger()` or `get_async_logger()`

### 2. Memory-Efficient by Design

Fapilog processes logs without creating unnecessary copies:

- Your app uses less memory per log entry
- High-volume logging won't trigger GC pauses that hurt response times
- You can log more without budgeting extra RAM

### 3. Logs You Can Actually Query

All logs are structured JSON by default:

- Filter by request_id, user_id, or any field in your log aggregator
- Build dashboards and alerts without parsing text
- Same format everywhere—stdout, files, cloud sinks

### 4. Extend Without Forking

Add functionality through plugins:

- Send logs to any destination with custom sinks
- Add context automatically with enrichers
- Mask sensitive data with redactors

## Architecture Overview

Your log call returns immediately. Everything after the queue happens in background workers:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Application │───▶│   Context   │───▶│ Enrichers   │───▶│ Redactors   │
│             │    │ (request_id │    │ (add host,  │    │ (mask       │
│ log.info()  │    │  auto-added)│    │  version)   │    │  secrets)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      ↑                                                        │
   Returns                                                     ↓
  immediately    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
                 │    Sinks    │◀───│    Queue    │◀───│ Processors  │
                 │ (CloudWatch,│    │ (buffer for │    │ (format,    │
                 │  stdout...) │    │  slow sinks)│    │  compress)  │
                 └─────────────┘    └─────────────┘    └─────────────┘
```

## What You'll Learn

1. **[Pipeline Architecture](pipeline-architecture.md)** - Why log calls never block your app
2. **[Envelope](envelope.md)** - How logs are structured for easy querying
3. **[Context Binding](context-binding.md)** - Add request_id once, see it everywhere
4. **[Batching & Backpressure](batching-backpressure.md)** - Control what happens during traffic spikes
5. **[Redaction](../redaction/index.md)** - Keep secrets out of logs automatically
6. **[Sinks](sinks.md)** - Send logs to stdout, files, CloudWatch, databases
7. **[Metrics](metrics.md)** - Monitor queue health before problems hit
8. **[Diagnostics & Resilience](diagnostics-resilience.md)** - How fapilog handles errors gracefully

## Next Steps

After understanding the core concepts:

- **[User Guide](../user-guide/index.md)** - Learn practical usage patterns
- **[API Reference](../api-reference/index.md)** - Complete API documentation
- **[Examples](../examples/index.md)** - Real-world usage patterns

---

_Understanding these core concepts will help you make the most of fapilog's capabilities._
