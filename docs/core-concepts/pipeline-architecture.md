# Pipeline Architecture

How messages flow through fapilog's high-performance pipeline.

## Overview

fapilog uses a pipeline architecture that processes log messages through several stages, each optimized for specific tasks:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Application │───▶│   Context   │───▶│ Enrichers   │───▶│ Redactors   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                              │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│    Sinks    │◀───│    Queue    │◀───│ Processors  │◀───────┘
└─────────────┘    └─────────────┘    └─────────────┘
```

## Pipeline Stages

### 1. Application Layer

Your application code calls logging methods:

```python
from fapilog import get_logger

logger = get_logger()
logger.info("User action", user_id="123")
```

**What happens:**

- Message is created with current context
- Extra fields are merged with context
- Timestamp and level are added
- Message is queued for processing

### 2. Context Binding

Context is automatically attached to messages:

```python
# Context is automatically included
logger.info("Request processed", status_code=200)
```

**Context includes:**

- Request ID
- User ID
- Correlation ID
- Service name
- Environment

### 3. Enrichers

Enrichers add additional metadata to messages:

**Built-in enrichers:**

- **Runtime Info** - Python version, process ID, memory usage
- **Context Variables** - Request context, user context
- **Custom Enrichers** - Business-specific metadata

**Example:**

```python
# Message before enrichment
{"message": "User logged in", "user_id": "123"}

# Message after enrichment
{
  "message": "User logged in",
  "user_id": "123",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "process_id": 12345,
  "python_version": "3.11.0",
  "request_id": "req-abc123"
}
```

### 4. Redactors

Redactors remove or mask sensitive information:

**Built-in redactors:**

- **Field Mask** - Mask specific field names
- **Regex Mask** - Mask patterns (passwords, API keys)
- **URL Credentials** - Remove credentials from URLs

**Example:**

```python
# Before redaction
{
  "message": "User credentials",
  "username": "john_doe",
  "password": "secret123",
  "api_key": "sk-1234567890abcdef"
}

# After redaction
{
  "message": "User credentials",
  "username": "john_doe",
  "password": "***REDACTED***",
  "api_key": "***REDACTED***"
}
```

### 5. Processors

Processors transform and optimize messages:

**Built-in processors:**

- **Zero-Copy** - Efficient message handling
- **Batch Processing** - Group messages for efficiency
- **Compression** - Reduce storage requirements

### 6. Queue

The queue buffers messages between processing and output:

**Features:**

- **Lock-free design** - Maximum concurrency
- **Configurable capacity** - Prevent memory issues
- **Backpressure handling** - Drop or wait under load
- **Zero-copy operations** - Minimal memory allocation

### 7. Sinks

Sinks are the final destination for messages:

**Built-in sinks:**

- **Stdout JSON** - Development and containers
- **Rotating File** - Production and compliance
- **HTTP Client** - Remote systems and APIs
- **MMAP Persistence** - High-performance local storage

## Performance Characteristics

### Async Processing

- **Non-blocking** - Logging never blocks your application
- **Concurrent** - Multiple messages processed simultaneously
- **Efficient** - Minimal CPU and memory overhead

### Zero-Copy Operations

- **Memory efficient** - Messages flow without copying
- **Reduced GC pressure** - Fewer temporary objects
- **Better performance** - Especially under high load

### Batching

- **Configurable batch sizes** - Balance latency vs throughput
- **Automatic batching** - Based on volume and time
- **Batch compression** - Reduce storage and network usage

## Guarantees

### 1. Async Operations

Logging calls enqueue work without blocking on sinks:

```python
# Sync
logger.info("Processing started")

# Async
await async_logger.info("Processing started")
```

### 2. Bounded Memory

Memory usage is bounded and configurable:

```python
# Set maximum queue size
export FAPILOG_CORE__MAX_QUEUE_SIZE=8192

# Set maximum batch size
export FAPILOG_CORE__BATCH_MAX_SIZE=100
```

### 3. Backpressure Handling

System handles overload gracefully:

```python
# Configure backpressure behavior
export FAPILOG_CORE__DROP_ON_FULL=true
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=100
```

### 4. Deduplication

Automatic deduplication of similar messages:

```python
# Configure deduplication window
export FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS=60
```

## Configuration

### Pipeline Configuration

```python
from fapilog import Settings

settings = Settings(
    # Queue configuration
    core__max_queue_size=16384,
    core__batch_max_size=200,
    core__drop_on_full=False,
    core__backpressure_wait_ms=100,
    core__error_dedupe_window_seconds=60,
    # Optional HTTP sink
    http__endpoint="https://logs.example.com/ingest",
)
```

### Environment Variables

```bash
# Pipeline performance
export FAPILOG_CORE__MAX_QUEUE_SIZE=16384
export FAPILOG_CORE__BATCH_MAX_SIZE=200

# Deduplication
export FAPILOG_CORE__ERROR_DEDUPE_WINDOW_SECONDS=60

# Backpressure
export FAPILOG_CORE__DROP_ON_FULL=false
export FAPILOG_CORE__BACKPRESSURE_WAIT_MS=100
```

## Monitoring

### Pipeline Metrics

Monitor pipeline performance:

```python
from fapilog import get_pipeline_metrics

metrics = await get_pipeline_metrics()
print(f"Queue utilization: {metrics.queue_utilization}%")
print(f"Processing rate: {metrics.messages_per_second}/s")
print(f"Batch efficiency: {metrics.batch_efficiency}%")
```

### Health Checks

Check pipeline health:

```python
from fapilog import get_pipeline_health

health = await get_pipeline_health()
print(f"Pipeline status: {health.status}")
print(f"Active workers: {health.active_workers}")
print(f"Queue health: {health.queue_health}")
```

## Next Steps

- **[Envelope](envelope.md)** - Understand the message format
- **[Context Binding](context-binding.md)** - Learn about context management
- **[Batching & Backpressure](batching-backpressure.md)** - Performance optimization

---

_The pipeline architecture ensures high performance and reliability while maintaining simplicity for developers._
