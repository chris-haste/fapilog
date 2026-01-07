from __future__ import annotations

import pytest

from fapilog.plugins.sinks.http_client import AsyncHttpSender


class _SpyRetry:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return await func(*args, **kwargs)


class _Pool:
    def __init__(self) -> None:
        self._client = _ClientStub()

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self._client

    async def __aexit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def acquire(self):  # type: ignore[no-untyped-def]
        return self


class _ClientStub:
    def __init__(self) -> None:
        self.calls = 0

    async def post(self, url: str, json, headers):  # type: ignore[no-untyped-def]
        self.calls += 1
        return type("Resp", (), {"status_code": 200})()


@pytest.mark.asyncio
async def test_retry_callable_protocol_used_by_sender() -> None:
    pool = _Pool()  # type: ignore[assignment]
    retry = _SpyRetry()
    sender = AsyncHttpSender(pool=pool, retry_config=retry)

    resp = await sender.post_json("http://example.com", json={"hello": "world"})

    assert resp.status_code == 200
    assert retry.calls == 1
    assert pool._client.calls == 1


@pytest.mark.asyncio
async def test_tenacity_adapter_example_if_available() -> None:
    tenacity = pytest.importorskip("tenacity")

    class TenacityAdapter:
        def __init__(self, retrying: tenacity.AsyncRetrying) -> None:
            self._retrying = retrying

        async def __call__(self, func, *args, **kwargs):  # type: ignore[no-untyped-def]
            async for attempt in self._retrying:
                with attempt:
                    return await func(*args, **kwargs)

    attempts = 0

    async def sometimes_fails() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("try again")
        return "ok"

    adapter = TenacityAdapter(
        tenacity.AsyncRetrying(
            stop=tenacity.stop_after_attempt(3),
            wait=tenacity.wait_exponential(multiplier=0),
        )
    )

    result = await adapter(sometimes_fails)

    assert result == "ok"
    assert attempts == 2
