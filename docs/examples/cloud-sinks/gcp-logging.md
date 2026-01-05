# Google Cloud Logging

Send structured logs to Google Cloud Logging using the example sink in `examples/sinks/gcp_logging_sink.py`.

## Quick start (code)

```python
from fapilog import Settings, get_logger
from examples.sinks.gcp_logging_sink import GCPCloudLoggingSink, GCPCloudLoggingConfig

sink = GCPCloudLoggingSink(
    GCPCloudLoggingConfig(
        log_name="myapp",
        project="my-gcp-project",
        resource_type="gce_instance",
        resource_labels={"instance_id": "abc", "zone": "us-central1-a"},
        labels={"env": "prod"},
    )
)
logger = get_logger(settings=Settings(), sinks=[sink])
logger.info("hello gcp", user="alice")
```

## Environment setup

```bash
export GOOGLE_CLOUD_PROJECT=my-gcp-project
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Then:

```python
from fapilog import get_logger
from examples.sinks.gcp_logging_sink import GCPCloudLoggingSink

logger = get_logger(sinks=[GCPCloudLoggingSink()])
logger.warning("rate limited", path="/api")
```

## Entry-point registration

```toml
[project.entry-points."fapilog.sinks"]
gcp_cloud_logging = "myapp.sinks.gcp_logging_sink:GCPCloudLoggingSink"
```

```yaml
core:
  sinks: ["gcp_cloud_logging"]
sink_config:
  gcp_cloud_logging:
    log_name: "myapp"
    resource_type: "global"
    labels:
      env: "prod"
```

## Operational notes

- Uses `google-cloud-logging` client with `log_struct` for structured payloads.
- Leverages Application Default Credentials; service accounts via `GOOGLE_APPLICATION_CREDENTIALS`.
- Provide `resource_type` and `resource_labels` to align with GCP billing/metrics.

## Troubleshooting

- Auth errors: verify ADC is available or the service account JSON path.
- Missing labels: ensure `resource_labels` keys match the selected resource type.
