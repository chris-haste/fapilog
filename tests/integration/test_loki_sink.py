from __future__ import annotations

import asyncio
import os
import time

import pytest

LOKI_URL = os.getenv("LOKI_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not LOKI_URL, reason="LOKI_URL not set; start Loki to run integration test"
    ),
]


@pytest.mark.asyncio
async def test_loki_sink_push_and_query() -> None:
    import httpx

    from fapilog.plugins.sinks.contrib.loki import LokiSink, LokiSinkConfig

    message = f"loki-test-{int(time.time())}"
    sink = LokiSink(
        LokiSinkConfig(
            url=LOKI_URL,
            labels={"service": "fapilog-integration"},
            batch_size=1,
        )
    )
    await sink.start()
    await sink.write({"level": "INFO", "message": message})
    await sink.stop()

    await asyncio.sleep(1.0)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{LOKI_URL.rstrip('/')}/loki/api/v1/query",
            params={"query": '{service="fapilog-integration"}'},
        )
        assert resp.status_code == 200
        # Parse response body (httpx Response, not Pydantic)
        import json as json_mod

        data: dict = json_mod.loads(resp.content)
        results = data.get("data", {}).get("result", [])
        assert any(message in v for r in results for _, v in r.get("values", []))
