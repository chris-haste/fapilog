from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from fapilog import Settings
from fapilog.core import diagnostics
from fapilog.core.circuit_breaker import CircuitState
from fapilog.plugins import loader
from fapilog.plugins.sinks.contrib import loki
from fapilog.plugins.sinks.contrib.loki import LokiSink, LokiSinkConfig


class FakeResponse:
    def __init__(
        self, status_code: int, text: str = "", headers: dict[str, str] | None = None
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeAsyncClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.posts: list[dict[str, Any]] = []
        self.gets: list[dict[str, Any]] = []
        self._post_responses: list[FakeResponse] = []
        self._get_response = FakeResponse(200)

    def queue_post_response(self, resp: FakeResponse) -> None:
        self._post_responses.append(resp)

    async def post(self, url: str, json: dict[str, Any], **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, "json": json, "kwargs": kwargs})
        if self._post_responses:
            return self._post_responses.pop(0)
        return FakeResponse(204)

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.gets.append({"url": url, "kwargs": kwargs})
        return self._get_response

    async def aclose(self) -> None:  # noqa: D401
        return None


@pytest.fixture()
def fake_client(monkeypatch) -> FakeAsyncClient:
    client = FakeAsyncClient()
    monkeypatch.setattr(
        loki,
        "httpx",
        SimpleNamespace(
            AsyncClient=lambda **_k: client, BasicAuth=loki.httpx.BasicAuth
        ),
    )
    return client


@pytest.fixture()
def capture_diagnostics(monkeypatch):
    diagnostics._reset_for_tests()
    monkeypatch.setenv("FAPILOG_CORE__INTERNAL_LOGGING_ENABLED", "true")
    captured: list[dict] = []
    original = diagnostics._writer
    diagnostics.set_writer_for_tests(captured.append)
    yield captured
    diagnostics.set_writer_for_tests(original)


@pytest.mark.asyncio
async def test_batches_by_labels(fake_client: FakeAsyncClient) -> None:
    sink = LokiSink(
        LokiSinkConfig(
            url="http://loki",
            labels={"service": "unit"},
            label_keys=["level"],
            batch_size=2,
        )
    )
    await sink.start()
    await sink.write({"level": "INFO", "message": "a"})
    await sink.write({"level": "ERROR", "message": "b"})
    await sink.stop()

    assert fake_client.posts
    payload = fake_client.posts[0]["json"]
    streams = {json.dumps(s["stream"], sort_keys=True): s for s in payload["streams"]}
    assert len(streams) == 2
    assert streams[json.dumps({"service": "unit", "level": "INFO"}, sort_keys=True)]


@pytest.mark.asyncio
async def test_write_serialized_fast_path(fake_client: FakeAsyncClient) -> None:
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1))
    await sink.start()
    view = loki.SerializedView(data=b'{"msg":"hi"}')
    await sink.write_serialized(view)
    await sink.stop()

    assert fake_client.posts
    values = fake_client.posts[0]["json"]["streams"][0]["values"]
    assert any("hi" in entry[1] for entry in values)


@pytest.mark.asyncio
async def test_rate_limit_retries(fake_client: FakeAsyncClient, monkeypatch) -> None:
    fake_client.queue_post_response(FakeResponse(429, headers={"Retry-After": "0.01"}))
    fake_client.queue_post_response(FakeResponse(204))
    slept: list[float] = []
    original_sleep = asyncio.sleep
    monkeypatch.setattr(
        loki.asyncio, "sleep", lambda s: slept.append(s) or original_sleep(0)
    )

    sink = LokiSink(
        LokiSinkConfig(
            url="http://loki", batch_size=1, max_retries=2, retry_base_delay=0.01
        )
    )
    await sink.start()
    await sink.write({"level": "INFO", "message": "retry"})
    await sink.stop()

    assert fake_client.posts
    assert slept, "expected backoff sleep on 429"


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open(fake_client: FakeAsyncClient) -> None:
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1))
    await sink.start()
    assert sink._circuit_breaker is not None  # noqa: SLF001
    sink._circuit_breaker._state = CircuitState.OPEN  # type: ignore[attr-defined]  # noqa: SLF001
    await sink.write({"message": "skip"})
    await sink.stop()

    assert fake_client.posts == []


def test_settings_env_aliases(monkeypatch) -> None:
    monkeypatch.setenv("FAPILOG_LOKI__URL", "http://env-loki")
    monkeypatch.setenv("FAPILOG_LOKI__TENANT_ID", "tenant-x")
    monkeypatch.setenv("FAPILOG_LOKI__LABEL_KEYS", '["level","component"]')
    monkeypatch.setenv("FAPILOG_LOKI__AUTH_TOKEN", "t123")
    monkeypatch.setenv("FAPILOG_CORE__SINKS", '["loki"]')

    settings = Settings()
    cfg = settings.sink_config.loki

    assert cfg.url == "http://env-loki"
    assert cfg.tenant_id == "tenant-x"
    assert cfg.label_keys == ["level", "component"]
    assert cfg.auth_token == "t123"


def test_loader_registers_loki(fake_client: FakeAsyncClient) -> None:
    plugin = loader.load_plugin("fapilog.sinks", "loki", {})
    assert isinstance(plugin, LokiSink)


@pytest.mark.asyncio
async def test_label_sanitization(fake_client: FakeAsyncClient) -> None:
    sink = LokiSink(
        LokiSinkConfig(
            url="http://loki",
            batch_size=1,
            label_keys=["user"],
            labels={"service": "svc"},
        )
    )
    await sink.start()
    await sink.write({"user": "a@b.c", "message": "hello"})
    await sink.stop()

    payload = fake_client.posts[0]["json"]
    stream = payload["streams"][0]["stream"]
    assert stream["user"] == "a_b_c"


# --- Negative tests for client errors (400/401/403) ---


@pytest.mark.asyncio
async def test_client_error_400_emits_diagnostics(
    fake_client: FakeAsyncClient, capture_diagnostics: list[dict]
) -> None:
    """400 Bad Request should emit diagnostic and not retry."""
    fake_client.queue_post_response(FakeResponse(400, text="invalid labels"))
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1, max_retries=3))
    await sink.start()
    await sink.write({"level": "INFO", "message": "bad"})
    await sink.stop()

    # Should only attempt once (no retry on 400)
    assert len(fake_client.posts) == 1
    # Should emit diagnostic
    assert any("loki client error" in str(d) for d in capture_diagnostics)


@pytest.mark.asyncio
async def test_client_error_401_emits_diagnostics(
    fake_client: FakeAsyncClient, capture_diagnostics: list[dict]
) -> None:
    """401 Unauthorized should emit diagnostic and not retry."""
    fake_client.queue_post_response(FakeResponse(401, text="unauthorized"))
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1, max_retries=3))
    await sink.start()
    await sink.write({"level": "INFO", "message": "auth fail"})
    await sink.stop()

    assert len(fake_client.posts) == 1
    assert any("loki client error" in str(d) for d in capture_diagnostics)


@pytest.mark.asyncio
async def test_client_error_403_emits_diagnostics(
    fake_client: FakeAsyncClient, capture_diagnostics: list[dict]
) -> None:
    """403 Forbidden should emit diagnostic and not retry."""
    fake_client.queue_post_response(FakeResponse(403, text="forbidden"))
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1, max_retries=3))
    await sink.start()
    await sink.write({"level": "INFO", "message": "forbidden"})
    await sink.stop()

    assert len(fake_client.posts) == 1
    assert any("loki client error" in str(d) for d in capture_diagnostics)


# --- Health check tests ---


@pytest.mark.asyncio
async def test_health_check_returns_true_when_ready(
    fake_client: FakeAsyncClient,
) -> None:
    """Health check should return True when Loki /ready returns 200."""
    fake_client._get_response = FakeResponse(200)
    sink = LokiSink(LokiSinkConfig(url="http://loki"))
    await sink.start()

    result = await sink.health_check()

    assert result is True
    assert any("/ready" in g["url"] for g in fake_client.gets)
    await sink.stop()


@pytest.mark.asyncio
async def test_health_check_returns_false_when_not_ready(
    fake_client: FakeAsyncClient,
) -> None:
    """Health check should return False when Loki /ready returns non-200."""
    fake_client._get_response = FakeResponse(503, text="not ready")
    sink = LokiSink(LokiSinkConfig(url="http://loki"))
    await sink.start()

    result = await sink.health_check()

    assert result is False
    await sink.stop()


@pytest.mark.asyncio
async def test_health_check_returns_false_when_not_started() -> None:
    """Health check should return False when sink is not started (no client)."""
    sink = LokiSink(LokiSinkConfig(url="http://loki"))
    # Don't call start()

    result = await sink.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_health_check_returns_false_when_circuit_open(
    fake_client: FakeAsyncClient,
) -> None:
    """Health check should return False when circuit breaker is open."""
    sink = LokiSink(LokiSinkConfig(url="http://loki"))
    await sink.start()
    assert sink._circuit_breaker is not None  # noqa: SLF001
    sink._circuit_breaker._state = CircuitState.OPEN  # type: ignore[attr-defined]  # noqa: SLF001

    result = await sink.health_check()

    assert result is False
    await sink.stop()
