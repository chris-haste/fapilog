"""
Simple webhook sink example.

Demonstrates how to implement a remote sink with retries, diagnostics,
health checks, and optional signing header.
"""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from ...core.resources import HttpClientPool
from ...core.retry import AsyncRetrier, RetryConfig
from ...core.serialization import SerializedView
from ...metrics.metrics import MetricsCollector

__all__ = ["WebhookSink", "WebhookSinkConfig"]


class WebhookSinkConfig:
    def __init__(
        self,
        *,
        endpoint: str,
        secret: str | None = None,
        headers: Mapping[str, str] | None = None,
        retry: RetryConfig | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.secret = secret
        self.headers = dict(headers or {})
        self.retry = retry
        self.timeout_seconds = timeout_seconds


class WebhookSink:
    """Reference remote sink that POSTs JSON payloads to a webhook endpoint."""

    def __init__(
        self,
        config: WebhookSinkConfig,
        *,
        metrics: MetricsCollector | None = None,
        pool: HttpClientPool | None = None,
    ) -> None:
        self._config = config
        self._metrics = metrics
        self._pool = pool or HttpClientPool(
            name="webhook",
            max_size=4,
            timeout=config.timeout_seconds,
            acquire_timeout_seconds=2.0,
        )
        self._retrier = AsyncRetrier(config.retry) if config.retry else None
        self._last_status: int | None = None
        self._last_error: str | None = None

    async def start(self) -> None:
        await self._pool.start()

    async def stop(self) -> None:
        await self._pool.stop()

    async def _post(self, payload: Any) -> httpx.Response:
        headers = dict(self._config.headers)
        if self._config.secret:
            headers.setdefault("X-Webhook-Secret", self._config.secret)
        async with self._pool.acquire() as client:

            async def _do_post() -> httpx.Response:
                return await client.post(
                    self._config.endpoint, json=payload, headers=headers
                )

            if self._retrier:
                return await self._retrier.retry(_do_post)
            return await _do_post()

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            resp = await self._post(entry)
            self._last_status = resp.status_code
            self._last_error = None
            if resp.status_code >= 400:
                from ...core.diagnostics import warn as _warn

                snippet = None
                try:
                    snippet = resp.text[:256]
                except Exception:
                    snippet = None
                _warn(
                    "webhook-sink",
                    "failed to deliver log",
                    status_code=resp.status_code,
                    endpoint=self._config.endpoint,
                    body=snippet,
                )
                if self._metrics is not None:
                    await self._metrics.record_events_dropped(1)
                return
            if self._metrics is not None:
                await self._metrics.record_event_processed()
        except Exception as exc:
            self._last_error = str(exc)
            try:
                from ...core.diagnostics import warn as _warn

                _warn(
                    "webhook-sink",
                    "exception while delivering log",
                    endpoint=self._config.endpoint,
                    error=str(exc),
                )
            except Exception:
                pass
            if self._metrics is not None:
                await self._metrics.record_events_dropped(1)

    async def write_serialized(self, view: SerializedView) -> None:
        try:
            import json

            data = json.loads(bytes(view.data))
        except Exception:
            data = {"message": "fallback"}
        await self.write(data)

    async def health_check(self) -> bool:
        return (
            self._last_error is None
            and self._last_status is not None
            and self._last_status < 400
        )


# Mark public API methods for tooling
_ = WebhookSink.health_check  # pragma: no cover
