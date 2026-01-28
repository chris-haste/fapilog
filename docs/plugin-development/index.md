# Plugin Development

Create custom plugins to extend fapilog's capabilities.

```{toctree}
:maxdepth: 2
:caption: Plugin Development

quickstart
```

## Getting Started

**New to plugin development?** Start with the [Quickstart Guide](quickstart.md) to create your first plugin in 10 minutes.

## Plugin Types

| Type | Purpose | Use Case |
|------|---------|----------|
| [Sink](../plugins/sinks.md) | Output destinations | Send logs to custom endpoints |
| [Enricher](../plugins/enrichers.md) | Add context | Inject metadata automatically |
| [Redactor](../plugins/redactors.md) | Mask data | Protect sensitive information |
| [Filter](../plugins/filters.md) | Control flow | Sample or drop events |
| [Processor](../plugins/processors.md) | Transform data | Compress or encrypt payloads |

## Resources

- **[Quickstart](quickstart.md)** - Create your first plugin
- **[Plugin Authoring](../plugins/authoring.md)** - Detailed development guide
- **[Testing Plugins](../plugins/testing.md)** - Validation and fixtures
- **[Plugin Catalog](../plugin-guide.md)** - Built-in reference implementations
