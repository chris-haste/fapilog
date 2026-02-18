# Configuration Presets

Presets provide pre-configured settings for common deployment scenarios. Choose a preset that matches your use case to get sensible defaults without manual configuration.

## Quick Reference

| Preset | Use Case | Drops Logs? | File Output | Redaction |
|--------|----------|-------------|-------------|-----------|
| `dev` | Local development | No | No | No |
| `production` | Production with adaptive scaling | Backpressure retry | Fallback only | Yes (CREDENTIALS) |
| `serverless` | Lambda/Cloud Run | If needed | No | Yes (CREDENTIALS) |
| `hardened` | Compliance (HIPAA/PCI) | Never | Yes | Yes (HIPAA + PCI + CREDENTIALS) |
| `minimal` | Maximum control | Default | Default | No |

> **Note:** The `adaptive` preset name is deprecated. Use `production` instead — it now includes all adaptive features (dynamic worker scaling, filter tightening, circuit breaker).

## Choosing a Preset

```
Is this for local development?
├─ Yes → dev
└─ No → Is this for serverless (Lambda/Cloud Run)?
         ├─ Yes → serverless
         └─ No → Do you need HIPAA/PCI compliance?
                  ├─ Yes → hardened
                  └─ No → Is this a production deployment?
                           ├─ Yes → production (adaptive scaling, backpressure, circuit breaker)
                           └─ No → minimal (maximum control)
```

## Usage

```python
from fapilog import get_logger, LoggerBuilder

# Simple usage
logger = get_logger(preset="production")

# Builder API
logger = (
    LoggerBuilder()
    .with_preset("production")
    .build()
)

# Customize a preset
logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_redaction(preset="HIPAA_PHI")  # Add HIPAA compliance
    .with_level("DEBUG")                  # Override log level
    .build()
)
```

## Performance Settings

| Preset | Workers | Batch Size | Queue Size | Enrichers |
|--------|---------|------------|------------|-----------|
| `dev` | 1 | 1 | 256 | runtime_info, context_vars |
| `production` | 2 (up to 4) | 256 | 10000 (fixed) | runtime_info, context_vars |
| `serverless` | 2 | 25 | 256 | runtime_info, context_vars |
| `hardened` | 2 | 256 | 256 | runtime_info, context_vars |
| `minimal` | 1 | 256 | 256 | runtime_info, context_vars |

> **Performance note:** Production-oriented presets use 2 workers for ~30x better throughput compared to single-worker defaults. See [Performance Tuning](performance-tuning.md) for details.

## Reliability Settings

| Preset | `drop_on_full` | `redaction_fail_mode` | `strict_envelope_mode` | File Rotation |
|--------|----------------|----------------------|----------------------|---------------|
| `dev` | N/A | N/A | `False` | None |
| `production` | `False` | `warn` | `False` | Fallback only (50MB x 10, gzip) |
| `serverless` | `True` | `warn` | `False` | None |
| `hardened` | `False` | `closed` | `True` | 50MB x 10, gzip |
| `minimal` | `True` | N/A | `False` | None |

### Understanding `drop_on_full`

- **`False`** (production, hardened): The caller thread retries with exponential backoff up to `backpressure_wait_ms` (default 50ms) before dropping. This ensures durability with bounded latency impact.
- **`True`** (serverless, minimal): Drops events immediately when queue is full, maintaining application throughput. Events may be lost under extreme load.

See [Reliability Defaults](reliability-defaults.md) for detailed backpressure behavior.

## Redaction Settings

| Preset | Auto-Applied Presets | `fallback_redact_mode` | `fallback_scrub_raw` |
|--------|---------------------|----------------------|---------------------|
| `dev` | None | N/A | N/A |
| `production` | CREDENTIALS | `minimal` | `False` |
| `serverless` | CREDENTIALS | `minimal` | `False` |
| `hardened` | HIPAA_PHI + PCI_DSS + CREDENTIALS | `inherit` | `True` |
| `minimal` | None | N/A | N/A |

The **CREDENTIALS** preset automatically redacts:
- `password`, `api_key`, `token`, `secret`
- `authorization`, `api_secret`, `private_key`
- `ssn`, `credit_card`

See [Redaction Presets](../redaction/presets.md) for the complete field list and compliance presets.

## Preset Details

### dev

Local development with maximum visibility.

```python
logger = get_logger(preset="dev")
```

**Settings:**
- DEBUG level shows all messages
- Immediate flushing (batch_size=1) for real-time debugging
- Pretty console output for readability
- Internal diagnostics enabled
- No redaction (safe for local secrets)

**Use when:** Debugging locally, running tests, exploring fapilog features.

### production

Production deployment with adaptive scaling, backpressure retry, and circuit breaker fallback.

```python
logger = get_logger(preset="production")
```

**Settings:**
- INFO level filters noise
- `batch_max_size=256`, `batch_timeout_seconds=0.25`
- `max_queue_size=10000`, `sink_concurrency=8`, `shutdown_timeout_seconds=25.0`
- Adaptive pipeline enabled: dynamic worker scaling (2-4), filter tightening, fixed queue capacity
- Circuit breaker with rotating file fallback — failing sinks are isolated, events reroute to local files
- File rotation: `./logs/fapilog-*.log`, 50MB max, 10 files, gzip compressed (fallback only)
- `drop_on_full=False` — bounded backpressure retry before dropping
- Protected levels: ERROR, CRITICAL (routed to dedicated queue)
- Automatic redaction of credentials

**Use when:** Any production deployment — audit trails, high-throughput APIs, microservices, variable-load workloads.

**Trade-off:** Under extreme load, logging may briefly retry (up to 50ms default) on the caller thread to ensure durability. For latency-sensitive workloads, override with `.with_backpressure(drop_on_full=True)`.

For fine-grained control over adaptive behavior, use the builder:

```python
logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_adaptive(max_workers=6)
    .with_circuit_breaker(fallback_sink="rotating_file")
    .build()
)

# Enable batch sizing when using batch-aware sinks (CloudWatch, Loki, PostgreSQL)
logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_adaptive(batch_sizing=True)
    .add_cloudwatch("/myapp/prod")
    .build()
)
```

See [Adaptive Pipeline](adaptive-pipeline.md) for a detailed guide on tuning thresholds and actuators.

### serverless

Optimized for AWS Lambda, Google Cloud Run, Azure Functions.

```python
logger = get_logger(preset="serverless")
```

**Settings:**
- Stdout-only (cloud providers capture stdout automatically)
- `drop_on_full=True` (don't block in time-constrained environments)
- Smaller batch size (25) for quick flushing before function timeout
- Automatic redaction of credentials
- 2 workers for throughput

**Use when:** Lambda functions, Cloud Run services, any short-lived serverless workload.

### hardened

Maximum security for regulated environments (HIPAA, PCI-DSS, financial services).

```python
logger = get_logger(preset="hardened")
```

**Settings:**
- All strict security settings enabled:
  - `redaction_fail_mode="closed"` — drops events if redaction fails
  - `strict_envelope_mode=True` — rejects malformed envelopes
  - `fallback_redact_mode="inherit"` — full redaction on fallback output
  - `fallback_scrub_raw=True` — scrubs raw fallback output
  - `drop_on_full=False` — never drops logs
- Comprehensive redaction from HIPAA_PHI, PCI_DSS, and CREDENTIALS presets
- File rotation for audit trails

**Use when:** Healthcare (HIPAA), payment processing (PCI-DSS), financial services, any environment requiring fail-closed security.

**Trade-off:** Prioritizes security over availability — may drop events that fail redaction or have malformed data.

### minimal

Matches `get_logger()` with no arguments. Use for explicit preset selection while maintaining backwards compatibility.

```python
logger = get_logger(preset="minimal")
```

**Settings:**
- Default values for everything
- No redaction configured
- No file output

**Use when:** Migrating from another logging library, gradual adoption, explicit "no preset" behavior.

## Migration: `adaptive` to `production`

The `adaptive` preset name is deprecated as of Story 1.53. All adaptive features are now included in the `production` preset.

**Before:**
```python
logger = get_logger(preset="adaptive")  # DeprecationWarning
```

**After:**
```python
logger = get_logger(preset="production")  # Same features, no warning
```

The `adaptive` name continues to work as an alias but emits a `DeprecationWarning`.

## Customizing Presets

Presets are applied first, then builder methods override specific values:

```python
from fapilog import LoggerBuilder

# Start with production, customize for your needs
logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_level("DEBUG")                          # Override log level
    .with_redaction(preset="HIPAA_PHI")           # Add HIPAA fields
    .with_sampling(rate=0.1)                      # Sample 10%
    .add_cloudwatch("/myapp/prod")                # Add CloudWatch sink
    .build()
)
```

Sinks are merged, not replaced:

```python
# Production preset has stdout_json (primary) + rotating_file (fallback)
# This adds CloudWatch without removing those
logger = (
    LoggerBuilder()
    .with_preset("production")
    .add_cloudwatch("/myapp/prod")  # Now has 2 primary sinks + fallback
    .build()
)
```

## Trade-offs Explained

### Latency vs Durability

The fundamental trade-off in production logging:

- **Durability-first** (`production`, `hardened`): Set `drop_on_full=False`. The caller thread retries with bounded backpressure (exponential backoff up to `backpressure_wait_ms`) before dropping. Best for audit trails and debugging.

- **Latency-first** (`serverless`): Set `drop_on_full=True`. Events are dropped if the queue is full, ensuring the application never blocks on logging. Best for latency-sensitive workloads. For production with latency priority, use `production` with `.with_backpressure(drop_on_full=True)`.

### Worker Count Impact

| Workers | Throughput | Use Case |
|---------|------------|----------|
| 1 | ~3,500/sec | Development, low-volume |
| 2 | ~105,000/sec | Production workloads |

All production-oriented presets default to 2 workers. See [Performance Tuning](performance-tuning.md) for benchmarks.

### Redaction Modes

- **`warn`** (default): Log a warning if redaction fails, emit event anyway. Production-safe default.
- **`closed`** (hardened only): Drop the event entirely if redaction fails. Maximum security, may lose events.

## Listing Available Presets

```python
from fapilog import list_presets

print(list_presets())
# ['adaptive', 'dev', 'hardened', 'minimal', 'production', 'serverless']
```

## Related

- [Configuration](configuration.md) — Full configuration guide
- [Builder API](../api-reference/builder.md) — Complete builder method reference
- [Adaptive Pipeline](adaptive-pipeline.md) — Adaptive scaling and pressure monitoring
- [Circuit Breaker](circuit-breaker.md) — Sink fault isolation and fallback routing
- [Redaction Presets](../redaction/presets.md) — Compliance redaction presets
- [Performance Tuning](performance-tuning.md) — Benchmarks and optimization
- [Reliability Defaults](reliability-defaults.md) — Backpressure and queue behavior
