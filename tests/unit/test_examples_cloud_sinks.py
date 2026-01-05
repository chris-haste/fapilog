from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# Ensure example modules (outside src/) are importable in tests
sys.path.append(str(Path(__file__).resolve().parents[2]))


class _SleepCalls:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.calls.append(delay)
        return None


@pytest.mark.asyncio
async def test_cloud_sink_base_batches_and_flushes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from examples.sinks.cloud_sink_base import CloudSinkBase, CloudSinkConfig

    sent: list[list[dict]] = []

    class DemoSink(CloudSinkBase[dict]):
        name = "demo"

        def __init__(self) -> None:
            super().__init__(CloudSinkConfig(batch_size=2, batch_timeout_seconds=0.01))

        async def _initialize_client(self) -> None:
            return None

        async def _cleanup_client(self) -> None:
            return None

        def _transform_entry(self, entry: dict) -> dict:
            return {"wrapped": entry}

        async def _send_batch(self, batch: list[dict]) -> None:
            sent.append(batch)

        async def health_check(self) -> bool:
            return True

    sink = DemoSink()
    await sink.start()
    await sink.write({"msg": "a"})
    await sink.write({"msg": "b"})  # flushes due to batch_size
    await sink.write({"msg": "c"})
    await sink.stop()  # flushes final

    assert sent == [
        [{"wrapped": {"msg": "a"}}, {"wrapped": {"msg": "b"}}],
        [{"wrapped": {"msg": "c"}}],
    ]


@pytest.mark.asyncio
async def test_cloud_sink_base_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    from examples.sinks.cloud_sink_base import CloudSinkBase, CloudSinkConfig

    sleep_spy = _SleepCalls()
    monkeypatch.setattr("examples.sinks.cloud_sink_base.asyncio.sleep", sleep_spy)

    attempts: list[int] = []

    class RetrySink(CloudSinkBase[int]):
        name = "retry"

        def __init__(self) -> None:
            super().__init__(
                CloudSinkConfig(
                    batch_size=1,
                    batch_timeout_seconds=0.01,
                    max_retries=3,
                    retry_base_delay=0.1,
                )
            )

        async def _initialize_client(self) -> None:
            return None

        async def _cleanup_client(self) -> None:
            return None

        def _transform_entry(self, entry: dict) -> int:
            return entry["n"]

        async def _send_batch(self, batch: list[int]) -> None:
            attempts.append(len(attempts))
            if len(attempts) < 2:
                raise RuntimeError("boom")
            return None

        async def health_check(self) -> bool:
            return True

    sink = RetrySink()
    await sink.start()
    await sink.write({"n": 1})
    await sink.stop()

    assert attempts == [0, 1]
    assert sleep_spy.calls and sleep_spy.calls[0] == pytest.approx(0.1, rel=0.1)


@pytest.mark.asyncio
async def test_cloudwatch_sink_handles_sequence_token_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fapilog.plugins.sinks.contrib import cloudwatch as module

    class FakeClientError(Exception):
        def __init__(self, code: str, expected: str | None = None) -> None:
            self.response = {"Error": {"Code": code}}
            if expected is not None:
                self.response["Error"]["expectedSequenceToken"] = expected

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []
            self.created = {"group": 0, "stream": 0}
            self.fail_first = True
            self.expected_token: str | None = None

        def create_log_group(self, **_: Any) -> None:
            self.created["group"] += 1

        def create_log_stream(self, **_: Any) -> None:
            self.created["stream"] += 1

        def describe_log_streams(self, **_: Any) -> None:
            return None

        def put_log_events(self, **kwargs: Any) -> dict[str, Any]:
            if self.fail_first:
                self.fail_first = False
                raise FakeClientError("InvalidSequenceTokenException", "token-123")
            if (
                self.expected_token
                and kwargs.get("sequenceToken") != self.expected_token
            ):
                raise FakeClientError(
                    "InvalidSequenceTokenException", self.expected_token
                )
            self.calls.append(kwargs)
            self.expected_token = "token-456"
            return {"nextSequenceToken": "token-456"}

    fake_client = FakeClient()
    monkeypatch.setattr(module, "ClientError", FakeClientError)

    def fake_client_factory(*args: Any, **kwargs: Any) -> FakeClient:
        _ = args, kwargs
        return fake_client

    monkeypatch.setattr(
        module, "boto3", SimpleNamespace(client=lambda *_a, **_k: fake_client)
    )

    async def _to_thread(fn, *a, **k):
        return fn(*a, **k)

    monkeypatch.setattr(
        "fapilog.plugins.sinks.contrib.cloudwatch.asyncio.to_thread", _to_thread
    )

    sink = module.CloudWatchSink(
        config=module.CloudWatchSinkConfig(
            log_group_name="g",
            log_stream_name="s",
            region="us-test-1",
            batch_size=2,
        )
    )
    await sink.start()
    await sink.write({"message": "hello"})
    await sink._flush_batch()
    await sink._flush_batch()
    assert fake_client.calls
    call = fake_client.calls[0]
    assert call["sequenceToken"] == "token-123"
    assert sink._sequence_token == "token-456"
    await sink.stop()


@pytest.mark.asyncio
async def test_datadog_sink_batches_and_formats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from examples.sinks import datadog_sink as module

    posted: list[dict[str, Any]] = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.is_closed = False

        async def post(self, url: str, content: str) -> FakeResponse:
            posted.append(
                {
                    "url": url,
                    "content": content,
                    "headers": self.kwargs.get("headers", {}),
                }
            )
            return FakeResponse()

        async def aclose(self) -> None:
            self.is_closed = True

    monkeypatch.setattr(module, "httpx", SimpleNamespace(AsyncClient=FakeClient))

    sink = module.DatadogSink(
        config=module.DatadogSinkConfig(
            api_key="key", site="datadoghq.eu", service="svc", env="prod", batch_size=2
        )
    )
    await sink.start()
    await sink.write({"message": "hi", "level": "INFO", "foo": "bar"})
    await sink.write({"message": "bye", "level": "ERROR", "user": 1})
    await sink.stop()

    assert posted
    payload = posted[0]["content"]
    assert '"ddsource": "python"' in payload
    assert '"service": "svc"' in payload
    assert '"ddtags": "env:prod"' in payload
    assert "http-intake.logs.datadoghq.eu/api/v2/logs" in posted[0]["url"]
    assert posted[0]["headers"]["DD-API-KEY"] == "key"


@pytest.mark.asyncio
async def test_gcp_logging_sink_logs_structured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from examples.sinks import gcp_logging_sink as module

    entries: list[tuple[dict[str, Any], dict[str, Any]]] = []

    class FakeLogger:
        def log_struct(self, payload: dict[str, Any], **kwargs: Any) -> None:
            entries.append((payload, kwargs))

    class FakeResource:
        def __init__(self, type: str, labels: dict[str, str]) -> None:
            self.type = type
            self.labels = labels

    class FakeClient:
        def __init__(self, **_: Any) -> None:
            self.logged = False

        def logger(self, name: str) -> FakeLogger:
            return FakeLogger()

        def resource(self, type: str, labels: dict[str, str]) -> FakeResource:
            return FakeResource(type, labels)

    module.gcp_logging = SimpleNamespace(Client=lambda **_: FakeClient())
    sink = module.GCPCloudLoggingSink(
        config=module.GCPCloudLoggingConfig(
            log_name="app-log",
            project="proj",
            resource_type="global",
            resource_labels={"location": "us"},
            labels={"env": "dev"},
        )
    )
    await sink.start()
    await sink.write({"message": "hello", "level": "INFO", "foo": "bar"})
    await sink.stop()

    assert entries
    payload, kwargs = entries[0]
    assert payload["message"] == "hello"
    assert kwargs["labels"]["env"] == "dev"
    assert kwargs["resource"].labels["location"] == "us"
