"""
HTTP sink utilities using a pooled httpx.AsyncClient for efficiency.
Provides a simple async HTTP sender that leverages `HttpClientPool` for
connection reuse and bounded concurrency.
"""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from ...core.resources import HttpClientPool


class AsyncHttpSender:
    """Thin wrapper around a `HttpClientPool` to send requests efficiently."""

    def __init__(
        self,
        *,
        pool: HttpClientPool,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._pool = pool
        self._default_headers = dict(default_headers or {})

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
            return await client.post(url, json=json, headers=merged_headers)
