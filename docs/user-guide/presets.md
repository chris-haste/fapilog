# Configuration Presets

Presets provide pre-configured settings for common deployment scenarios. Choose a preset that matches your use case to get sensible defaults without manual configuration.

## Quick Reference

| Preset | Use Case | Drops Logs? | File Output | Redaction |
|--------|----------|-------------|-------------|-----------|
| `dev` | Local development | No | No | No |
| `production` | Durable production | Never | Yes | Yes (CREDENTIALS) |
| `production-latency` | Low-latency production | If needed | No | Yes (CREDENTIALS) |
| `fastapi` | FastAPI applications | If needed | No | Yes (CREDENTIALS) |
| `serverless` | Lambda/Cloud Run | If needed | No | Yes (CREDENTIALS) |
| `hardened` | Compliance (HIPAA/PCI) | Never | Yes | Yes (HIPAA + PCI + CREDENTIALS) |
| `minimal` | Maximum control | Default | Default | No |

## Choosing a Preset

```
Is this for local development?
├─ Yes → dev
└─ No → Is this for serverless (Lambda/Cloud Run)?
         ├─ Yes → serverless
         └─ No → Do you need HIPAA/PCI compliance?
                  ├─ Yes → hardened
                  └─ No → Are you using FastAPI?
                           ├─ Yes → fastapi
                           └─ No → Is log durability critical?
                                    ├─ Yes → production (never drops)
                                    └─ No → production-latency (prioritizes speed)
```

### Key Decision: `production` vs `production-latency`

Both presets are production-ready with automatic redaction. The difference is in the latency vs durability trade-off:

| Aspect | `production` | `production-latency` |
|--------|--------------|---------------------|
| **Philosophy** | Never lose logs | Don't block the app |
| **`drop_on_full`** | `False` | `True` |
| **File sink** | Yes (50MB rotation) | No |
| **Best for** | Audit trails, debugging, compliance | High-throughput APIs, latency-sensitive |
| **Trade-off** | May briefly block under extreme load | May drop logs under extreme load |

**Recommendation:**
- Use `production` when every log matters (audit trails, compliance, debugging production issues)
- Use `production-latency` when response time matters more than capturing every log (high-throughput APIs, user-facing latency SLOs)

## Usage

```python
from fapilog import get_logger, LoggerBuilder

# Simple usage
logger = get_logger(preset="production")

# Builder API
logger = (
    LoggerBuilder()
    .with_preset("production-latency")
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
| `production` | 2 | 100 | 256 | runtime_info, context_vars |
| `production-latency` | 2 | 100 | 256 | runtime_info, context_vars |
| `fastapi` | 2 | 50 | 256 | context_vars only |
| `serverless` | 2 | 25 | 256 | runtime_info, context_vars |
| `hardened` | 2 | 100 | 256 | runtime_info, context_vars |
| `minimal` | 1 | 256 | 256 | runtime_info, context_vars |

> **Performance note:** Production-oriented presets use 2 workers for ~30x better throughput compared to single-worker defaults. See [Performance Tuning](performance-tuning.md) for details.

## Reliability Settings

| Preset | `drop_on_full` | `redaction_fail_mode` | `strict_envelope_mode` | File Rotation |
|--------|----------------|----------------------|----------------------|---------------|
| `dev` | N/A | N/A | `False` | None |
| `production` | `False` | `warn` | `False` | 50MB × 10, gzip |
| `production-latency` | `True` | `warn` | `False` | None |
| `fastapi` | `True` | `warn` | `False` | None |
| `serverless` | `True` | `warn` | `False` | None |
| `hardened` | `False` | `closed` | `True` | 50MB × 10, gzip |
| `minimal` | `True` | N/A | `False` | None |

### Understanding `drop_on_full`

- **`False`**: Queue blocks briefly when full, ensuring no log loss. May add latency under extreme load.
- **`True`**: Drops events when queue is full, maintaining application throughput. Events may be lost under extreme load.

See [Reliability Defaults](reliability-defaults.md) for detailed backpressure behavior.

## Redaction Settings

| Preset | Auto-Applied Presets | `fallback_redact_mode` | `fallback_scrub_raw` |
|--------|---------------------|----------------------|---------------------|
| `dev` | None | N/A | N/A |
| `production` | CREDENTIALS | `minimal` | `False` |
| `production-latency` | CREDENTIALS | `minimal` | `False` |
| `fastapi` | CREDENTIALS | `minimal` | `False` |
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

Production deployments where log durability is critical.

```python
logger = get_logger(preset="production")
```

**Settings:**
- INFO level filters noise
- File rotation: `./logs/fapilog-*.log`, 50MB max, 10 files, gzip compressed
- `drop_on_full=False` — logs block briefly rather than drop
- Automatic redaction of credentials
- 2 workers for 30x throughput improvement

**Use when:** Audit trails matter, debugging production issues, compliance requirements, post-incident analysis.

**Trade-off:** Under extreme load, logging may briefly block the application to ensure no log loss.

### production-latency

Production deployments where application latency is critical.

```python
logger = get_logger(preset="production-latency")
```

**Settings:**
- INFO level filters noise
- Stdout-only (no file I/O latency)
- `drop_on_full=True` — drops logs rather than block
- Automatic redaction of credentials
- 2 workers for 30x throughput improvement

**Use when:** High-throughput APIs, latency-sensitive services, user-facing endpoints with strict SLOs.

**Trade-off:** Under extreme load, some log events may be dropped to maintain application throughput.

### fastapi

Optimized for async FastAPI applications.

```python
from fapilog.fastapi import setup_logging
from fastapi import FastAPI

app = FastAPI(lifespan=setup_logging(preset="fastapi"))
```

**Settings:**
- INFO level
- `context_vars` enricher only (reduced overhead for high-throughput)
- Container-friendly stdout JSON output
- Automatic redaction of credentials
- 2 workers for throughput

**Use when:** FastAPI applications, async workloads, container deployments.

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
# Production preset has stdout_json + rotating_file
# This adds CloudWatch without removing those
logger = (
    LoggerBuilder()
    .with_preset("production")
    .add_cloudwatch("/myapp/prod")  # Now has 3 sinks
    .build()
)
```

## Trade-offs Explained

### Latency vs Durability

The fundamental trade-off in production logging:

- **Durability-first** (`production`, `hardened`): Set `drop_on_full=False`. The logging pipeline will briefly block if the queue fills up, ensuring no log events are lost. Best for audit trails and debugging.

- **Latency-first** (`production-latency`, `fastapi`, `serverless`): Set `drop_on_full=True`. Events are dropped if the queue is full, ensuring the application never blocks on logging. Best for latency-sensitive workloads.

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
# ['dev', 'fastapi', 'hardened', 'minimal', 'production', 'production-latency', 'serverless']
```

## Related

- [Configuration](configuration.md) — Full configuration guide
- [Builder API](../api-reference/builder.md) — Complete builder method reference
- [Redaction Presets](../redaction/presets.md) — Compliance redaction presets
- [Performance Tuning](performance-tuning.md) — Benchmarks and optimization
- [Reliability Defaults](reliability-defaults.md) — Backpressure and queue behavior
