# AWS CloudWatch Logs Sink

Send structured logs to AWS CloudWatch Logs using the built-in `cloudwatch` sink.

## Installation

```bash
pip install "fapilog[aws]"
```

## Configuration

```python
from fapilog import Settings

settings = Settings()
settings.core.sinks = ["cloudwatch"]
settings.sink_config.cloudwatch.log_group_name = "/myapp/prod"
settings.sink_config.cloudwatch.log_stream_name = "web-1"
settings.sink_config.cloudwatch.region = "us-east-1"
settings.sink_config.cloudwatch.batch_size = 100
settings.sink_config.cloudwatch.batch_timeout_seconds = 5.0
settings.sink_config.cloudwatch.max_retries = 3
settings.sink_config.cloudwatch.retry_base_delay = 0.5
```

Environment shortcuts (`FAPILOG_CLOUDWATCH__*`) are supported:

```bash
export FAPILOG_CORE__SINKS='["cloudwatch"]'
export FAPILOG_CLOUDWATCH__LOG_GROUP_NAME=/myapp/prod
export FAPILOG_CLOUDWATCH__LOG_STREAM_NAME=web-1
export FAPILOG_CLOUDWATCH__REGION=us-east-1
export FAPILOG_CLOUDWATCH__ENDPOINT_URL=http://localhost:4566   # LocalStack
```

## Behavior

- **Batching:** Respects CloudWatch limits (10,000 events per batch, ~1 MB per batch). Oversized events (>256 KB) are dropped with diagnostics.
- **Retries:** Handles `InvalidSequenceTokenException`, `DataAlreadyAcceptedException`, and `ThrottlingException` with automatic retry/backoff.
- **Resource management:** Optional creation of log groups/streams.
- **Circuit breaker:** Built-in per-sink circuit breaker to contain repeated failures.
- **Fast path:** Implements `write_serialized` for pipelines using `serialize_in_flush`.
- **Pattern reference:** See [Building SDK-Based Sinks](../../patterns/sdk-sinks.md) for reusable guidance.

## IAM permissions

Minimum permissions for a single log group:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/myapp/*"
    }
  ]
}
```

## Troubleshooting

- **InvalidSequenceTokenException:** Automatically retried with the expected token; ensure only one writer uses a stream or enable distinct streams per instance.
- **ThrottlingException:** Reduce `batch_size` or increase `batch_timeout_seconds`; CloudWatch throttles aggressively on small accounts.
- **ResourceNotFoundException:** Keep `create_log_group` / `create_log_stream` enabled, or pre-create resources with IaC.
- **Oversized events:** Pair with `size_guard` (`max_bytes=256000`) to ensure CloudWatch compatibility.

## Local testing (LocalStack)

Use the example in `examples/cloudwatch_logging`:

```bash
docker-compose up -d
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_REGION=us-east-1
export FAPILOG_CLOUDWATCH__ENDPOINT_URL=http://localhost:4566
uvicorn main:app --reload
```

See `tests/integration/test_cloudwatch_sink_localstack.py` for CI-friendly test patterns.
