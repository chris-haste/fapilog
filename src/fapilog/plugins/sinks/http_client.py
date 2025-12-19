"""
HTTP sink utilities using a pooled httpx.AsyncClient for efficiency.
Provides a simple async HTTP sender that leverages `HttpClientPool` for
connection reuse and bounded concurrency.
"""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from ...core.resources import HttpClientPool
from ...core.retry import AsyncRetrier, RetryConfig
from ...core.serialization import SerializedView

__all__ = ["HttpSink", "HttpSinkConfig"]


class AsyncHttpSender:
    """Thin wrapper around a `HttpClientPool` to send requests efficiently.

    Optional retry/backoff can be enabled by providing a ``RetryConfig``.
    """

    def __init__(
        self,
        *,
        pool: HttpClientPool,
        default_headers: Mapping[str, str] | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._pool = pool
        self._default_headers = dict(default_headers or {})
        self._retrier: AsyncRetrier | None = None
        if retry_config is not None:
            self._retrier = AsyncRetrier(retry_config)

    async def post_json(
        self,
        url: str,
        json: Any,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        merged_headers = dict(self._default_headers)
        if headers:
            merged_headers.update(headers)
        async with self._pool.acquire() as client:

            async def _do_post() -> httpx.Response:
                return await client.post(url, json=json, headers=merged_headers)

            if self._retrier is not None:
                return await self._retrier.retry(_do_post)
            return await _do_post()


class HttpSinkConfig:
    def __init__(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str] | None = None,
        retry: RetryConfig | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers or {})
        self.retry = retry
        self.timeout_seconds = timeout_seconds


class HttpSink:
    """Async HTTP sink that POSTs JSON to a configured endpoint."""

    def __init__(
        self,
        config: HttpSinkConfig,
        *,
        metrics: Any | None = None,
        pool: HttpClientPool | None = None,
        sender: AsyncHttpSender | None = None,
    ) -> None:
        self._config = config
        self._pool = pool or HttpClientPool(
            max_size=4,
            timeout=config.timeout_seconds,
            acquire_timeout_seconds=2.0,
        )
        self._sender = sender or AsyncHttpSender(
            pool=self._pool,
            default_headers=config.headers,
            retry_config=config.retry,
        )
        self._metrics = metrics
        self._last_status: int | None = None
        self._last_error: str | None = None

    async def start(self) -> None:
        await self._pool.start()

    async def stop(self) -> None:
        await self._pool.stop()

    async def write(self, entry: dict[str, Any]) -> None:
        try:
            response = await self._sender.post_json(self._config.endpoint, json=entry)
            self._last_status = response.status_code
            self._last_error = None
            if response.status_code >= 400:
                from ...core.diagnostics import warn as _warn

                body = None
                try:
                    body = response.text
                except Exception:
                    body = None
                _warn(
                    "http-sink",
                    "failed to deliver log",
                    status_code=response.status_code,
                    endpoint=self._config.endpoint,
                    body=body[:256] if body else None,
                )
                return
            if self._metrics is not None:
                await self._metrics.record_event_processed()
        except Exception as exc:
            self._last_error = str(exc)
            try:
                from ...core.diagnostics import warn as _warn

                _warn(
                    "http-sink",
                    "exception while delivering log",
                    endpoint=self._config.endpoint,
                    error=str(exc),
                )
            except Exception:
                pass

    async def write_serialized(self, view: SerializedView) -> None:
        try:
            import json

            data = json.loads(bytes(view.data))
        except Exception:
            data = None
        if data is not None:
            await self.write(data)
            return
        await self._sender.post_json(
            self._config.endpoint,
            json={"message": "fallback"},
        )

    async def health_check(self) -> bool:
        return (
            self._last_status is not None
            and self._last_status < 400
            and not self._last_error
        )


# Mark public API methods for tooling
_ = HttpSink.health_check  # pragma: no cover
