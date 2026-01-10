from __future__ import annotations

import os
import time

import pytest

LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT")

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        boto3 is None or LOCALSTACK_ENDPOINT is None,
        reason="LocalStack endpoint or boto3 not available",
    ),
]


@pytest.mark.asyncio
async def test_cloudwatch_sink_localstack() -> None:
    from fapilog.plugins.sinks.contrib.cloudwatch import (
        CloudWatchSink,
        CloudWatchSinkConfig,
    )

    group = f"/fapilog/test-{int(time.time())}"
    stream = "localstack"

    sink = CloudWatchSink(
        CloudWatchSinkConfig(
            log_group_name=group,
            log_stream_name=stream,
            endpoint_url=LOCALSTACK_ENDPOINT,
            region=os.getenv("AWS_REGION", "us-east-1"),
            batch_size=1,
        )
    )

    await sink.start()
    await sink.write({"level": "INFO", "message": "hello-localstack"})
    await sink.stop()

    client = boto3.client(
        "logs",
        endpoint_url=LOCALSTACK_ENDPOINT,
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )
    events = client.get_log_events(logGroupName=group, logStreamName=stream)
    assert any(
        "hello-localstack" in evt.get("message", "") for evt in events.get("events", [])
    )
