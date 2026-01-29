# Plugin Development

Extend fapilog to send logs anywhere, add context automatically, or mask custom secrets.

```{toctree}
:maxdepth: 2
:caption: Plugin Development

quickstart
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

See also: [Integration Patterns](../patterns.md) for reusable sink and processor patterns.

## Overview

Plugins let you customize fapilog without forking:

- **Send logs anywhere** - Build a sink for your internal system, a new cloud provider, or a message queue
- **Add context automatically** - Enrich every log with deployment info, feature flags, or tenant IDs
- **Mask your secrets** - Create redactors for proprietary data formats or company-specific PII
- **Control log volume** - Filter out noise, sample high-frequency events, or rate-limit by key

## Plugin Types

### [Sinks](sinks.md)

Send logs where you need them—your database, a message queue, a custom API, or a cloud service fapilog doesn't support yet.

### [Enrichers](enrichers.md)

Add context to every log automatically. Examples: deployment version, feature flags, tenant ID, or Kubernetes pod info.

### [Redactors](redactors.md)

Mask sensitive data before it reaches your sinks. Create patterns for company-specific secrets, custom PII formats, or proprietary data.

### [Filters](filters.md)

Control what gets logged. Drop debug logs in production, sample high-frequency events, or rate-limit noisy sources.

### [Processors](processors.md)

Transform logs before they're sent. Compress for cost savings, encrypt for compliance, or reformat for your aggregation tool.

### [Error Handling](error-handling.md)

Handle plugin failures gracefully. Learn how to contain errors so a broken sink doesn't crash your app.

## Getting Started

- [Quickstart](quickstart.md) - Create your first plugin in 10 minutes
- [Plugin Authoring Guide](authoring.md) - Learn how to create plugins
- [Contracts and Versioning](contracts-and-versioning.md) - Understand plugin compatibility
- [Redaction Plugins](redactors.md) - Data security and compliance
- [Plugin Testing](testing.md) - Validate contracts, benchmarks, and fixtures

---

_This section provides comprehensive guidance for plugin development and integration._
