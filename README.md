# Fapilog - Production-ready logging for the modern Python stack

**fapilog** delivers production-ready logging for the modern Python stack—async-first, structured, and optimized for FastAPI and cloud-native apps. It’s equally suitable for **on-prem**, **desktop**, or **embedded** projects where structured, JSON-ready, and pluggable logging is required.

![Async-first](https://img.shields.io/badge/async-first-008080?style=flat-square&logo=python&logoColor=white)
![JSON Ready](https://img.shields.io/badge/json-ready-008080?style=flat-square&logo=json&logoColor=white)
![Plugin Marketplace](https://img.shields.io/badge/plugin-marketplace-008080?style=flat-square&logo=puzzle&logoColor=white)
![Enterprise Ready](https://img.shields.io/badge/enterprise-ready-008080?style=flat-square&logo=shield&logoColor=white)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-008080?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Coverage](https://img.shields.io/badge/coverage-90%25-008080?style=flat-square)](docs/quality-signals.md)
![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-008080?style=flat-square&logo=pydantic&logoColor=white)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-008080?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fapilog/)
[![PyPI Version](https://img.shields.io/pypi/v/fapilog.svg?style=flat-square&color=008080&logo=pypi&logoColor=white)](https://pypi.org/project/fapilog/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-008080?style=flat-square&logo=apache&logoColor=white)](https://opensource.org/licenses/Apache-2.0)

## Why fapilog?

- **Non‑blocking under slow sinks**: Background worker, queue, and batching keep your app responsive when disk/network collectors slow down.
- **Predictable under bursts**: Configurable backpressure and policy‑driven drops prevent thread stalls during spikes.
- **Service-ready JSON logging**: Structured events, context binding (request/user IDs), exception serialization, graceful shutdown & drain.
- **Security & compliance guardrails**: Redaction stages (field/regex/url), error de-duplication, and safe failure behavior.
- **FastAPI integration**: Simple request context propagation and consistent logs across web handlers and background tasks.
- **Operational visibility**: Optional metrics for queue depth, drops, and flush latency.
- **Pre-1.0 stability**: Core logger and FastAPI middleware APIs are stable within minor versions; see [Stability](#stability) for details.

## When to use / when stdlib is enough

### Use fapilog when

- Services must not jeopardize request latency SLOs due to logging
- Workloads include bursts, slow/remote sinks, or compliance/redaction needs
- Teams standardize on structured JSON logs and contextual metadata

### Stdlib may be enough for

- Small scripts/CLIs writing to fast local stdout/files with minimal structure

## Installation

```bash
pip install fapilog
```

See the full guide at `docs/getting-started/installation.md` for extras and upgrade paths.
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-green.svg)](https://docs.pydantic.dev/)

**Async-first logging library for Python services**

## 🚀 Features (core)

- Async-first architecture (background worker, non-blocking enqueue)
- Auto console output (pretty in TTY, JSON when piped)
- Plugin-friendly (enrichers, redactors, processors, sinks)
- Context binding and exception serialization
- Guardrails: redaction stages, error de-duplication
- Level-based sink routing (fan out only the levels you want to each sink)

## 🎯 Quick Start

```python
from fapilog import get_logger, runtime

# Zero-config logger with isolated background worker and auto console output
logger = get_logger(name="app")
logger.info("Application started", environment="production")

# Scoped runtime that auto-flushes on exit
with runtime() as log:
    log.error("Something went wrong", code=500)
```

Example output (TTY):
```
2025-01-11 14:30:22 | INFO     | Application started environment=production
```

> **Production Tip:** Use `preset="production"` for log durability - it sets
> `drop_on_full=False` to prevent silent log drops under load. See
> [reliability defaults](docs/user-guide/reliability-defaults.md) for details.

### Configuration Presets

Get started quickly with built-in presets for common scenarios:

```python
from fapilog import get_logger, get_async_logger

# Development: DEBUG level, immediate flush, no redaction
logger = get_logger(preset="dev")
logger.debug("Debugging info")

# Production: INFO level, file rotation, automatic redaction
logger = get_logger(preset="production")
logger.info("User login", password="secret")  # password auto-redacted

# FastAPI: Optimized for async with context propagation
logger = await get_async_logger(preset="fastapi")
await logger.info("Request handled", request_id="abc-123")

# Minimal: Matches default behavior (backwards compatible)
logger = get_logger(preset="minimal")
```

| Preset | Log Level | File Logging | Redaction | Batch Size | Use Case |
|--------|-----------|--------------|-----------|------------|----------|
| `dev` | DEBUG | No | No | 1 (immediate) | Local development |
| `production` | INFO | Yes (50MB rotation) | Yes (9 fields) | 100 | Production deployments |
| `fastapi` | INFO | No | No | 50 | FastAPI/async apps |
| `minimal` | INFO | No | No | Default | Backwards compatible |

See [docs/user-guide/configuration.md](docs/user-guide/configuration.md) for full preset details.

### Sink routing by level

Route errors to a database while sending info logs to stdout:

```bash
export FAPILOG_SINK_ROUTING__ENABLED=true
export FAPILOG_SINK_ROUTING__RULES='[
  {"levels": ["ERROR", "CRITICAL"], "sinks": ["postgres"]},
  {"levels": ["DEBUG", "INFO", "WARNING"], "sinks": ["stdout_json"]}
]'
```

```python
from fapilog import runtime

with runtime() as log:
    log.info("Routine operation")   # → stdout_json
    log.error("Something broke!")   # → postgres
```

See [docs/user-guide/sink-routing.md](docs/user-guide/sink-routing.md) for advanced routing patterns.

### FastAPI request logging

```python
from fastapi import Depends, FastAPI
from fapilog.fastapi import get_request_logger, setup_logging

app = FastAPI(
    lifespan=setup_logging(
        preset="production",
        sample_rate=1.0,                  # sampling for successes; errors always logged
        redact_headers=["authorization"], # mask sensitive headers
        skip_paths=["/healthz"],          # skip noisy paths
    )
)

@app.get("/")
async def root(logger=Depends(get_request_logger)):
    await logger.info("Root endpoint accessed")  # request_id auto-included
    return {"message": "Hello World"}

# Optional marketplace router (plugin discovery)
# from fapilog.fastapi import get_router
# app.include_router(get_router(), prefix=\"/plugins\")
```

Need manual middleware control? Use the existing primitives:

```python
from fastapi import FastAPI
from fapilog.fastapi import setup_logging
from fapilog.fastapi.context import RequestContextMiddleware
from fapilog.fastapi.logging import LoggingMiddleware

app = FastAPI(lifespan=setup_logging(auto_middleware=False))
app.add_middleware(RequestContextMiddleware)  # sets correlation IDs
app.add_middleware(LoggingMiddleware)        # emits request_completed / request_failed
```

## Stability

Fapilog follows [Semantic Versioning](https://semver.org/). As a 0.x project:

- **Core APIs** (logger, FastAPI middleware): Stable within minor versions.
  Breaking changes only in minor version bumps (0.3 → 0.4) with deprecation warnings.
- **Plugins**: Stable unless marked experimental.
- **Experimental**: Marketplace, CLI, mmap_persistence sink. May change without notice.

We aim for 1.0 when core APIs have been production-tested across multiple releases.

### Component Stability

| Component | Stability | Notes |
|-----------|-----------|-------|
| Core logger | Stable | Breaking changes with deprecation |
| FastAPI middleware | Stable | Breaking changes with deprecation |
| Built-in sinks | Stable | file, stdout, webhook |
| Built-in enrichers | Stable | |
| Plugin system | Stable | Contract may evolve |
| Marketplace | Experimental | Config only, not functional |
| CLI | Placeholder | Not implemented |
| mmap_persistence | Experimental | Performance testing |

## Early adopters

Fapilog is pre-1.0 but actively used in production. What this means:

- **Core APIs are stable** - We avoid breaking changes; when necessary, we deprecate first
- **0.x → 0.y upgrades** may require minor code changes (documented in CHANGELOG)
- **Experimental components** (marketplace, CLI) are not ready for production
- **Feedback welcome** - Open issues or join [Discord](https://discord.gg/gHaNsczWte)

## 🏗️ Architecture

Fapilog uses a true async-first pipeline architecture:

```text
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Log Event   │───▶│ Enrichment   │───▶│ Redaction    │───▶│ Processing  │───▶│ Queue        │───▶│ Sinks       │
│             │    │              │    │              │    │             │    │              │    │             │
│ log.info()  │    │ Add context  │    │ Masking      │    │ Formatting  │    │ Async buffer │    │ File/Stdout │
│ log.error() │    │ Trace IDs    │    │ PII removal  │    │ Validation  │    │ Batching     │    │ HTTP/Custom │
|             |    │ User data    │    │ Policy checks│    │ Transform   │    │ Overflow     │    │             │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
```

See Redactors documentation: [docs/plugins/redactors.md](docs/plugins/redactors.md)

## 🔧 Configuration

Container-scoped settings via Pydantic v2:

```python
from fapilog import get_logger
from fapilog.core.settings import Settings

settings = Settings()  # reads env at call time
logger = get_logger(name="api", settings=settings)
logger.info("configured", queue=settings.core.max_queue_size)
```

### Default enrichers

By default, the logger enriches each event before serialization:

- `runtime_info`: `service`, `env`, `version`, `host`, `pid`, `python`
- `context_vars`: `request_id`, `user_id` (if set), and optionally `trace_id`/`span_id` when OpenTelemetry is present

You can toggle enrichers at runtime:

````python
from fapilog.plugins.enrichers.runtime_info import RuntimeInfoEnricher

logger.disable_enricher("context_vars")
logger.enable_enricher(RuntimeInfoEnricher())
```text

### Internal diagnostics (optional)

Enable structured WARN diagnostics for internal, non-fatal errors (worker/sink):

```bash
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
````

When enabled, you may see messages like:

```text
[fapilog][worker][WARN] worker_main error: ...
[fapilog][sink][WARN] flush error: ...
```

Apps will not crash; these logs are for development visibility.

## 🔌 Plugin Ecosystem

Fapilog features an extensible plugin ecosystem:

### **Sink Plugins**

- **Console**: `stdout_json` (JSON lines) and `stdout_pretty` (human-readable)
- **File**: `rotating_file` with size/time rotation, compression, retention
- **HTTP**: `http` and `webhook` sinks with retry, batching, and HMAC signing
- **Cloud**: `cloudwatch` (AWS, requires `boto3`), `loki` (Grafana)
- **Database**: `postgres` (requires `asyncpg`)
- **Compliance**: `audit` sink with integrity checks, `routing` for level-based fan-out

### **Processor Plugins**

- Size guarding and truncation
- Zero-copy optimization for high throughput
- Custom transformation pipelines

### **Enricher Plugins**

- `runtime_info`: service, env, version, host, pid, python version
- `context_vars`: request_id, user_id from ContextVar
- `kubernetes`: pod, namespace, node from K8s downward API

### **Filter Plugins**

- `level`: drop events below threshold
- `sampling`, `adaptive_sampling`, `trace_sampling`: probabilistic filtering
- `rate_limit`: token bucket limiter (per-key optional)
- `first_occurrence`: track unique message patterns

## 🧩 Extensions & Roadmap

**Available now:**
- Enterprise audit logging with `fapilog-tamper` add-on
- Grafana Loki integration
- AWS CloudWatch integration
- PostgreSQL sink for structured log storage

**Roadmap (not yet implemented):**
- Additional cloud providers (Azure Monitor, GCP Logging)
- SIEM integrations (Splunk, Elasticsearch)
- Message queue sinks (Kafka, Redis Streams)

## 📈 Enterprise performance characteristics

- **Non‑blocking under slow sinks**
  - Under a simulated 3 ms-per-write sink, fapilog reduced app-side log-call latency by ~75–80% vs stdlib, maintaining sub‑millisecond medians. Reproduce with `scripts/benchmarking.py`.
- **Burst absorption with predictable behavior**
  - With a 20k burst and a 3 ms sink delay, fapilog processed ~90% and dropped ~10% per policy, keeping the app responsive.
- **Tamper-evident logging add-on**
  - Optional `fapilog-tamper` package adds integrity MAC/signatures, sealed manifests, and enterprise key management (AWS/GCP/Azure/Vault). See `docs/addons/tamper-evident-logging.md` and `docs/enterprise/tamper-enterprise-key-management.md`.
- **Honest note**
  - In steady-state fast-sink scenarios, Python’s stdlib logging can be faster per call. Fapilog shines under constrained sinks, concurrency, and bursts.

## 📚 Documentation

- See the `docs/` directory for full documentation
- Benchmarks: `python scripts/benchmarking.py --help`
- Extras: `pip install fapilog[fastapi]` for FastAPI helpers, `[metrics]` for Prometheus exporter, `[system]` for psutil-based metrics, `[mqtt]` reserved for future MQTT sinks.
- Reliability hint: set `FAPILOG_CORE__DROP_ON_FULL=false` to prefer waiting over dropping under pressure in production.
- Quality signals: ~90% line coverage (see `docs/quality-signals.md`); reliability defaults documented in `docs/user-guide/reliability-defaults.md`.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [GitHub Repository](https://github.com/chris-haste/fapilog)
- [Documentation](https://fapilog.readthedocs.io/)

---

**Fapilog** - The future of async-first logging for Python applications.
