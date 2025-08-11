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
