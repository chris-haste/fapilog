from __future__ import annotations

from types import SimpleNamespace

import pytest

from fapilog.core.retry import RetryConfig
from fapilog.plugins.sinks.http_client import AsyncHttpSender


class _FakeClient:
    async def post(self, url: str, json, headers):  # type: ignore[no-untyped-def]
        return SimpleNamespace(status_code=200)


class _Pool:
    def __init__(self) -> None:
        self._client = _FakeClient()

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self._client

    async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def acquire(self):  # type: ignore[no-untyped-def]
        return self


@pytest.mark.asyncio
async def test_http_sender_post_json_with_retry() -> None:
    pool = _Pool()  # type: ignore[assignment]
    sender = AsyncHttpSender(pool=pool, retry_config=RetryConfig())
    resp = await sender.post_json("http://x", json={"a": 1}, headers={"h": "v"})
    assert getattr(resp, "status_code", 0) == 200
