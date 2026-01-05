from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

try:  # Optional dependency
    from google.cloud import logging as gcp_logging  # type: ignore
except Exception:  # pragma: no cover - optional import
    gcp_logging = None


@dataclass
class GCPCloudLoggingConfig:
    """Configuration for Google Cloud Logging sink."""

    log_name: str = "fapilog"
    project: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    credentials_path: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    resource_type: str = "global"
    resource_labels: dict[str, str] | None = field(default_factory=dict)
    labels: dict[str, str] | None = field(default_factory=dict)


class GCPCloudLoggingSink:
    """Sink that writes structured logs to Google Cloud Logging."""

    name = "gcp_cloud_logging"

    def __init__(self, config: GCPCloudLoggingConfig | None = None) -> None:
        self._config = config or GCPCloudLoggingConfig()
        self._client: Any = None
        self._logger: Any = None
        self._resource: Any = None

    async def start(self) -> None:
        if gcp_logging is None:
            raise ImportError(
                "google-cloud-logging is required for GCPCloudLoggingSink"
            )
        client_kwargs: dict[str, Any] = {}
        if self._config.project:
            client_kwargs["project"] = self._config.project
        if self._config.credentials_path:
            from google.oauth2 import service_account  # type: ignore

            credentials = service_account.Credentials.from_service_account_file(
                self._config.credentials_path
            )
            client_kwargs["credentials"] = credentials
        self._client = gcp_logging.Client(**client_kwargs)
        self._logger = self._client.logger(self._config.log_name)
        labels = self._config.resource_labels or {}
        self._resource = self._client.resource(
            self._config.resource_type, labels=labels
        )

    async def stop(self) -> None:
        return None

    async def write(self, entry: dict) -> None:
        if not self._logger:
            return None
        payload = dict(entry)
        labels = self._config.labels or {}
        try:
            await asyncio.to_thread(
                self._logger.log_struct,
                payload,
                resource=self._resource,
                labels=labels,
            )
        except Exception:
            return None

    async def health_check(self) -> bool:
        return self._logger is not None


PLUGIN_METADATA = {
    "name": "gcp_cloud_logging",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "examples.sinks.gcp_logging_sink:GCPCloudLoggingSink",
    "description": "Google Cloud Logging sink.",
    "author": "Fapilog Examples",
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
    "dependencies": ["google-cloud-logging>=3.8.0"],
}
