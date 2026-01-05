from __future__ import annotations

from typing import Any

import httpx
import pytest

from fapilog.plugins.sinks.http_client import BatchFormat, HttpSink, HttpSinkConfig


class _FormatPool:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def acquire(self):
        return self

    async def __aenter__(self) -> _FormatPool:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        self.calls.append(
            {
                "url": url,
                "json": json,
                "content": content,
                "headers": dict(headers or {}),
            }
        )
        return httpx.Response(200, request=httpx.Request("POST", url))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fmt,expected_header",
    [
        (BatchFormat.ARRAY, "application/json"),
        (BatchFormat.NDJSON, "application/x-ndjson"),
        (BatchFormat.WRAPPED, "application/json"),
    ],
)
async def test_batch_formats_apply_content_type(
    fmt: BatchFormat, expected_header: str
) -> None:
    pool = _FormatPool()
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            batch_size=2,
            batch_timeout_seconds=5.0,
            batch_format=fmt,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"level": "INFO"})
    await sink.write({"level": "INFO"})
    await sink.stop()

    assert pool.calls
    headers = pool.calls[0]["headers"]
    assert headers.get("Content-Type") == expected_header

    if fmt == BatchFormat.NDJSON:
        body = pool.calls[0]["content"]
        assert isinstance(body, (bytes, bytearray))
        assert b"\n" in body
    elif fmt == BatchFormat.WRAPPED:
        assert pool.calls[0]["json"] == {"logs": [{"level": "INFO"}, {"level": "INFO"}]}
    else:
        assert pool.calls[0]["json"] == [{"level": "INFO"}, {"level": "INFO"}]
