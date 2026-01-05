# AWS CloudWatch Logs

Complete CloudWatch integration using the built-in `cloudwatch` sink (`fapilog.plugins.sinks.contrib.cloudwatch`).

## Quick start (code)

```python
from fapilog import Settings, get_logger
from fapilog.plugins.sinks.contrib.cloudwatch import CloudWatchSink, CloudWatchSinkConfig

sink = CloudWatchSink(
    CloudWatchSinkConfig(
        log_group_name="/myapp/production",
        log_stream_name="api-server",
        region="us-west-2",
        batch_size=50,
    )
)
logger = get_logger(settings=Settings(), sinks=[sink])
logger.info("cloudwatch ready", service="api")
```

## Environment setup

```bash
export AWS_REGION=us-west-2
export FAPILOG_CORE__SINKS='["cloudwatch"]'
export FAPILOG_CLOUDWATCH__LOG_GROUP_NAME=/myapp/production
export FAPILOG_CLOUDWATCH__LOG_STREAM_NAME=api-server
# Use IAM role or:
# export AWS_ACCESS_KEY_ID=...
# export AWS_SECRET_ACCESS_KEY=...
```

Then:

```python
from fapilog import get_logger
from fapilog.plugins.sinks.contrib.cloudwatch import CloudWatchSink

logger = get_logger(sinks=[CloudWatchSink()])
logger.error("db connection failed", host="db.internal")
```

## Entry-point registration

```toml
[project.entry-points."fapilog.sinks"]
cloudwatch = "fapilog.plugins.sinks.contrib.cloudwatch:CloudWatchSink"
```

```yaml
core:
  sinks: ["cloudwatch"]
sink_config:
  cloudwatch:
    log_group_name: "/myapp/production"
    log_stream_name: "api-server"
    region: "us-west-2"
```

## Operational notes

- Uses `PutLogEvents` with sequence token handling and time-based batching.
- Retries sequence token mismatches automatically (requeues the batch).
- Tune `batch_size` and `batch_timeout_seconds` for cost/latency.
- Use IAM roles where possible; fall back to access keys in env.

## Troubleshooting

- `InvalidSequenceTokenException`: allow the sink to retry; ensure no other writer targets the same stream.
- `ThrottlingException`: reduce batch rate or add a `rate_limit` filter upstream.
- Ensure clock skew is minimal; CloudWatch requires ordered timestamps.
