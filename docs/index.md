# Fapilog - Batteries-included, async-first logging for Python services

**fapilog** is a high-performance logging pipeline that eliminates the bottlenecks of traditional Python logging. By replacing blocking I/O with a lock-free, async-native architecture, it ensures your application never stalls to write a log. While it’s an excellent choice for FastAPI and microservices, its lightweight footprint and pluggable sinks make it equally powerful for on-prem, desktop, or embedded projects.

**Stability:** Core logger and FastAPI middleware are beta/stable under semver.

## Why Fapilog?

Traditional logging libraries block your application, lose context, and produce unstructured output. Fapilog gives you:

- **Async-first** - Never block your application again
- **Structured** - JSON logs that machines can actually parse
- **Production-ready** - Built-in redaction, metrics, and resilience
- **High-performance** - Lock-free queues and zero-copy processing

**[Read more about why fapilog →](why-fapilog.md)** | **[Compare with alternatives →](comparisons.md)**

## Quick Example

```python
from fapilog import get_async_logger

# Zero-config, works immediately (async)
logger = await get_async_logger()
await logger.info("User logged in", user_id="123")

# Automatic context binding
await logger.error("Database connection failed", exc_info=True)
```

**Output:**

```json
{"timestamp": "2024-01-15T10:30:00.123Z", "level": "INFO", "message": "User logged in", "user_id": "123"}
{"timestamp": "2024-01-15T10:30:01.456Z", "level": "ERROR", "message": "Database connection failed", "exception": "..."}
```

## Get Started

- **[Quickstart Tutorial](getting-started/quickstart.md)** - Get logging in 2 minutes
- **[Installation Guide](getting-started/installation.md)** - Setup and configuration
- **[API Reference](api-reference/index.md)** - Complete API documentation

## Who It's For

- **Backend developers** building APIs and microservices
- **Data engineers** running pipelines and ETL jobs
- **DevOps teams** managing infrastructure and monitoring
- **Anyone** who's tired of logging slowing down their Python apps

---

## Documentation Sections

```{toctree}
:maxdepth: 2
:titlesonly:
:caption: Documentation

getting-started/index
why-fapilog
comparisons
core-concepts/index
user-guide/index
cookbook/index
examples/index
redaction/index
enterprise
api-reference/index
plugins/index
patterns
troubleshooting/index
faq
appendices
```

**Start Here:**

- **[Getting Started](getting-started/index.md)** - Installation and quickstart
- **[Core Concepts](core-concepts/index.md)** - Understanding the architecture
- **[User Guide](user-guide/index.md)** - Practical usage and configuration
- **[Cookbook](cookbook/index.md)** - Focused recipes for common problems
- **[Examples](examples/index.md)** - Real-world usage patterns

**Production Ready:**

- **[Redaction](redaction/index.md)** - Protect sensitive data (GDPR, HIPAA, PCI-DSS)
- **[Enterprise Features](enterprise.md)** - Compliance, audit trails, and security

**Reference:**

- **[API Reference](api-reference/index.md)** - Complete API documentation
- **[Examples](examples/index.md)** - Real-world usage patterns
- **[Troubleshooting](troubleshooting/index.md)** - Common issues and solutions
- **[FAQ](faq.md)** - Frequently asked questions

**Development:**

- **[Contributing](https://github.com/chris-haste/fapilog/blob/main/CONTRIBUTING.md)** - How to contribute to fapilog
- **[Release Notes](release-notes.md)** - Changelog and upgrade guides
- **[Appendices](appendices.md)** - Glossary, architecture diagrams, and license

---

If fapilog is useful to you, consider [giving it a star on GitHub](https://github.com/chris-haste/fapilog) — it helps others discover the library.
