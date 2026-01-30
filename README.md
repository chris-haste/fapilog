<p align="center">
  <a href="https://fapilog.dev">
    <img src="https://fapilog.dev/fapilog-logo.png" alt="Fapilog Logo" width="200">
  </a>
</p>

# Fapilog - Batteries-included, async-first logging for Python services

![Async-first](https://img.shields.io/badge/async-first-9FE17B?style=flat-square&logo=python&logoColor=white)
![JSON Ready](https://img.shields.io/badge/json-ready-9FE17B?style=flat-square&logo=json&logoColor=white)
![Enterprise Ready](https://img.shields.io/badge/enterprise-ready-9FE17B?style=flat-square&logo=shield&logoColor=white)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-9FE17B?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Coverage](https://img.shields.io/badge/coverage-90%25-9FE17B?style=flat-square)](docs/quality-signals.md)
![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-9FE17B?style=flat-square&logo=pydantic&logoColor=white)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-9FE17B?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fapilog/)
[![PyPI Version](https://img.shields.io/pypi/v/fapilog.svg?style=flat-square&color=9FE17B&logo=pypi&logoColor=white)](https://pypi.org/project/fapilog/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-9FE17B?style=flat-square&logo=apache&logoColor=white)](https://opensource.org/licenses/Apache-2.0)

**fapilog** delivers production-ready logging for the modern Python stack—async-first, structured, and optimized for FastAPI and cloud-native apps. It's equally suitable for **on-prem**, **desktop**, or **embedded** projects where structured, JSON-ready, and pluggable logging is required.

Fapilog isn't a thin wrapper over existing logging libraries—it's an async-first logging pipeline designed to keep your app responsive under slow or bursty log sinks, with backpressure policies, redaction, and first-class FastAPI integration built in.

> **Save evaluation time:** [Independent technical assessments](docs/audits/) are available from multiple AI reviewers.

## Why fapilog?

- **Your app speed doesn't depend on your log destination**: Even if logs go to a slow S3 bucket or flaky network, your API responses stay fast.
- **Predictable behavior under load**: You decide what happens during traffic spikes—drop logs gracefully or wait briefly. No random thread stalls.
- **No lost logs on shutdown**: Graceful drain ensures those final logs make it to storage before your container stops.
- **Secrets stay out of logs automatically**: Passwords, API keys, and tokens are redacted by default with production presets.
- **Request tracking without boilerplate**: Bind a request ID once and it appears in every log—no need to pass it through your call stack.
- **See what's happening in production**: Optional metrics show queue depth, dropped logs, and flush latency so you can tune before problems hit.
- **Pre-1.0 stability**: Core logger and FastAPI middleware APIs are stable within minor versions; see [Stability](#stability) for details.

**[Read more →](https://docs.fapilog.dev/en/latest/why-fapilog.html)** | **[Compare with structlog, loguru, and others →](https://docs.fapilog.dev/en/latest/comparisons.html)**

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

## 🚀 Features (core)

- **Log calls never block on I/O** — your app stays fast even with slow sinks
- **Smart console output** — pretty in terminal, JSON when piped to files or tools
- **Extend without forking** — add enrichers, redactors, processors, or custom sinks
- **Context flows automatically** — bind request_id once, see it in every log
- **Secrets masked by default** — passwords and API keys don't leak to logs
- **Route logs by level** — send errors to your database, info to stdout

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

| Preset | Log Level | File Logging | Redaction | Batch Size | Workers | When to use |
|--------|-----------|--------------|-----------|------------|---------|-------------|
| `dev` | DEBUG | No | No | 1 (immediate) | 1 | See every log instantly while debugging locally |
| `production` | INFO | Yes (50MB rotation) | Yes (9 fields) | 100 | 2 | Never lose logs, automatically mask secrets |
| `fastapi` | INFO | No | Yes (9 fields) | 50 | 2 | Async apps where you want redaction without file overhead |
| `serverless` | INFO | No | Yes (9 fields) | 25 | 2 | Lambda/Cloud Functions with fast flush |
| `hardened` | INFO | Yes (50MB rotation) | Yes (compliance) | 100 | 2 | Regulated environments (HIPAA, PCI-DSS) |
| `minimal` | INFO | No | No | Default | 1 | Migrating from another logger—start here |

> **Security Note:** By default, only URL credentials (`user:pass@host`) are stripped. For full field redaction (passwords, API keys, tokens), use a preset like `production`/`fastapi` or configure redactors manually. See [redaction docs](docs/redaction/index.md).

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
- **Experimental**: CLI, mmap_persistence sink. May change without notice.

We aim for 1.0 when core APIs have been production-tested across multiple releases.

### Component Stability

| Component | Stability | Notes |
|-----------|-----------|-------|
| Core logger | Stable | Breaking changes with deprecation |
| FastAPI middleware | Stable | Breaking changes with deprecation |
| Built-in sinks | Stable | file, stdout, webhook |
| Built-in enrichers | Stable | |
| Plugin system | Stable | Contract may evolve |
| CLI | Placeholder | Not implemented |
| mmap_persistence | Experimental | Performance testing |

## Early adopters

Fapilog is pre-1.0 but actively used in production. What this means:

- **Core APIs are stable** - We avoid breaking changes; when necessary, we deprecate first
- **0.x → 0.y upgrades** may require minor code changes (documented in CHANGELOG)
- **Experimental components** (CLI, mmap_persistence) are not ready for production
- **Feedback welcome** - Open issues or join [Discord](https://discord.gg/gHaNsczWte)

## 🏗️ Architecture

Your log calls return immediately. Everything else happens in the background:

```text
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Log Event   │───▶│ Enrichment   │───▶│ Redaction    │───▶│ Processing  │───▶│ Queue        │───▶│ Sinks       │
│             │    │              │    │              │    │             │    │              │    │             │
│ log.info()  │    │ Add context  │    │ Masking      │    │ Formatting  │    │ Async buffer │    │ File/Stdout │
│ log.error() │    │ Trace IDs    │    │ PII removal  │    │ Validation  │    │ Batching     │    │ HTTP/Custom │
|             |    │ User data    │    │ Policy checks│    │ Transform   │    │ Overflow     │    │             │
└─────────────┘    └──────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
     ↑                                                                                                  ↑
     │                                                                                                  │
  Returns                                                                              Slow sinks don't
  immediately                                                                          affect your app
```

See Redactors documentation: [docs/plugins/redactors.md](docs/plugins/redactors.md)

## 🔧 Configuration

### Builder API (Recommended)

The Builder API provides a fluent, type-safe way to configure loggers:

```python
from fapilog import LoggerBuilder

# Production setup with file rotation and CloudWatch
logger = (
    LoggerBuilder()
    .with_preset("production")
    .with_level("INFO")
    .add_file("logs/app", max_bytes="100 MB", max_files=10)
    .add_cloudwatch("/myapp/prod", region="us-east-1")
    .with_circuit_breaker(enabled=True)
    .with_redaction(fields=["password", "api_key"])
    .build()
)

# Async version for FastAPI
from fapilog import AsyncLoggerBuilder

logger = await (
    AsyncLoggerBuilder()
    .with_preset("fastapi")
    .add_stdout()
    .build_async()
)
```

See [Builder API Reference](docs/api-reference/builder.md) for complete documentation.

### Settings Class

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

```python
from fapilog.plugins.enrichers.runtime_info import RuntimeInfoEnricher

logger.disable_enricher("context_vars")
logger.enable_enricher(RuntimeInfoEnricher())
```

### Internal diagnostics (optional)

Enable structured WARN diagnostics for internal, non-fatal errors (worker/sink):

```bash
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
```

Diagnostics write to **stderr** by default (Unix convention), keeping them separate from application logs on stdout. For backward compatibility:

```bash
export FAPILOG_CORE__DIAGNOSTICS_OUTPUT=stdout
```

When enabled, you may see messages like:

```text
[fapilog][worker][WARN] worker_main error: ...
[fapilog][sink][WARN] flush error: ...
```

Apps will not crash; these logs are for development visibility.

## 🔌 Plugin Ecosystem

Send logs anywhere, enrich them automatically, and filter what you don't need:

### **Sinks** — Send logs where you need them

- **Console**: JSON for machines, pretty output for humans
- **File**: Auto-rotating logs with compression and retention policies
- **HTTP/Webhook**: Send to any endpoint with retry, batching, and HMAC signing
- **Cloud**: CloudWatch (AWS), Loki (Grafana) — no custom integration needed
- **Database**: PostgreSQL for queryable log storage
- **Routing**: Split by level — errors to one place, info to another

### **Enrichers** — Add context without boilerplate

- **Runtime info**: Service name, version, host, PID added automatically
- **Request context**: request_id, user_id flow through without passing them around
- **Kubernetes**: Pod, namespace, node info from K8s downward API

### **Filters** — Control log volume and cost

- **Level filtering**: Drop DEBUG in production
- **Sampling**: Log 10% of successes, 100% of errors
- **Rate limiting**: Prevent log floods from crashing your aggregator

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

## ⚡ Execution Modes & Throughput

Fapilog automatically detects your execution context and optimizes accordingly:

| Mode | Context | Throughput | Use Case |
|------|---------|------------|----------|
| **Async** | `AsyncLoggerFacade` or `await` calls | ~100K+ events/sec | FastAPI, async frameworks |
| **Bound loop** | `SyncLoggerFacade` started inside async | ~100K+ events/sec | Sync APIs in async apps |
| **Thread** | `SyncLoggerFacade` started outside async | ~10-15K events/sec | CLI tools, sync scripts |

```python
# Async mode (fastest) - for FastAPI and async code
from fapilog import get_async_logger
logger = await get_async_logger(preset="fastapi")
await logger.info("event")  # ~100K+ events/sec

# Bound loop mode - sync API, async performance
async def main():
    logger = get_logger(preset="production")  # Started inside async context
    logger.info("event")  # ~100K+ events/sec (no cross-thread overhead)

# Thread mode - for traditional sync code
logger = get_logger(preset="production")  # Started outside async context
logger.info("event")  # ~10-15K events/sec (cross-thread sync)
```

**Why the difference?** Thread mode requires cross-thread synchronization for each log call. Async and bound loop modes avoid this overhead by working directly with the event loop.

**Recommendation:** For maximum throughput in async applications, use `AsyncLoggerFacade` or ensure `SyncLoggerFacade.start()` is called inside an async context.

See [Execution Modes Guide](docs/user-guide/execution-modes.md) for detailed patterns and migration tips.

## 📈 Enterprise performance characteristics

- **High throughput in async modes**
  - AsyncLoggerFacade and bound loop mode deliver ~100,000+ events/sec. Thread mode (sync code outside async) achieves ~10-15K events/sec due to cross-thread coordination. See [execution modes](docs/user-guide/execution-modes.md) for details.
- **Non‑blocking under slow sinks**
  - Under a simulated 3 ms-per-write sink, fapilog reduced app-side log-call latency by ~75–80% vs stdlib, maintaining sub‑millisecond medians. Reproduce with `scripts/benchmarking.py`.
- **Burst absorption with predictable behavior**
  - With a 20k burst and a 3 ms sink delay, fapilog processed ~90% and dropped ~10% per policy, keeping the app responsive.
- **Tamper-evident logging add-on**
  - Optional `fapilog-tamper` package adds integrity MAC/signatures, sealed manifests, and enterprise key management (AWS/GCP/Azure/Vault). See `docs/addons/tamper-evident-logging.md` and `docs/enterprise/tamper-enterprise-key-management.md`.
- **Honest note**
  - In steady-state fast-sink scenarios, Python's stdlib logging can be faster per call. Fapilog shines under constrained sinks, concurrency, and bursts.

## 📚 Documentation

- See the `docs/` directory for full documentation
- Benchmarks: `python scripts/benchmarking.py --help`
- Extras: `pip install fapilog[fastapi]` for FastAPI helpers, `[metrics]` for Prometheus exporter, `[system]` for psutil-based metrics, `[mqtt]` reserved for future MQTT sinks.
- Reliability hint: set `FAPILOG_CORE__DROP_ON_FULL=false` to prefer waiting over dropping under pressure in production.
- Quality signals: ~90% line coverage (see `docs/quality-signals.md`); reliability defaults documented in `docs/user-guide/reliability-defaults.md`.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## Support

If fapilog is useful to you, consider giving it a star on GitHub — it helps others discover the library.

[![Star on GitHub](https://img.shields.io/github/stars/chris-haste/fapilog?style=social)](https://github.com/chris-haste/fapilog)

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [Website](https://fapilog.dev)
- [GitHub Repository](https://github.com/chris-haste/fapilog)
- [Documentation](https://fapilog.readthedocs.io/en/stable/)

---

**Fapilog** - Batteries-included, async-first logging for Python services.
