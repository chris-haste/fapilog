import pytest

import fapilog.core.resources as res
from fapilog.plugins.sinks.http_client import AsyncHttpSender


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        self.calls: list[tuple[str, dict]] = []

    async def post(self, url: str, json=None, headers=None):  # noqa: D401
        self.calls.append((url, {"json": json, "headers": dict(headers or {})}))

        class _Resp:
            status_code = 200

        return _Resp()


@pytest.mark.asyncio
async def test_http_sender_post_json_merges_headers(monkeypatch):
    monkeypatch.setattr(res.httpx, "AsyncClient", FakeClient)

    pool = res.HttpClientPool(max_size=1, acquire_timeout_seconds=0.1)
    sender = AsyncHttpSender(pool=pool, default_headers={"A": "1"})
    resp = await sender.post_json("http://example", {"x": 1}, headers={"B": "2"})
    assert getattr(resp, "status_code", None) == 200

    # Acquire a client to inspect captured calls
    async with pool.acquire() as client:  # type: ignore[assignment]
        # Our FakeClient instance is reused in pool; inspect calls captured
        assert isinstance(client, FakeClient)
        assert client.calls
        url, payload = client.calls[-1]
        assert url.startswith("http://example")
        assert payload["json"] == {"x": 1}
        # Headers should include both A and B
        assert payload["headers"].get("A") == "1"
        assert payload["headers"].get("B") == "2"
