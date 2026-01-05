from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from fapilog.plugins.sinks.http_client import HttpSink, HttpSinkConfig


class _RecordingPool:
    """Stub HttpClientPool that records POST calls."""

    def __init__(self, outcomes: list[Any] | None = None) -> None:
        self.started = False
        self.stopped = False
        self.calls: list[dict[str, Any]] = []
        self._outcomes = outcomes or [
            httpx.Response(200, request=httpx.Request("POST", "http://example.com"))
        ]

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def acquire(self):
        return self

    async def __aenter__(self) -> _RecordingPool:
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
        outcome = (
            self._outcomes.pop(0)
            if self._outcomes
            else httpx.Response(200, request=httpx.Request("POST", url))
        )
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_batch_flushes_on_size_and_stop() -> None:
    pool = _RecordingPool()
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
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

    assert pool.started is True
    assert pool.stopped is True
    assert len(pool.calls) == 2
    assert pool.calls[0]["json"] == [{"n": 1}, {"n": 2}]
    assert pool.calls[1]["json"] == [{"n": 3}]


@pytest.mark.asyncio
async def test_batch_flushes_on_timeout() -> None:
    pool = _RecordingPool()
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            batch_size=10,
            batch_timeout_seconds=0.05,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"n": 1})
    await asyncio.sleep(0.12)  # allow flush loop to run
    await sink.stop()

    assert len(pool.calls) >= 1
    assert pool.calls[0]["json"] == [{"n": 1}]


@pytest.mark.asyncio
async def test_batch_size_one_sends_immediately() -> None:
    pool = _RecordingPool()
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            batch_size=1,
            batch_timeout_seconds=1.0,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"msg": "immediate"})
    await sink.stop()

    assert len(pool.calls) == 1
    assert pool.calls[0]["json"] == [{"msg": "immediate"}]


@pytest.mark.asyncio
async def test_stop_drains_remaining_events() -> None:
    pool = _RecordingPool()
    sink = HttpSink(
        HttpSinkConfig(
            endpoint="https://logs.example.com/api/logs",
            batch_size=4,
            batch_timeout_seconds=5.0,
        ),
        pool=pool,
    )

    await sink.start()
    await sink.write({"n": 1})
    await sink.write({"n": 2})
    await sink.stop()

    assert len(pool.calls) == 1
    assert pool.calls[0]["json"] == [{"n": 1}, {"n": 2}]
