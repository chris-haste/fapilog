"""
HTTP sink utilities using a pooled httpx.AsyncClient for efficiency.
Provides a simple async HTTP sender that leverages `HttpClientPool` for
connection reuse and bounded concurrency.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.resources import HttpClientPool
from ...core.retry import AsyncRetrier, RetryCallable, RetryConfig
from ...core.serialization import SerializedView
from ..utils import parse_plugin_config
from ._batching import BatchingMixin

__all__ = ["HttpSink", "HttpSinkConfig", "AsyncHttpSender", "BatchFormat"]


class AsyncHttpSender:
    """Thin wrapper around a `HttpClientPool` to send requests efficiently.

    Optional retry/backoff can be enabled by providing a ``RetryConfig`` or any
    callable that matches the retry protocol.
    """

    def __init__(
        self,
        *,
        pool: HttpClientPool,
        default_headers: Mapping[str, str] | None = None,
        retry_config: RetryCallable | RetryConfig | None = None,
    ) -> None:
        self._pool = pool
        self._default_headers = dict(default_headers or {})
        self._retrier: RetryCallable | None = None
        if retry_config is not None:
            self._retrier = (
                AsyncRetrier(retry_config)
                if isinstance(retry_config, RetryConfig)
                else retry_config
            )

    async def post(
        self,
        url: str,
        *,
        json: Any | None = None,
        content: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        merged_headers = dict(self._default_headers)
        if headers:
            merged_headers.update(headers)
        async with self._pool.acquire() as client:

            async def _do_post() -> httpx.Response:
                if content is not None:
                    return await client.post(
                        url,
                        content=content,
                        headers=merged_headers,
                    )
                return await client.post(
                    url,
                    json=json,
                    headers=merged_headers,
                )

            if self._retrier is not None:
                return await self._retrier(_do_post)
            return await _do_post()

    async def post_json(
        self,
        url: str,
        json: Any,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        return await self.post(url, json=json, headers=headers)


class BatchFormat(str, Enum):
    ARRAY = "array"
    NDJSON = "ndjson"
    WRAPPED = "wrapped"


class HttpSinkConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True, arbitrary_types_allowed=True)  # fmt: skip

    endpoint: str
    headers: dict[str, str] = Field(default_factory=dict)
    retry: RetryCallable | RetryConfig | None = None
    timeout_seconds: float = Field(default=5.0, gt=0.0)
    batch_size: int = Field(default=1, ge=1)
    batch_timeout_seconds: float = Field(default=5.0, ge=0.0)
    batch_format: BatchFormat = Field(default=BatchFormat.ARRAY)
    batch_wrapper_key: str = "logs"

    @field_validator("headers", mode="before")
    @classmethod
    def _coerce_headers(cls, value: Mapping[str, str] | None) -> dict[str, str]:
        if value is None:
            return {}
        return dict(value)


class HttpSink(BatchingMixin):
    """Async HTTP sink that POSTs JSON to a configured endpoint."""

    name = "http"

    def __init__(
        self,
        config: HttpSinkConfig | dict | None = None,
        *,
        metrics: Any | None = None,
        pool: HttpClientPool | None = None,
        sender: AsyncHttpSender | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = parse_plugin_config(HttpSinkConfig, config, **kwargs)
        self._config = cfg
        self._pool = pool or HttpClientPool(
            max_size=4,
            timeout=cfg.timeout_seconds,
            acquire_timeout_seconds=2.0,
        )
        self._sender = sender or AsyncHttpSender(
            pool=self._pool,
            default_headers=cfg.headers,
            retry_config=cfg.retry,
        )
        self._metrics = metrics
        self._last_status: int | None = None
        self._last_error: str | None = None
        self._init_batching(cfg.batch_size, cfg.batch_timeout_seconds)

    async def start(self) -> None:
        await self._pool.start()
        await self._start_batching()

    async def stop(self) -> None:
        await self._stop_batching()
        await self._pool.stop()

    async def write(self, entry: dict[str, Any]) -> None:
        await self._enqueue_for_batch(entry)

    async def write_serialized(self, view: SerializedView) -> None:
        """Fast path for pre-serialized payloads."""
        from ...core.diagnostics import warn
        from ...core.errors import SinkWriteError

        try:
            data = json.loads(bytes(view.data))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            warn(
                "http-sink",
                "write_serialized deserialization failed",
                error=str(exc),
                data_size=len(view.data),
                _rate_limit_key="http-sink-deserialize",
            )
            raise SinkWriteError(
                f"Failed to deserialize payload in {self.name}.write_serialized",
                sink_name=self.name,
                cause=exc,
            ) from exc
        await self.write(data)

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        try:
            payload, content_type = self._format_batch(batch)
            headers = dict(self._config.headers)
            headers["Content-Type"] = content_type

            response = await self._sender.post(
                self._config.endpoint,
                json=payload if not isinstance(payload, (bytes, bytearray)) else None,
                content=payload if isinstance(payload, (bytes, bytearray)) else None,
                headers=headers,
            )
            self._last_status = response.status_code
            self._last_error = None
            if response.status_code >= 400:
                from ...core.diagnostics import warn as _warn

                _warn(
                    "http-sink",
                    "batch delivery failed",
                    status_code=response.status_code,
                    endpoint=self._config.endpoint,
                    batch_size=len(batch),
                )
                if self._metrics is not None:
                    await self._metrics.record_events_dropped(len(batch))
                return

            if self._metrics is not None:
                for _ in batch:
                    await self._metrics.record_event_processed()

        except Exception as exc:
            self._last_error = str(exc)
            self._last_status = None
            try:
                from ...core.diagnostics import warn as _warn

                _warn(
                    "http-sink",
                    "batch delivery exception",
                    endpoint=self._config.endpoint,
                    error=str(exc),
                    batch_size=len(batch),
                )
            except Exception:
                pass
            if self._metrics is not None:
                try:
                    await self._metrics.record_events_dropped(len(batch))
                except Exception:
                    pass

    def _format_batch(self, batch: list[dict[str, Any]]) -> tuple[Any, str]:
        fmt = self._config.batch_format
        if fmt == BatchFormat.NDJSON:
            lines = [json.dumps(entry, default=str) for entry in batch]
            return ("\n".join(lines)).encode("utf-8"), "application/x-ndjson"
        if fmt == BatchFormat.WRAPPED:
            return {self._config.batch_wrapper_key: batch}, "application/json"
        return batch, "application/json"

    async def health_check(self) -> bool:
        return (
            self._last_status is not None
            and self._last_status < 400
            and not self._last_error
        )


# Mark public API methods for tooling
_ = HttpSink.health_check  # pragma: no cover

# Plugin metadata for discovery
PLUGIN_METADATA = {
    "name": "http",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.http_client:HttpSink",
    "description": "Async HTTP sink that POSTs JSON to a configured endpoint.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}

# Mark Pydantic validators as used for vulture
_VULTURE_USED: tuple[object, ...] = (HttpSinkConfig._coerce_headers,)
