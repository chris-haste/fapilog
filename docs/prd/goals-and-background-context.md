# Goals and Background Context

## Goals

- **Immediate Developer Productivity**: Create a logging library that works perfectly out of the box with zero configuration - `pip install fapilog` → productive immediately
- **Progressive Enhancement Philosophy**: Built-in core features provide complete logging solution, plugins enable enterprise superpowers
- **Revolutionary Async Performance**: Achieve 500K-2M events/second throughput with zero-copy operations and parallel processing
- **Plugin Ecosystem Power**: Enterprise compliance, advanced sinks, and specialized processing available through simple plugin installation
- **Universal Adoption**: Serve individual developers (zero config), startups (basic config), enterprises (plugin ecosystem) with the same core library
- **Native FastAPI Support**: Provide seamless integration with FastAPI for request-aware logging, middleware injection, lifecycle management, and observability
- **Developer-First Design**: Prioritize simplicity and immediate value, with enterprise complexity hidden behind optional plugins
- **Production Excellence**: Built-in features are production-ready; plugins add enterprise capabilities without core complexity

## Background Context

Fapilog v2 demonstrated architectural excellence, but v3 represents a fundamental shift in philosophy: **developer-first simplicity with plugin-based enterprise power**. Instead of a complex enterprise-first approach, v3 provides immediate value with built-in features while enabling unlimited extensibility through plugins.

**Core Philosophy**:

- **Built-in Features**: Complete logging solution (stdout, file, JSON, filtering, correlation) - works immediately after installation
- **Plugin Ecosystem**: Enterprise features (Splunk, compliance, PII redaction, alerting) available as optional plugins
- **FastAPI Integration**: Seamless integration with popular async web frameworks such as FastAPI for request-aware logging
- **Zero Configuration**: Default settings provide production-ready logging without any setup
- **Progressive Enhancement**: Start simple, add power as needed through plugin installation

This approach ensures fapilog competes with simple libraries for ease of use while providing enterprise capabilities that exceed complex enterprise solutions.

## Built-in vs Plugin Feature Strategy

**Core Library (Built-in) - Works immediately after `pip install fapilog`:**

| Category          | Built-in Features                           | Purpose                       |
| ----------------- | ------------------------------------------- | ----------------------------- |
| **Sinks**         | stdout, stderr, file, null                  | Essential output destinations |
| **Processors**    | filter, throttle, format, dedupe            | Core processing capabilities  |
| **Enrichers**     | timestamp, correlation, context, hostname   | Essential context enrichment  |
| **Formatters**    | simple, json, logfmt, minimal               | Standard output formats       |
| **Performance**   | Async pipeline, batching, zero-copy         | Revolutionary throughput      |
| **Configuration** | Zero-config defaults, environment variables | Immediate productivity        |
| **Integrations**  | FastAPI middleware, lifecycle, DI           | Framework compatibility       |

**Important**: The core library is a **pure Python logging library with no REST API or HTTP endpoints**. Web-based features (plugin marketplace discovery) leverage existing GitHub Pages infrastructure rather than requiring API servers.

**Plugin Ecosystem (Optional) - Enhanced capabilities via plugin installation:**

| Category                   | Plugin Examples                                  | Purpose                         |
| -------------------------- | ------------------------------------------------ | ------------------------------- |
| **Enterprise Sinks**       | splunk, elasticsearch, datadog, loki, kafka      | Advanced output destinations    |
| **Enterprise Processing**  | pii-redaction, encryption, compression, alerting | Advanced processing             |
| **Enterprise Enrichment**  | user-context, geo-location, performance-metrics  | Advanced context                |
| **Enterprise Compliance**  | pci-dss, hipaa, sox, gdpr, audit-trails          | Regulatory requirements         |
| **Enterprise Integration** | siem, apm, observability platforms               | Platform integration            |
| **Enterprise Features**    | advanced-compression, sharding, caching          | Performance optimization        |
| **Integrations**           | request-logger, otel-formatter, tracing          | HTTP access logs, OTEL, tracing |

**Progressive Enhancement Examples:**

```python