from __future__ import annotations

import asyncio
from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from fapilog.core import diagnostics
from fapilog.core.circuit_breaker import CircuitState
from fapilog.core.serialization import SerializedView
from fapilog.plugins import loader
from fapilog.plugins.sinks.contrib import cloudwatch
from fapilog.plugins.sinks.contrib.cloudwatch import (
    CloudWatchSink,
    CloudWatchSinkConfig,
)


class FakeClientError(Exception):
    def __init__(
        self, code: str, expected_token: str | None = None, message: str | None = None
    ) -> None:
        self.response = {"Error": {"Code": code}}
        if expected_token is not None:
            self.response["Error"]["expectedSequenceToken"] = expected_token
        if message:
            self.response["Error"]["Message"] = message
        super().__init__(message or code)


class FakeCloudWatchClient:
    def __init__(self) -> None:
        self.created_groups: list[str] = []
        self.created_streams: list[str] = []
        self.put_calls: list[dict] = []
        self.sequence_token = "token-0"
        self.expected_sequence_token: str | None = None
        self.resource_exists: set[str] = set()
        self.throttle_times = 0
        self.fail_invalid_once = False

    def create_log_group(self, *, logGroupName: str) -> None:
        if logGroupName in self.resource_exists:
            raise FakeClientError("ResourceAlreadyExistsException")
        self.resource_exists.add(logGroupName)
        self.created_groups.append(logGroupName)

    def create_log_stream(self, *, logGroupName: str, logStreamName: str) -> None:
        key = f"{logGroupName}:{logStreamName}"
        if key in self.resource_exists:
            raise FakeClientError("ResourceAlreadyExistsException")
        self.resource_exists.add(key)
        self.created_streams.append(key)

    def describe_log_streams(self, *, logGroupName: str, limit: int) -> dict:
        return {"logStreams": [{"logStreamName": logGroupName}]}

    def put_log_events(self, **kwargs: object) -> dict:
        provided_token = kwargs.get("sequenceToken")
        if self.fail_invalid_once:
            self.fail_invalid_once = False
            raise FakeClientError(
                "InvalidSequenceTokenException", expected_token=self.sequence_token
            )
        if (
            self.expected_sequence_token
            and provided_token != self.expected_sequence_token
        ):
            raise FakeClientError(
                "InvalidSequenceTokenException",
                expected_token=self.expected_sequence_token,
            )
        if self.throttle_times > 0:
            self.throttle_times -= 1
            raise FakeClientError("ThrottlingException")

        self.sequence_token = f"token-{len(self.put_calls) + 1}"
        self.expected_sequence_token = self.sequence_token
        self.put_calls.append(dict(kwargs))
        return {"nextSequenceToken": self.sequence_token}


@pytest.fixture()
def capture_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[list[dict[str, Any]], None, None]:
    diagnostics._reset_for_tests()
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")
    captured: list[dict[str, Any]] = []
    original = diagnostics._writer
    diagnostics.set_writer_for_tests(captured.append)
    yield captured
    diagnostics.set_writer_for_tests(original)


@pytest.fixture()
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeCloudWatchClient:
    client = FakeCloudWatchClient()
    monkeypatch.setattr(cloudwatch, "ClientError", FakeClientError)
    monkeypatch.setattr(
        cloudwatch,
        "boto3",
        SimpleNamespace(client=lambda *_args, **_kwargs: client),
    )
    return client


@pytest.mark.asyncio
async def test_start_creates_group_and_stream(
    fake_client: FakeCloudWatchClient,
) -> None:
    cfg = CloudWatchSinkConfig(
        log_group_name="/app/test",
        log_stream_name="stream-a",
        region="us-east-1",
    )
    sink = CloudWatchSink(cfg)

    await sink.start()
    await sink.stop()

    assert fake_client.created_groups == ["/app/test"]
    assert fake_client.created_streams == ["/app/test:stream-a"]


@pytest.mark.asyncio
async def test_write_serialized_fast_path(fake_client: FakeCloudWatchClient) -> None:
    sink = CloudWatchSink(
        CloudWatchSinkConfig(
            log_group_name="/app/test",
            log_stream_name="stream-a",
            batch_size=1,
            region="us-east-1",
        )
    )
    await sink.start()

    view = SerializedView(data=b'{"message":"hi"}')
    await sink.write_serialized(view)
    await sink.stop()

    assert fake_client.put_calls, "put_log_events not called"
    log_events = fake_client.put_calls[0]["logEvents"]
    assert log_events[0]["message"] == '{"message":"hi"}'


@pytest.mark.asyncio
async def test_invalid_sequence_token_retry(
    fake_client: FakeCloudWatchClient,
) -> None:
    fake_client.expected_sequence_token = "expected-1"
    sink = CloudWatchSink(
        CloudWatchSinkConfig(
            log_group_name="/app/test",
            log_stream_name="stream-a",
            batch_size=1,
            region="us-east-1",
        )
    )
    await sink.start()
    await sink.write({"message": "seq-test"})
    await sink.stop()

    assert len(fake_client.put_calls) >= 1
    assert sink._sequence_token is not None  # noqa: SLF001


@pytest.mark.asyncio
async def test_drops_oversized_events(
    fake_client: FakeCloudWatchClient, capture_diagnostics: list[dict[str, Any]]
) -> None:
    sink = CloudWatchSink(
        CloudWatchSinkConfig(
            log_group_name="/app/test",
            log_stream_name="stream-a",
            batch_size=1,
            region="us-east-1",
        )
    )
    await sink.start()

    huge_message = "x" * (cloudwatch.MAX_EVENT_SIZE_BYTES + 1024)
    await sink.write({"message": huge_message})
    await sink.stop()

    assert fake_client.put_calls == []
    assert any(
        evt.get("component") == "sink"
        and evt.get("message") == "cloudwatch event dropped"
        for evt in capture_diagnostics
    )


def test_settings_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__LOG_GROUP_NAME", "/env/group")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__LOG_STREAM_NAME", "env-stream")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__REGION", "eu-west-1")
    monkeypatch.setenv("FAPILOG_CLOUDWATCH__BATCH_SIZE", "5")
    monkeypatch.setenv("FAPILOG_CORE__SINKS", '["cloudwatch"]')

    from fapilog import Settings

    settings = Settings()
    cfg = settings.sink_config.cloudwatch

    assert cfg.log_group_name == "/env/group"
    assert cfg.log_stream_name == "env-stream"
    assert cfg.region == "eu-west-1"
    assert cfg.batch_size == 5


def test_loader_registers_cloudwatch(
    monkeypatch: pytest.MonkeyPatch, fake_client: FakeCloudWatchClient
) -> None:
    plugin = loader.load_plugin("fapilog.sinks", "cloudwatch", {})
    assert isinstance(plugin, CloudWatchSink)


@pytest.mark.asyncio
async def test_health_check_false_when_circuit_open(
    fake_client: FakeCloudWatchClient,
) -> None:
    sink = CloudWatchSink(
        CloudWatchSinkConfig(
            log_group_name="/app/test",
            log_stream_name="stream-a",
            region="us-east-1",
        )
    )
    await sink.start()
    assert await sink.health_check() is True
    assert sink._circuit_breaker is not None  # noqa: SLF001
    sink._circuit_breaker._state = CircuitState.OPEN  # noqa: SLF001
    assert await sink.health_check() is False
    await sink.stop()


@pytest.mark.asyncio
async def test_throttling_retries_respected(
    fake_client: FakeCloudWatchClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_client.throttle_times = 1
    sink = CloudWatchSink(
        CloudWatchSinkConfig(
            log_group_name="/app/test",
            log_stream_name="stream-a",
            batch_size=1,
            region="us-east-1",
            retry_base_delay=0.01,
        )
    )
    slept: list[float] = []
    original_sleep = asyncio.sleep

    async def tracking_sleep(seconds: float) -> None:
        slept.append(seconds)
        await original_sleep(0)

    monkeypatch.setattr(cloudwatch.asyncio, "sleep", tracking_sleep)

    await sink.start()
    await sink.write({"message": "throttle"})
    await sink.stop()

    assert fake_client.put_calls
    assert slept, "Expected backoff sleep when throttled"


# --- Config Parsing Tests ---


@pytest.mark.asyncio
async def test_cloudwatch_sink_accepts_dict_config_and_coerces(
    fake_client: FakeCloudWatchClient,
) -> None:
    """Dict config with string numbers should be coerced to correct types."""
    sink = CloudWatchSink(
        config={
            "log_group_name": "/dict/test",
            "log_stream_name": "stream-dict",
            "batch_size": "50",  # String should coerce to int
            "region": "us-west-2",
        }
    )
    await sink.start()
    await sink.stop()

    assert sink._config.log_group_name == "/dict/test"
    assert sink._config.batch_size == 50
    assert fake_client.created_groups == ["/dict/test"]


def test_cloudwatch_sink_rejects_unknown_config_fields() -> None:
    """Unknown config keys should raise ValidationError."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CloudWatchSink(
            config={
                "log_group_name": "/test",
                "unknown_field": "oops",
            }
        )


def test_cloudwatch_sink_validates_constraints() -> None:
    """Pydantic Field constraints should be enforced."""
    # batch_size must be >= 1
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        CloudWatchSinkConfig(batch_size=0)

    # batch_timeout_seconds must be > 0
    with pytest.raises(ValidationError, match="greater than 0"):
        CloudWatchSinkConfig(batch_timeout_seconds=0)


@pytest.mark.asyncio
async def test_cloudwatch_sink_auto_generates_stream_name(
    fake_client: FakeCloudWatchClient,
) -> None:
    """When log_stream_name is None, sink should auto-generate one."""
    sink = CloudWatchSink(
        config={
            "log_group_name": "/app/autogen",
            "log_stream_name": None,  # Should auto-generate
            "region": "us-east-1",
        }
    )
    await sink.start()
    await sink.stop()

    # Should have auto-generated a stream name and stored it in instance var
    assert sink._log_stream_name is not None
    assert "-" in sink._log_stream_name  # hostname-timestamp format
    assert fake_client.created_streams


def test_cloudwatch_sink_accepts_kwargs() -> None:
    """Should accept kwargs-style configuration."""
    sink = CloudWatchSink(
        log_group_name="/kwargs/test",
        log_stream_name="stream-kwargs",
        batch_size=25,
        region="eu-west-1",
    )
    assert sink._config.log_group_name == "/kwargs/test"
    assert sink._config.batch_size == 25
