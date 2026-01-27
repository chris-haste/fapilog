from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from ....core import diagnostics
from ....core.circuit_breaker import SinkCircuitBreaker, SinkCircuitBreakerConfig
from ....core.serialization import SerializedView
from ...utils import parse_plugin_config
from .._batching import BatchingMixin


class LokiSinkConfig(BaseModel):
    """Configuration for Grafana Loki sink."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    url: str = Field(
        default_factory=lambda: os.getenv("FAPILOG_LOKI__URL", "http://localhost:3100")
    )
    tenant_id: str | None = Field(
        default_factory=lambda: os.getenv("FAPILOG_LOKI__TENANT_ID")
    )
    labels: dict[str, str] = Field(default_factory=lambda: {"service": "fapilog"})
    label_keys: list[str] = Field(default_factory=lambda: ["level"])
    batch_size: int = Field(default=100, ge=1)
    batch_timeout_seconds: float = Field(default=5.0, gt=0.0)
    timeout_seconds: float = Field(default=10.0, gt=0.0)
    max_retries: int = Field(default=3, ge=0)
    retry_base_delay: float = Field(default=0.5, ge=0.0)
    auth_username: str | None = Field(
        default_factory=lambda: os.getenv("FAPILOG_LOKI__AUTH_USERNAME")
    )
    auth_password: str | None = Field(
        default_factory=lambda: os.getenv("FAPILOG_LOKI__AUTH_PASSWORD")
    )
    auth_token: str | None = Field(
        default_factory=lambda: os.getenv("FAPILOG_LOKI__AUTH_TOKEN")
    )
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = Field(default=5, ge=1)


class LokiSink(BatchingMixin):
    """Grafana Loki sink with batching, labels, and retry."""

    name = "loki"

    def __init__(self, config: LokiSinkConfig | None = None, **kwargs: Any) -> None:
        cfg = parse_plugin_config(LokiSinkConfig, config, **kwargs)
        self._config = cfg
        self._client: httpx.AsyncClient | None = None
        self._circuit_breaker: SinkCircuitBreaker | None = None
        self._push_url = f"{self._config.url.rstrip('/')}/loki/api/v1/push"
        self._init_batching(cfg.batch_size, cfg.batch_timeout_seconds)

    async def start(self) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._config.tenant_id:
            headers["X-Scope-OrgID"] = self._config.tenant_id
        if self._config.auth_token:
            headers["Authorization"] = f"Bearer {self._config.auth_token}"

        auth = None
        if self._config.auth_username and self._config.auth_password:
            auth = httpx.BasicAuth(
                self._config.auth_username, self._config.auth_password
            )

        self._client = httpx.AsyncClient(
            timeout=self._config.timeout_seconds, headers=headers, auth=auth
        )

        if self._config.circuit_breaker_enabled:
            self._circuit_breaker = SinkCircuitBreaker(
                self.name,
                SinkCircuitBreakerConfig(
                    enabled=True,
                    failure_threshold=self._config.circuit_breaker_threshold,
                ),
            )

        await self._start_batching()

    async def stop(self) -> None:
        await self._stop_batching()
        if self._client:
            await self._client.aclose()
            self._client = None

    async def write(self, entry: dict[str, Any]) -> None:
        await self._enqueue_for_batch(entry)

    async def write_serialized(self, view: SerializedView) -> None:
        """Fast path for pre-serialized payloads."""
        from ....core.errors import SinkWriteError

        try:
            log_line = bytes(view.data).decode("utf-8")
        except UnicodeDecodeError as exc:
            diagnostics.warn(
                "loki-sink",
                "write_serialized deserialization failed",
                error=str(exc),
                data_size=len(view.data),
                _rate_limit_key="loki-sink-deserialize",
            )
            raise SinkWriteError(
                f"Failed to deserialize payload in {self.name}.write_serialized",
                sink_name=self.name,
                cause=exc,
            ) from exc
        await self.write({"_raw": log_line, "level": "INFO"})

    async def _send_batch(self, batch: list[dict[str, Any]]) -> None:
        if not batch or self._client is None:
            return
        if self._circuit_breaker and not self._circuit_breaker.should_allow():
            diagnostics.warn(
                "sink",
                "loki circuit open, dropping batch",
                batch_size=len(batch),
                _rate_limit_key="loki-open",
            )
            return

        streams = self._group_by_labels(batch)
        if not streams:
            return
        payload = {"streams": streams}
        await self._push_with_retry(payload, len(batch))

    def _group_by_labels(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for entry in entries:
            labels = dict(self._config.labels)
            for key in self._config.label_keys:
                if key in entry:
                    labels[key] = self._sanitize_label_value(str(entry[key]))

            label_key = json.dumps(labels, sort_keys=True)

            if "_raw" in entry:
                log_line = entry["_raw"]
            else:
                try:
                    log_line = json.dumps(entry, default=str)
                except Exception:
                    log_line = str(entry)

            ts = entry.get("timestamp")
            if isinstance(ts, (int, float)):
                ts_ns = str(int(ts * 1_000_000_000))
            else:
                ts_ns = str(int(time.time() * 1_000_000_000))

            grouped[label_key].append((ts_ns, log_line))

        streams: list[dict[str, Any]] = []
        for label_key, values in grouped.items():
            labels = json.loads(label_key)
            streams.append({"stream": labels, "values": values})
        return streams

    def _sanitize_label_value(self, value: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
        return sanitized[:128]

    async def _push_with_retry(self, payload: dict[str, Any], entry_count: int) -> None:
        if self._client is None:  # Satisfy mypy; caller already checks
            return
        attempts = max(1, int(self._config.max_retries))
        for attempt in range(attempts):
            try:
                response = await self._client.post(self._push_url, json=payload)
                if response.status_code == 204:
                    if self._circuit_breaker:
                        self._circuit_breaker.record_success()
                    return

                if response.status_code == 429:
                    delay = self._config.retry_base_delay * (2**attempt)
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            pass
                    diagnostics.warn(
                        "sink",
                        "loki rate limited",
                        delay=delay,
                        attempt=attempt + 1,
                        _rate_limit_key="loki-429",
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code in (400, 401, 403):
                    diagnostics.warn(
                        "sink",
                        "loki client error",
                        status=response.status_code,
                        body=response.text[:200],
                        entries=entry_count,
                        _rate_limit_key="loki-client",
                    )
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure()
                    return

                diagnostics.warn(
                    "sink",
                    "loki push failed",
                    status=response.status_code,
                    attempt=attempt + 1,
                    _rate_limit_key="loki-fail",
                )
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()
            except Exception as exc:
                diagnostics.warn(
                    "sink",
                    "loki exception",
                    error=str(exc),
                    attempt=attempt + 1,
                    _rate_limit_key="loki-exc",
                )
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()

            if attempt < attempts - 1:
                await asyncio.sleep(self._config.retry_base_delay * (2**attempt))

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        if self._circuit_breaker and self._circuit_breaker.is_open:
            return False
        try:
            resp = await self._client.get(f"{self._config.url.rstrip('/')}/ready")
            return resp.status_code == 200
        except Exception:
            return False


PLUGIN_METADATA = {
    "name": "loki",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "fapilog.plugins.sinks.contrib.loki:LokiSink",
    "description": "Grafana Loki sink with batching, labels, and retry/backoff.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
    "dependencies": [],
}
