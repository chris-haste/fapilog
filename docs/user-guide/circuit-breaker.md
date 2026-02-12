# Circuit Breaker

Circuit breakers isolate failing sinks to prevent cascade failures. When a sink fails repeatedly, the circuit opens and events are either skipped or routed to a fallback sink.

## Quick start

```python
from fapilog import LoggerBuilder

logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_circuit_breaker(enabled=True, failure_threshold=5)
    .build()
)
```

With fallback routing:

```python
logger = (
    LoggerBuilder()
    .with_preset("production")
    .add_file("logs/fallback", name="fallback_file")
    .with_circuit_breaker(
        enabled=True,
        failure_threshold=5,
        recovery_timeout="30s",
        fallback_sink="fallback_file",
    )
    .build()
)
```

Or use the `adaptive` preset which enables circuit breaker with rotating file fallback automatically:

```python
from fapilog import get_logger

logger = get_logger(preset="adaptive")
```

## How it works

```
CLOSED (healthy)
  │
  ├─ Sink write succeeds → stay CLOSED
  └─ Sink write fails → increment failure count
       └─ failures >= threshold → transition to OPEN
                                    │
OPEN (tripped)                      │
  │                                 │
  ├─ Events → fallback sink (if configured)
  ├─ Events → silently skipped (if no fallback)
  └─ After recovery_timeout → transition to HALF-OPEN
                                    │
HALF-OPEN (probing)                 │
  │                                 │
  ├─ Probe write succeeds → transition to CLOSED (reset failure count)
  └─ Probe write fails → transition to OPEN (restart timeout)
```

### States

| State | Behavior |
|-------|----------|
| **CLOSED** | All events sent to sink normally. Failure count tracked. |
| **OPEN** | Sink bypassed. Events route to fallback sink (or are skipped). |
| **HALF-OPEN** | Single probe event sent to sink. Success closes circuit, failure reopens it. |

## Configuration

### Builder API

```python
builder.with_circuit_breaker(
    enabled=True,              # Enable circuit breaker
    failure_threshold=5,       # Failures before opening (default: 5)
    recovery_timeout="30s",    # Time before probing (default: 30s)
    fallback_sink="rotating_file",  # Fallback when open (default: None)
)
```

### Settings

```python
from fapilog import Settings

settings = Settings(core={
    "sink_circuit_breaker_enabled": True,
    "sink_circuit_breaker_failure_threshold": 5,
    "sink_circuit_breaker_recovery_timeout_seconds": 30.0,
    "sink_circuit_breaker_fallback_sink": "rotating_file",
})
```

### Environment variables

```bash
FAPILOG_CORE__SINK_CIRCUIT_BREAKER_ENABLED=true
FAPILOG_CORE__SINK_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
FAPILOG_CORE__SINK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS=30
FAPILOG_CORE__SINK_CIRCUIT_BREAKER_FALLBACK_SINK=rotating_file
```

## Fallback routing

Without a fallback sink, events are silently dropped when the circuit is open. With a fallback sink, events are rerouted so no data is lost.

### Common fallback patterns

**File fallback for remote sinks:**
```python
logger = (
    LoggerBuilder()
    .with_preset("production")
    .add_http("https://logs.example.com/ingest")
    .with_circuit_breaker(
        enabled=True,
        fallback_sink="rotating_file",
    )
    .build()
)
# If HTTP sink fails → events go to rotating file
# When HTTP recovers → events resume to HTTP
```

**Stdout fallback for file sinks:**
```python
logger = (
    LoggerBuilder()
    .add_file("logs/app", name="primary_file")
    .add_stdout(name="console")
    .with_circuit_breaker(
        enabled=True,
        fallback_sink="console",
    )
    .build()
)
```

The `fallback_sink` value must match the name of a configured sink. If the name doesn't match any sink, events are skipped when the circuit opens.

## Per-sink circuit breakers

Cloud sinks (CloudWatch, Loki, PostgreSQL) have their own built-in circuit breakers that can be configured independently:

```python
builder.add_cloudwatch(
    "/myapp/prod",
    circuit_breaker=True,
    circuit_breaker_threshold=5,
)
```

The global `with_circuit_breaker()` setting applies to all sinks that don't have their own circuit breaker configuration.

## Adaptive pipeline integration

When the adaptive pipeline is enabled, open circuit breakers contribute additional pressure to the escalation state machine via `circuit_pressure_boost` (default: 0.20 per open circuit). This means the pipeline proactively scales up workers and batch sizes when sinks are failing, even before the queue physically fills up.

```python
logger = (
    LoggerBuilder()
    .with_adaptive(enabled=True, circuit_pressure_boost=0.30)
    .with_circuit_breaker(enabled=True, fallback_sink="rotating_file")
    .build()
)
```

See [Adaptive Pipeline](adaptive-pipeline.md) for details on pressure monitoring.

## Interaction with sink routing

Circuit breakers work with [level-based sink routing](sink-routing.md). When a routed sink's circuit opens, only events destined for that sink are rerouted to the fallback. Other sinks continue operating normally.

## Related

- [Adaptive Pipeline](adaptive-pipeline.md) — Automatic scaling and pressure monitoring
- [Sink Routing](sink-routing.md) — Level-based routing and fallback routing
- [Performance Tuning](performance-tuning.md) — Manual tuning options
- [Builder API](../api-reference/builder.md) — `with_circuit_breaker()` method reference
