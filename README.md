# Fapilog v3 - Async-First Logging Library

**fapilog** is an async-first, structured logging library for Python, designed for **FastAPI** and modern cloud-native applications.  
While optimized for distributed, containerized, and serverless environments, it is equally suitable for **on-prem**, **desktop**, or **embedded** Python projects where structured, JSON-ready, and pluggable logging is required.

![Async-first](https://img.shields.io/badge/async-first-008080?style=flat-square&logo=python&logoColor=white)
![JSON Ready](https://img.shields.io/badge/json-ready-004080?style=flat-square&logo=json&logoColor=white)
![Plugin Marketplace](https://img.shields.io/badge/plugin-marketplace-008080?style=flat-square&logo=puzzle&logoColor=white)
![Enterprise Ready](https://img.shields.io/badge/enterprise-ready-004080?style=flat-square&logo=shield&logoColor=white)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-008000?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-008080?style=flat-square&logo=pydantic&logoColor=white)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-008080?style=flat-square&logo=python&logoColor=white)](https://pypi.org/project/fapilog/)
[![PyPI Version](https://img.shields.io/pypi/v/fapilog.svg?style=flat-square&color=008080&logo=pypi&logoColor=white)](https://pypi.org/project/fapilog/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-004080?style=flat-square&logo=apache&logoColor=white)](https://opensource.org/licenses/Apache-2.0)

## Why fapilog?

- **Non‑blocking under slow sinks**: Background worker, queue, and batching keep your app responsive when disk/network collectors slow down.
- **Predictable under bursts**: Configurable backpressure and policy‑driven drops prevent thread stalls during spikes.
- **Service‑ready JSON logging**: Structured events, context binding (request/user IDs), exception serialization, graceful shutdown & drain.
- **Security & compliance guardrails**: Redaction stages (field/regex/url), error de‑duplication, and safe failure behavior.
- **FastAPI integration**: Simple request context propagation and consistent logs across web handlers and background tasks.
- **Operational visibility**: Optional metrics for queue depth, drops, and flush latency.

## When to use / when stdlib is enough

### Use fapilog when
- Services must not jeopardize request latency SLOs due to logging
- Workloads include bursts, slow/remote sinks, or compliance/redaction needs
- Teams standardize on structured JSON logs and contextual metadata

### Stdlib may be enough for
- Small scripts/CLIs writing to fast local stdout/files with minimal structure

## Installation

Copy-ready commands:

```bash
pip install "fapilog>=3,<4"
# or
uv add "fapilog>=3,<4"
```

Optional extras:

```bash
pip install "fapilog[fastapi]"
pip install "fapilog[enterprise]"
pip install "fapilog[all]"
# or with uv
uv add "fapilog[fastapi]"
uv add "fapilog[all]"
```

See full guide: docs/install-and-update.md
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-green.svg)](https://docs.pydantic.dev/)

**Async-first logging library for Python services**

## 🚀 Features (core)

- Async-first architecture (background worker, non-blocking enqueue)
- Structured JSON output (stdout sink by default)
- Plugin-friendly (enrichers, redactors, processors, sinks)
- Context binding and exception serialization
- Guardrails: redaction stages, error de-duplication

## 📦 Installation

```bash
pip install fapilog
```

## 🎯 Quick Start

```python
from fapilog import get_logger, runtime

# Zero-config logger with isolated background worker and stdout JSON sink
logger = get_logger(name="app")
logger.info("Application started", environment="production")

# Scoped runtime that auto-flushes on exit
with runtime() as log:
    log.error("Something went wrong", code=500)
```

## 🏗️ Architecture

Fapilog v3 uses a true async-first pipeline architecture:

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

```python
from fapilog.plugins.enrichers.runtime_info import RuntimeInfoEnricher

logger.disable_enricher("context_vars")
logger.enable_enricher(RuntimeInfoEnricher())
```text

### Internal diagnostics (optional)

Enable structured WARN diagnostics for internal, non-fatal errors (worker/sink):

```bash
export FAPILOG_CORE__INTERNAL_LOGGING_ENABLED=true
```

When enabled, you may see messages like:

```text
[fapilog][worker][WARN] worker_main error: ...
[fapilog][sink][WARN] flush error: ...
```

Apps will not crash; these logs are for development visibility.

## 🔌 Plugin Ecosystem

Fapilog v3 features a universal plugin ecosystem:

### **Sink Plugins**

- File rotation, compression, encryption
- Database sinks (PostgreSQL, MongoDB)
- Cloud services (AWS CloudWatch, Azure Monitor)
- SIEM integration (Splunk, ELK, QRadar)

### **Processor Plugins**

- Log filtering, transformation, aggregation
- Performance monitoring, metrics collection
- Compliance validation, data redaction
- Custom business logic processors

### **Enricher Plugins**

- Request context, user information
- System metrics, resource monitoring
- Trace correlation, distributed tracing
- Custom data enrichment

## 🧩 Extensions (roadmap / optional packages)

- Enterprise sinks: Splunk/Elasticsearch/Loki/Datadog/Kafka/webhooks
- Advanced processors: sampling, compression, encryption, sharding, adaptive batching
- Deep observability: metrics for queue/drops/flush latency, tracing hooks
- Compliance modules: policy packs and attestations
- Operational tooling: plugin marketplace and versioned contracts

## 📈 Enterprise performance characteristics

- **Non‑blocking under slow sinks**
  - Under a simulated 3 ms-per-write sink, fapilog reduced app-side log-call latency by ~75–80% vs stdlib, maintaining sub‑millisecond medians. Reproduce with `scripts/benchmarking.py`.
- **Burst absorption with predictable behavior**
  - With a 20k burst and a 3 ms sink delay, fapilog processed ~90% and dropped ~10% per policy, keeping the app responsive.
- **Honest note**
  - In steady-state fast-sink scenarios, Python’s stdlib logging can be faster per call. Fapilog shines under constrained sinks, concurrency, and bursts.

## 📚 Documentation

- See the `docs/` directory for full documentation
- Benchmarks: `python scripts/benchmarking.py --help`

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [GitHub Repository](https://github.com/chris-haste/fapilog)
- [Documentation](https://fapilog.readthedocs.io/)
- [Plugin Marketplace](https://plugins.fapilog.dev/)
- [Community Discord](https://discord.gg/fapilog)

---

**Fapilog v3** - The future of async-first logging for Python applications.
