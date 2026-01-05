# Common Cloud Sink Patterns

Reusable patterns for building and operating cloud sinks.

## Base class

- `examples/sinks/cloud_sink_base.py` provides:
  - Batching with size/time limits
  - Retry with exponential backoff
  - Background flush loop
  - Health check hook
- Extend it for custom sinks:

```python
from examples.sinks.cloud_sink_base import CloudSinkBase, CloudSinkConfig

class MySink(CloudSinkBase[dict]):
    name = "mycloud"
    async def _initialize_client(self): ...
    async def _cleanup_client(self): ...
    def _transform_entry(self, entry): ...
    async def _send_batch(self, batch): ...
    async def health_check(self): ...
```

## Authentication

- Prefer provider SDK default credentials (IAM roles, ADC) over inline secrets.
- For API keys, load from environment variables or secret stores—not YAML.

## Batching and rate limits

- Start with `batch_size` 50–100; adjust for latency vs cost.
- Combine with `rate_limit` filter to avoid ingestion throttling.
- Align `batch_timeout_seconds` with provider quotas and desired flush latency.

## Retry strategy

- Use exponential backoff (`retry_base_delay`, `retry_max_delay`).
- Retry only on transient errors; surface permanent failures via diagnostics.

## Entry-point wiring

- Register sinks via `pyproject.toml`:

```toml
[project.entry-points."fapilog.sinks"]
cloudwatch = "fapilog.plugins.sinks.contrib.cloudwatch:CloudWatchSink"
datadog = "myapp.sinks.datadog_sink:DatadogSink"
gcp_cloud_logging = "myapp.sinks.gcp_logging_sink:GCPCloudLoggingSink"
```

Then set `core.sinks` to the names; pass config via `sink_config.*`.

## Troubleshooting

- Verify credentials and network egress first.
- Enable `core.enable_metrics` to track drops and backpressure.
- Use `health_check()` in readiness probes for cloud connectivity.
