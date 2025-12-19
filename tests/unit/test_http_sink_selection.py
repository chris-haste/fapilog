from __future__ import annotations

from typing import Any

import pytest

from fapilog import get_logger


@pytest.mark.asyncio
async def test_get_logger_prefers_http_sink_over_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[Any] = []

    class FakeHttpSink:
        def __init__(self, config: Any, metrics: Any = None) -> None:
            messages.append(config.endpoint)
            self._started = False

        async def start(self) -> None:
            self._started = True

        async def write(self, entry: dict[str, Any]) -> None:
            messages.append(entry)
            return None

        async def write_serialized(self, entry: Any) -> None:
            messages.append(entry)
            return None

    monkeypatch.setenv("FAPILOG_HTTP__ENDPOINT", "https://logs.example.com/api/logs")
    monkeypatch.setenv("FAPILOG_FILE__DIRECTORY", "/tmp/should_not_use")
    monkeypatch.setattr("fapilog.plugins.sinks.http_client.HttpSink", FakeHttpSink)
    # If file sink is constructed, raise to catch precedence regression
    monkeypatch.setattr(
        "fapilog.plugins.sinks.rotating_file.RotatingFileSink",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("file sink used")),
    )

    logger = get_logger("http-selection")
    logger.info("hello", key="value")
    await logger.stop_and_drain()

    assert any(isinstance(m, dict) and m.get("message") == "hello" for m in messages)
    assert "https://logs.example.com/api/logs" in messages[0]


@pytest.mark.asyncio
async def test_http_sink_env_headers_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeHttpSink:
        def __init__(self, config: Any, metrics: Any = None) -> None:
            captured["config"] = config
            self._started = False

        async def start(self) -> None:
            self._started = True

        async def write(self, entry: dict[str, Any]) -> None:
            return None

    monkeypatch.setenv("FAPILOG_HTTP__ENDPOINT", "https://logs.example.com/api/logs")
    monkeypatch.setenv(
        "FAPILOG_HTTP__HEADERS_JSON",
        '{"Authorization": "Bearer token", "X-Test": "1"}',
    )
    monkeypatch.setenv("FAPILOG_HTTP__RETRY_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("FAPILOG_HTTP__RETRY_BACKOFF_SECONDS", "0.3")
    monkeypatch.setenv("FAPILOG_HTTP__TIMEOUT_SECONDS", "7.5")
    monkeypatch.setattr("fapilog.plugins.sinks.http_client.HttpSink", FakeHttpSink)

    logger = get_logger("http-env")
    await logger.stop_and_drain()

    cfg = captured["config"]
    assert cfg.endpoint == "https://logs.example.com/api/logs"
    assert cfg.headers.get("Authorization") == "Bearer token"
    assert cfg.headers.get("X-Test") == "1"
    assert cfg.retry is not None and cfg.retry.max_attempts == 4
    assert cfg.retry.base_delay == 0.3
    assert cfg.timeout_seconds == 7.5
