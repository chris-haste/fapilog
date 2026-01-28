"""
Simple webhook sink example.

Demonstrates how to implement a remote sink with retries, diagnostics,
health checks, and optional signing header.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import time
import warnings
from enum import Enum
from typing import Any, Mapping

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.resources import HttpClientPool
from ...core.retry import AsyncRetrier, RetryCallable, RetryConfig
from ...core.serialization import SerializedView
from ...metrics.metrics import MetricsCollector
from ..utils import parse_plugin_config
from ._batching import BatchingMixin

__all__ = ["SignatureMode", "WebhookSink", "WebhookSinkConfig"]


class SignatureMode(str, Enum):
    """Authentication mode for webhook signing."""

    HEADER = "header"  # Legacy: X-Webhook-Secret (deprecated)
    HMAC = "hmac"  # Recommended: X-Fapilog-Signature-256


class WebhookSinkConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True, arbitrary_types_allowed=True)  # fmt: skip

    endpoint: str
    secret: str | None = None
    signature_mode: SignatureMode = Field(
        default=SignatureMode.HMAC,
        description="Authentication mode: 'hmac' (recommended) or 'header' (deprecated)",
    )
    replay_tolerance_seconds: int = Field(
        default=300,
        ge=0,
        description="Recommended replay tolerance for receivers (5 minutes). Receivers should reject requests with timestamps outside this window.",
    )
    headers: dict[str, str] = Field(default_factory=dict)
    retry: RetryCallable | RetryConfig | None = None
    timeout_seconds: float = Field(default=5.0, gt=0.0)
    batch_size: int = Field(default=1, ge=1)
    batch_timeout_seconds: float = Field(default=5.0, ge=0.0)

    @field_validator("headers", mode="before")
    @classmethod
    def _coerce_headers(cls, value: Mapping[str, str] | None) -> dict[str, str]:
        if value is None:
            return {}
        return dict(value)


class WebhookSink(BatchingMixin):
    """Reference remote sink that POSTs JSON payloads to a webhook endpoint."""

    name = "webhook"

    def __init__(
        self,
        config: WebhookSinkConfig | dict | None = None,
        *,
        metrics: MetricsCollector | None = None,
        pool: HttpClientPool | None = None,
        **kwargs: Any,
    ) -> None:
        cfg = parse_plugin_config(WebhookSinkConfig, config, **kwargs)
        self._config = cfg
        self._metrics = metrics
        self._pool = pool or HttpClientPool(
            name="webhook",
            max_size=4,
            timeout=cfg.timeout_seconds,
            acquire_timeout_seconds=2.0,
        )
        if cfg.retry is None:
            self._retrier: RetryCallable | None = None
        elif isinstance(cfg.retry, RetryConfig):
            self._retrier = AsyncRetrier(cfg.retry)
        else:
            self._retrier = cfg.retry
        self._last_status: int | None = None
        self._last_error: str | None = None
        self._init_batching(cfg.batch_size, cfg.batch_timeout_seconds)

    async def start(self) -> None:
        await self._pool.start()
        await self._start_batching()

    async def stop(self) -> None:
        await self._stop_batching()
        await self._pool.stop()

    async def _post(self, payload: Any) -> httpx.Response:
        headers = dict(self._config.headers)
        if self._config.secret:
            if self._config.signature_mode == SignatureMode.HMAC:
                # Compute HMAC-SHA256 of timestamp + JSON payload for replay protection
                timestamp = int(time.time())
                json_body = json.dumps(payload, separators=(",", ":"))
                message = f"{timestamp}.{json_body}".encode()
                signature = _hmac.new(
                    self._config.secret.encode(),
                    message,
                    hashlib.sha256,
                ).hexdigest()
                headers["X-Fapilog-Timestamp"] = str(timestamp)
                headers["X-Fapilog-Signature-256"] = f"sha256={signature}"
            else:
                # Legacy mode - deprecation warning
                warnings.warn(
                    "X-Webhook-Secret header mode is deprecated. "
                    "Use signature_mode='hmac' for HMAC-SHA256 signatures.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                headers.setdefault("X-Webhook-Secret", self._config.secret)
        async with self._pool.acquire() as client:

            async def _do_post() -> httpx.Response:
                return await client.post(
                    self._config.endpoint, json=payload, headers=headers
                )

            if self._retrier:
                return await self._retrier(_do_post)
            return await _do_post()

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
                "webhook-sink",
                "write_serialized deserialization failed",
                error=str(exc),
                data_size=len(view.data),
                _rate_limit_key="webhook-sink-deserialize",
            )
            raise SinkWriteError(
                f"Failed to deserialize payload in {self.name}.write_serialized",
                sink_name=self.name,
                cause=exc,
            ) from exc
        await self.write(data)

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        payload: Any
        if self._config.batch_size <= 1:
            payload = batch[0] if batch else {}
        else:
            payload = batch

        try:
            resp = await self._post(payload)
            self._last_status = resp.status_code
            self._last_error = None
            if resp.status_code >= 400:
                from ...core.diagnostics import warn as _warn

                snippet = None
                try:
                    snippet = resp.text[:256]
                except Exception:
                    snippet = None
                _warn(
                    "webhook-sink",
                    "failed to deliver log",
                    status_code=resp.status_code,
                    endpoint=self._config.endpoint,
                    body=snippet,
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
                    "webhook-sink",
                    "exception while delivering log",
                    endpoint=self._config.endpoint,
                    error=str(exc),
                )
            except Exception:
                pass
            if self._metrics is not None:
                try:
                    await self._metrics.record_events_dropped(len(batch))
                except Exception:
                    pass

    async def health_check(self) -> bool:
        return (
            self._last_error is None
            and self._last_status is not None
            and self._last_status < 400
        )


# Mark public API methods for tooling
_ = WebhookSink.health_check  # pragma: no cover

# Plugin metadata for discovery
PLUGIN_METADATA = {
    "name": "webhook",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.webhook:WebhookSink",
    "description": "Webhook sink that POSTs JSON with optional signing.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}

# Mark Pydantic validators as used for vulture
_VULTURE_USED: tuple[object, ...] = (
    WebhookSinkConfig._coerce_headers,
    SignatureMode.HEADER,  # Used for backward compatibility
)
