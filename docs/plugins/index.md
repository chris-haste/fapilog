# Plugin Development

Learn how to create and use plugins to extend fapilog's capabilities.

```{toctree}
:maxdepth: 2
:caption: Plugin Development

authoring
contracts-and-versioning
redactors
sinks
enrichers
filters
processors
testing
configuration
health-checks
error-handling
```

## Overview

fapilog provides a comprehensive plugin system that allows you to:

- **Extend functionality** with custom sinks, processors, and enrichers
- **Customize behavior** for your specific use cases
- **Integrate external systems** through plugin interfaces
- **Maintain compatibility** through versioned plugin contracts

## Plugin Types

### [Sinks](sinks.md)

Output destination management for logs and events.

### [Processors](processors.md)

Transform serialized log data (compression, encryption, format conversion).

### [Enrichers](enrichers.md)

Data enrichment and augmentation.

### [Redactors](redactors.md)

Data redaction and masking utilities.

### [Error Handling](error-handling.md)

How to contain errors, emit diagnostics, and keep pipelines healthy.

## Getting Started

- [Plugin Authoring Guide](authoring.md) - Learn how to create plugins
- [Contracts and Versioning](contracts-and-versioning.md) - Understand plugin compatibility
- [Redaction Plugins](redactors.md) - Data security and compliance
- [Plugin Testing](testing.md) - Validate contracts, benchmarks, and fixtures

---

_This section provides comprehensive guidance for plugin development and integration._
