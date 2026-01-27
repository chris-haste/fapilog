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


# --- Additional coverage tests ---


@pytest.mark.asyncio
async def test_tenant_id_header_set(monkeypatch) -> None:
    """Verify X-Scope-OrgID header is set when tenant_id is configured."""
    captured_kwargs: dict[str, Any] = {}

    def capture_client(**kwargs: Any):
        captured_kwargs.update(kwargs)
        return FakeAsyncClient(**kwargs)

    monkeypatch.setattr(
        loki,
        "httpx",
        SimpleNamespace(AsyncClient=capture_client, BasicAuth=loki.httpx.BasicAuth),
    )

    sink = LokiSink(LokiSinkConfig(url="http://loki", tenant_id="my-tenant"))
    await sink.start()

    assert captured_kwargs.get("headers", {}).get("X-Scope-OrgID") == "my-tenant"
    await sink.stop()


@pytest.mark.asyncio
async def test_auth_token_header_set(monkeypatch) -> None:
    """Verify Authorization header is set when auth_token is configured."""
    captured_kwargs: dict[str, Any] = {}

    def capture_client(**kwargs: Any):
        captured_kwargs.update(kwargs)
        return FakeAsyncClient(**kwargs)

    monkeypatch.setattr(
        loki,
        "httpx",
        SimpleNamespace(AsyncClient=capture_client, BasicAuth=loki.httpx.BasicAuth),
    )

    sink = LokiSink(LokiSinkConfig(url="http://loki", auth_token="secret-token"))
    await sink.start()

    assert "Bearer secret-token" in captured_kwargs.get("headers", {}).get(
        "Authorization", ""
    )
    await sink.stop()


@pytest.mark.asyncio
async def test_basic_auth_configured(monkeypatch) -> None:
    """Verify basic auth is set when username and password are configured."""
    captured_kwargs: dict[str, Any] = {}

    def capture_client(**kwargs: Any):
        captured_kwargs.update(kwargs)
        return FakeAsyncClient(**kwargs)

    monkeypatch.setattr(
        loki,
        "httpx",
        SimpleNamespace(AsyncClient=capture_client, BasicAuth=loki.httpx.BasicAuth),
    )

    sink = LokiSink(
        LokiSinkConfig(url="http://loki", auth_username="user", auth_password="pass")
    )
    await sink.start()

    assert captured_kwargs.get("auth") is not None
    await sink.stop()


@pytest.mark.asyncio
async def test_write_serialized_raises_on_invalid_bytes(
    fake_client: FakeAsyncClient,
) -> None:
    """write_serialized should raise SinkWriteError on non-UTF8 bytes (Story 4.53)."""
    from fapilog.core.errors import SinkWriteError

    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1))
    await sink.start()
    # Create a view with invalid UTF-8 bytes
    view = loki.SerializedView(data=b"\xff\xfe invalid utf8")
    with pytest.raises(SinkWriteError) as exc_info:
        await sink.write_serialized(view)
    await sink.stop()

    assert exc_info.value.context.plugin_name == "loki"
    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)


@pytest.mark.asyncio
async def test_timestamp_from_entry(fake_client: FakeAsyncClient) -> None:
    """Timestamp should be taken from entry when present as int/float."""
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1))
    await sink.start()
    # Provide a specific timestamp
    await sink.write({"level": "INFO", "message": "timed", "timestamp": 1609459200.0})
    await sink.stop()

    assert fake_client.posts
    values = fake_client.posts[0]["json"]["streams"][0]["values"]
    # Timestamp should be 1609459200 * 1e9 = 1609459200000000000
    assert values[0][0] == "1609459200000000000"


@pytest.mark.asyncio
async def test_server_error_retries_and_fails(
    fake_client: FakeAsyncClient, capture_diagnostics: list[dict], monkeypatch
) -> None:
    """Server errors (5xx) should be retried and emit diagnostics."""
    fake_client.queue_post_response(FakeResponse(500, text="server error"))
    fake_client.queue_post_response(FakeResponse(500, text="server error"))
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
    await sink.write({"level": "INFO", "message": "fail"})
    await sink.stop()

    # Should have retried
    assert len(fake_client.posts) == 2
    assert any("loki push failed" in str(d) for d in capture_diagnostics)
    assert slept  # Should have slept between retries


@pytest.mark.asyncio
async def test_exception_during_push(
    fake_client: FakeAsyncClient, capture_diagnostics: list[dict], monkeypatch
) -> None:
    """Exceptions during push should be caught and emit diagnostics."""

    async def raise_error(*args, **kwargs):
        raise ConnectionError("network failure")

    fake_client.post = raise_error
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
    await sink.write({"level": "INFO", "message": "error"})
    await sink.stop()

    assert any("loki exception" in str(d) for d in capture_diagnostics)


@pytest.mark.asyncio
async def test_retry_after_invalid_value(
    fake_client: FakeAsyncClient, monkeypatch
) -> None:
    """Invalid Retry-After header should fall back to default backoff.

    When Retry-After header contains an invalid value (non-numeric),
    the sink should fall back to the configured retry_base_delay.
    """
    fake_client.queue_post_response(
        FakeResponse(429, headers={"Retry-After": "not-a-number"})
    )
    fake_client.queue_post_response(FakeResponse(204))
    slept: list[float] = []
    original_sleep = asyncio.sleep

    async def tracking_sleep(s: float) -> None:
        slept.append(s)
        # Skip actual sleep for test speed
        await original_sleep(0)

    monkeypatch.setattr(loki.asyncio, "sleep", tracking_sleep)

    sink = LokiSink(
        LokiSinkConfig(
            url="http://loki", batch_size=1, max_retries=2, retry_base_delay=0.5
        )
    )
    await sink.start()
    await sink.write({"level": "INFO", "message": "retry"})
    await sink.stop()

    # Should have used default backoff (0.5 * 2^0 = 0.5)
    # Check that at least one sleep was with the expected base delay
    assert slept, "Expected at least one sleep call during retry"
    assert 0.5 in slept, f"Expected 0.5s backoff delay in {slept}"


@pytest.mark.asyncio
async def test_health_check_exception_returns_false(monkeypatch) -> None:
    """Health check should return False when an exception occurs."""

    class ErrorClient:
        async def get(self, url: str, **kwargs):
            raise ConnectionError("cannot connect")

        async def aclose(self):
            pass

    monkeypatch.setattr(
        loki,
        "httpx",
        SimpleNamespace(
            AsyncClient=lambda **_k: ErrorClient(), BasicAuth=lambda *a: None
        ),
    )

    sink = LokiSink(LokiSinkConfig(url="http://loki", circuit_breaker_enabled=False))
    await sink.start()

    result = await sink.health_check()

    assert result is False
    await sink.stop()


@pytest.mark.asyncio
async def test_circuit_breaker_disabled(fake_client: FakeAsyncClient) -> None:
    """Sink should work without circuit breaker when disabled."""
    sink = LokiSink(
        LokiSinkConfig(url="http://loki", batch_size=1, circuit_breaker_enabled=False)
    )
    await sink.start()
    assert sink._circuit_breaker is None  # noqa: SLF001
    await sink.write({"level": "INFO", "message": "no breaker"})
    await sink.stop()

    assert fake_client.posts


def test_plugin_metadata_exists() -> None:
    """PLUGIN_METADATA should be properly defined."""
    from fapilog.plugins.sinks.contrib.loki import PLUGIN_METADATA

    assert PLUGIN_METADATA["name"] == "loki"
    assert PLUGIN_METADATA["plugin_type"] == "sink"
    assert "version" in PLUGIN_METADATA
    assert "entry_point" in PLUGIN_METADATA


@pytest.mark.asyncio
async def test_send_batch_no_client() -> None:
    """_send_batch should return early if client is None."""
    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1))
    # Don't start - client will be None
    await sink._send_batch([{"level": "INFO"}])  # noqa: SLF001
    # Should not raise, just return


@pytest.mark.asyncio
async def test_json_serialization_fallback(fake_client: FakeAsyncClient) -> None:
    """Entry with non-serializable value should fall back to str()."""

    class NonSerializable:
        def __repr__(self):
            return "<NonSerializable>"

    sink = LokiSink(LokiSinkConfig(url="http://loki", batch_size=1))
    await sink.start()
    # Object that json.dumps will fail on without default=str
    await sink.write({"level": "INFO", "obj": NonSerializable()})
    await sink.stop()

    assert fake_client.posts
    # Should have serialized using default=str
    values = fake_client.posts[0]["json"]["streams"][0]["values"]
    assert "NonSerializable" in values[0][1]
