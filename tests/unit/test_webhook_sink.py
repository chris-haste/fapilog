from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from fapilog.metrics.metrics import MetricsCollector
from fapilog.plugins.sinks.webhook import WebhookSink, WebhookSinkConfig


class _StubPool:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, Any, Any]] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(
        self,
        url: str,
        json: Any = None,
        content: bytes | None = None,
        headers: Any = None,
    ) -> httpx.Response:
        payload = json if json is not None else content
        self.calls.append((url, payload, headers))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_webhook_sink_success_and_headers() -> None:
    pool = _StubPool([httpx.Response(200, json={"ok": True})])
    metrics = MetricsCollector(enabled=False)
    sink = WebhookSink(
        WebhookSinkConfig(
            endpoint="https://hooks.example.com",
            secret="abc123",
            headers={"X-Test": "1"},
        ),
        pool=pool,
        metrics=metrics,
    )
    await sink.start()
    await sink.write({"message": "hello"})
    await sink.stop()

    assert pool.started and pool.stopped
    assert metrics._state.events_processed == 1  # type: ignore[attr-defined]
    assert pool.calls
    _, _, headers = pool.calls[0]
    assert headers.get("X-Webhook-Secret") == "abc123"
    assert headers.get("X-Test") == "1"


@pytest.mark.asyncio
async def test_webhook_sink_failure_drops_and_warns() -> None:
    warnings: list[dict[str, Any]] = []

    def _warn(component: str, message: str, **fields: Any) -> None:
        warnings.append({"component": component, "message": message, **fields})

    pool = _StubPool([httpx.Response(500, text="fail")])
    sink = WebhookSink(
        WebhookSinkConfig(endpoint="https://hooks.example.com"),
        pool=pool,
    )
    with patch("fapilog.core.diagnostics.warn", side_effect=_warn):
        await sink.start()
        await sink.write({"message": "fail"})
        await sink.stop()

    assert warnings
    assert warnings[0]["component"] == "webhook-sink"
    assert warnings[0]["status_code"] == 500


@pytest.mark.asyncio
async def test_webhook_sink_exception_health() -> None:
    pool = _StubPool(
        [httpx.ConnectTimeout("timeout"), httpx.Response(200, json={"ok": True})]
    )
    sink = WebhookSink(
        WebhookSinkConfig(endpoint="https://hooks.example.com"),
        pool=pool,
    )
    await sink.start()
    await sink.write({"message": "first"})
    assert await sink.health_check() is False
    await sink.write({"message": "second"})
    assert await sink.health_check() is True
    await sink.stop()


@pytest.mark.asyncio
async def test_webhook_sink_serialized_fallback_and_metrics() -> None:
    pool = _StubPool([httpx.Response(200, json={"ok": True})])
    metrics = MetricsCollector(enabled=True)
    sink = WebhookSink(
        WebhookSinkConfig(endpoint="https://hooks.example.com"),
        pool=pool,
        metrics=metrics,
    )

    class _BadView:
        def __init__(self, data: bytes) -> None:
            self.data = memoryview(data)

    await sink.start()
    await sink.write_serialized(_BadView(b"not-json"))
    await sink.stop()

    assert pool.calls and metrics._state.events_processed == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_webhook_sink_batches_and_flushes() -> None:
    pool = _StubPool([httpx.Response(200), httpx.Response(200)])
    sink = WebhookSink(
        WebhookSinkConfig(
            endpoint="https://hooks.example.com",
            secret="abc123",
            batch_size=2,
            batch_timeout_seconds=5.0,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"n": 1})
    await sink.write({"n": 2})
    await sink.write({"n": 3})
    await sink.stop()

    assert len(pool.calls) == 2
    assert pool.calls[0][1] == [{"n": 1}, {"n": 2}]
    assert pool.calls[1][1] == [{"n": 3}]
    # Secret header should be applied to batch requests
    assert pool.calls[0][2].get("X-Webhook-Secret") == "abc123"


@pytest.mark.asyncio
async def test_webhook_sink_flushes_on_timeout() -> None:
    pool = _StubPool([httpx.Response(200)])
    sink = WebhookSink(
        WebhookSinkConfig(
            endpoint="https://hooks.example.com",
            batch_size=10,
            batch_timeout_seconds=0.05,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"n": 1})
    await asyncio.sleep(0.12)
    await sink.stop()

    assert pool.calls
    assert pool.calls[0][1] == [{"n": 1}]
