# Fapilog — Fast, Async, Structured Logging for Python

**The logging library that doesn't slow you down.**

## Why Fapilog?

Traditional logging libraries block your application, lose context, and produce unstructured output. Fapilog gives you:

- **🚀 Async-first** - Never block your application again
- **📊 Structured** - JSON logs that machines can actually parse
- **🔒 Production-ready** - Built-in redaction, metrics, and resilience
- **⚡ High-performance** - Lock-free queues and zero-copy processing

## Quick Example

```python
from fapilog import get_logger

# Zero-config, works immediately
logger = get_logger()
await logger.info("User logged in", extra={"user_id": "123"})

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
:maxdepth: 3
:caption: Documentation

getting-started/index
core-concepts/index
user-guide/index
api-reference/index
examples/index
troubleshooting/index
faq
contributing/index
release-notes
appendices
```

**Start Here:**

- **[Getting Started](getting-started/index.md)** - Installation and quickstart
- **[Core Concepts](core-concepts/index.md)** - Understanding the architecture
- **[User Guide](user-guide/index.md)** - Practical usage and configuration

**Reference:**

- **[API Reference](api-reference/index.md)** - Complete API documentation
- **[Examples](examples/index.md)** - Real-world usage patterns
- **[Troubleshooting](troubleshooting/index.md)** - Common issues and solutions
- **[FAQ](faq.md)** - Frequently asked questions

**Development:**

- **[Contributing](contributing/index.md)** - How to contribute to fapilog
- **[Documentation Guide](documentation-guide-for-contributors.md)** - Writing and maintaining docs
- **[Release Notes](release-notes.md)** - Changelog and upgrade guides
- **[Appendices](appendices.md)** - Glossary, architecture diagrams, and license
