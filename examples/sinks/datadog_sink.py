from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class DatadogSinkConfig:
    """Configuration for Datadog sink."""

    api_key: str = field(default_factory=lambda: os.getenv("DD_API_KEY", ""))
    site: str = field(default_factory=lambda: os.getenv("DD_SITE", "datadoghq.com"))
    service: str = field(default_factory=lambda: os.getenv("DD_SERVICE", "fapilog"))
    env: str = field(default_factory=lambda: os.getenv("DD_ENV", "dev"))
    source: str = "python"
    batch_size: int = 100
    timeout_seconds: float = 10.0


class DatadogSink:
    """Async sink that sends logs to Datadog over HTTP."""

    name = "datadog"

    def __init__(self, config: DatadogSinkConfig | None = None) -> None:
        self._config = config or DatadogSinkConfig()
        self._client: httpx.AsyncClient | None = None
        self._url = f"https://http-intake.logs.{self._config.site}/api/v2/logs"
        self._batch: list[dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=self._config.timeout_seconds,
            headers={
                "DD-API-KEY": self._config.api_key,
                "Content-Type": "application/json",
            },
        )

    async def stop(self) -> None:
        await self._flush_batch()
        if self._client:
            await self._client.aclose()

    async def write(self, entry: dict) -> None:
        try:
            dd_entry = {
                "message": entry.get("message", ""),
                "ddsource": self._config.source,
                "ddtags": f"env:{self._config.env}",
                "service": self._config.service,
                "status": self._level_to_status(entry.get("level", "INFO")),
                **{k: v for k, v in entry.items() if k not in ("message", "level")},
            }

            flush_now = False
            async with self._batch_lock:
                self._batch.append(dd_entry)
                if len(self._batch) >= self._config.batch_size:
                    flush_now = True
            if flush_now:
                await self._flush_batch()
        except Exception:
            return None

    async def _flush_batch(self) -> None:
        async with self._batch_lock:
            if not self._batch or not self._client:
                return
            batch = self._batch[:]
            self._batch = []

        try:
            await self._client.post(
                self._url,
                content=json.dumps(batch),
            )
        except Exception:
            return None

    def _level_to_status(self, level: str) -> str:
        mapping = {
            "DEBUG": "debug",
            "INFO": "info",
            "WARNING": "warn",
            "WARN": "warn",
            "ERROR": "error",
            "CRITICAL": "critical",
        }
        return mapping.get(level.upper(), "info")

    async def health_check(self) -> bool:
        return self._client is not None and not self._client.is_closed


PLUGIN_METADATA = {
    "name": "datadog",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "examples.sinks.datadog_sink:DatadogSink",
    "description": "Datadog Logs HTTP sink.",
    "author": "Fapilog Examples",
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
    "dependencies": ["httpx>=0.24.0"],
}
