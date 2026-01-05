# Cloud Sink Examples

End-to-end examples for sending logs to cloud observability platforms using fapilog's sink plugins.

```{toctree}
:maxdepth: 1
:titlesonly:

aws-cloudwatch
loki
gcp-logging
datadog
common-patterns
azure-monitor
elastic
```

Each guide includes:

- Quick start using `get_logger(sinks=[...])`
- Entry-point based wiring for production deployments
- Environment-variable friendly configuration for secrets
- Troubleshooting and cost tips
