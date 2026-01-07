from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.sinks.http_client import HttpSink, HttpSinkConfig


class _StubPool:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def acquire(self):
        return self

    async def __aenter__(self) -> _StubPool:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        content: bytes | None = None,
        headers: Any = None,
    ) -> httpx.Response:
        self.calls.append(
            {"url": url, "json": json, "content": content, "headers": headers}
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _CountingRetry:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return await func(*args, **kwargs)


@pytest.mark.asyncio
async def test_http_sink_success_records_metrics() -> None:
    pool = _StubPool([httpx.Response(200, json={"ok": True})])
    metrics = MetricsCollector(enabled=False)
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            batch_size=1,
        ),
        pool=pool,
        metrics=metrics,
    )

    await sink.start()
    await sink.write({"message": "hello"})
    await sink.stop()

    assert pool.started is True
    assert pool.stopped is True
    assert pool.calls
    # Metrics collector tracks processed even when disabled (accumulates batch size)
    assert metrics._state.events_processed == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_http_sink_warns_on_status_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[dict[str, Any]] = []
    monkeypatch.setenv("PYTHONASYNCIODEBUG", "0")

    def _warn(component: str, message: str, **fields: Any) -> None:
        warnings.append({"component": component, "message": message, **fields})

    with patch("fapilog.core.diagnostics.warn", side_effect=_warn):
        sink = HttpSink(
            HttpSinkConfig(
                endpoint="https://logs.example.com/api/logs",
                batch_size=1,
            ),
            pool=_StubPool(
                [httpx.Response(500, json={"error": "boom"})],
            ),
        )
        await sink.start()
        await sink.write({"message": "hello"})
        await sink.stop()

    assert warnings
    assert warnings[0]["component"] == "http-sink"
    assert warnings[0]["status_code"] == 500
    assert sink._metrics is None or sink._metrics._state.events_processed == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_http_sink_warns_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[dict[str, Any]] = []

    def _warn(component: str, message: str, **fields: Any) -> None:
        warnings.append({"component": component, "message": message, **fields})

    with patch("fapilog.core.diagnostics.warn", side_effect=_warn):
        sink = HttpSink(
            HttpSinkConfig(
                endpoint="https://logs.example.com/api/logs",
                batch_size=1,
            ),
            pool=_StubPool([httpx.ConnectTimeout("boom")]),
        )
        await sink.start()
        await sink.write({"message": "hello"})
        await sink.stop()

    assert warnings
    assert warnings[0]["component"] == "http-sink"
    assert "boom" in warnings[0]["error"]
    assert sink._last_error is not None


@pytest.mark.asyncio
async def test_http_sink_accepts_retry_callable() -> None:
    retry = _CountingRetry()
    pool = _StubPool([httpx.Response(200, json={"ok": True})])
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            retry=retry,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"message": "hello"})
    await sink.stop()

    assert retry.calls == 1
    assert pool.calls


@pytest.mark.asyncio
async def test_http_sink_retries_on_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    from fapilog.core.retry import RetryConfig

    warnings: list[dict[str, Any]] = []

    def _warn(component: str, message: str, **fields: Any) -> None:
        warnings.append({"component": component, "message": message, **fields})

    # First call raises, second succeeds via AsyncHttpSender retry
    outcomes = [TimeoutError("timeout"), httpx.Response(200, json={"ok": True})]
    pool = _StubPool(outcomes)
    with patch("fapilog.core.diagnostics.warn", side_effect=_warn):
        sink = HttpSink(
            HttpSinkConfig(
                endpoint="https://logs.example.com/api/logs",
                retry=RetryConfig(max_attempts=2, base_delay=0.0),
            ),
            pool=pool,
        )
        await sink.start()
        await sink.write({"message": "hello"})
        await sink.stop()

    # Should have attempted twice
    assert len(pool.calls) == 2
    assert sink._last_status == 200
    # Retry swallowed the first failure; warnings may or may not be emitted


@pytest.mark.asyncio
async def test_http_sink_retry_metrics_and_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retryable error should back off once and increment metrics only on success."""
    from fapilog.core.retry import RetryConfig

    metrics = MetricsCollector(enabled=False)
    timings: list[float] = []
    sleep_calls: list[float] = []

    class TimedPool(_StubPool):
        async def post(
            self,
            url: str,
            *,
            json: Any | None = None,
            content: bytes | None = None,
            headers: Any = None,
        ) -> httpx.Response:
            timings.append(asyncio.get_event_loop().time())
            return await super().post(url, json=json, content=content, headers=headers)

    # Retryable then success
    outcomes = [TimeoutError("timeout"), httpx.Response(200, json={"ok": True})]
    pool = TimedPool(outcomes)

    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            retry=RetryConfig(max_attempts=2, base_delay=0.01),
        ),
        pool=pool,
        metrics=metrics,
    )
    with patch(
        "fapilog.core.retry.asyncio.sleep", side_effect=lambda d: sleep_calls.append(d)
    ):
        await sink.start()
        await sink.write({"message": "hello"})
        await sink.stop()

    assert len(pool.calls) == 2
    # Backoff should trigger a sleep call near base_delay
    assert sleep_calls
    assert sleep_calls[0] >= 0.0
    # Metrics should increment only once (on success)
    assert metrics._state.events_processed == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_http_sink_health_check_and_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[dict[str, Any]] = []

    def _warn(component: str, message: str, **fields: Any) -> None:
        warnings.append({"component": component, "message": message, **fields})

    outcomes = [
        httpx.Response(503, text="down"),
        httpx.Response(200, json={"ok": True}),
    ]
    pool = _StubPool(outcomes)
    sink = HttpSink(
        HttpSinkConfig(endpoint="https://logs.example.com/api/logs"),
        pool=pool,
    )
    with patch("fapilog.core.diagnostics.warn", side_effect=_warn):
        await sink.start()
        await sink.write({"message": "first"})
        assert sink._last_status == 503
        assert warnings and warnings[0].get("status_code") == 503
        # health should be false after failure
        assert await sink.health_check() is False

        await sink.write({"message": "second"})
        assert sink._last_status == 200
        assert await sink.health_check() is True
        await sink.stop()


# --- Config Parsing Tests ---


@pytest.mark.asyncio
async def test_http_sink_accepts_dict_config_and_coerces() -> None:
    """Dict config with string numbers should be coerced to correct types."""
    pool = _StubPool([httpx.Response(200, json={"ok": True})])
    sink = HttpSink(
        config={
            "endpoint": "https://logs.example.com/api",
            "batch_size": "5",  # String should coerce to int
            "timeout_seconds": "10.0",  # String should coerce to float
        },
        pool=pool,
    )

    await sink.start()
    await sink.write({"message": "test"})
    await sink.stop()

    assert sink._config.batch_size == 5
    assert sink._config.timeout_seconds == 10.0


def test_http_sink_rejects_unknown_config_fields() -> None:
    """Unknown config keys should raise ValidationError."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        HttpSink(
            config={
                "endpoint": "https://logs.example.com",
                "unknown_field": "oops",
            }
        )


def test_http_sink_validates_constraints() -> None:
    """Pydantic Field constraints should be enforced."""
    # batch_size must be >= 1
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        HttpSinkConfig(endpoint="https://example.com", batch_size=0)

    # timeout_seconds must be > 0
    with pytest.raises(ValidationError, match="greater than 0"):
        HttpSinkConfig(endpoint="https://example.com", timeout_seconds=0)


def test_http_sink_requires_endpoint() -> None:
    """Endpoint is required and has no default."""
    with pytest.raises(ValidationError, match="endpoint"):
        HttpSinkConfig()  # type: ignore[call-arg]


def test_http_sink_accepts_kwargs() -> None:
    """Should accept kwargs-style configuration."""
    sink = HttpSink(
        endpoint="https://kwargs.example.com/api",
        batch_size=10,
        timeout_seconds=15.0,
        pool=_StubPool([]),
    )
    assert sink._config.endpoint == "https://kwargs.example.com/api"
    assert sink._config.batch_size == 10
    assert sink._config.timeout_seconds == 15.0


@pytest.mark.asyncio
async def test_http_sink_accepts_loader_format_config() -> None:
    """Loader-style nested config should work."""
    pool = _StubPool([httpx.Response(200)])
    sink = HttpSink(
        config={"config": {"endpoint": "https://nested.example.com", "batch_size": 3}},
        pool=pool,
    )

    assert sink._config.endpoint == "https://nested.example.com"
    assert sink._config.batch_size == 3
