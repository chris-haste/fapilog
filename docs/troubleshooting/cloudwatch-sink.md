# CloudWatch Sink Issues

Common problems when sending logs to AWS CloudWatch Logs.

## InvalidSequenceTokenException

- **Cause:** Multiple writers to the same stream or stale sequence token.
- **Fix:** The sink retries automatically using `expectedSequenceToken`. Ensure each instance uses a unique `log_stream_name` (e.g., include hostname) to avoid contention.

## ThrottlingException

- **Cause:** CloudWatch throttling during bursts.
- **Fix:** Lower `batch_size`, increase `batch_timeout_seconds`, or reduce log volume. The sink backs off exponentially by default.

## ResourceNotFoundException

- **Cause:** Log group or stream is missing.
- **Fix:** Keep `create_log_group`/`create_log_stream` enabled, or pre-create resources. Verify IAM permissions (`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`, `logs:DescribeLogStreams`).

## Oversized events (256 KB)

- **Cause:** Single log entry exceeds CloudWatch event limit.
- **Fix:** Enable `size_guard` with `max_bytes=256000` to truncate or drop before reaching the sink.

## Local testing

- Use LocalStack: set `FAPILOG_CLOUDWATCH__ENDPOINT_URL=http://localhost:4566` and credentials (`test`/`test`).
- See `tests/integration/test_cloudwatch_sink_localstack.py` and `examples/cloudwatch_logging`.
