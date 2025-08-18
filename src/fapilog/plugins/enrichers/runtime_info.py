from __future__ import annotations

import os
import platform
import socket
from typing import Any


class RuntimeInfoEnricher:
    name = "runtime_info"

    async def start(self) -> None:  # pragma: no cover - optional
        return None

    async def stop(self) -> None:  # pragma: no cover - optional
        return None

    async def enrich(self, event: dict[str, Any]) -> dict[str, Any]:
        info = {
            "service": os.getenv("FAPILOG_SERVICE", "fapilog"),
            "env": os.getenv("FAPILOG_ENV", os.getenv("ENV", "dev")),
            "version": os.getenv("FAPILOG_VERSION"),
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "python": platform.python_version(),
        }
        # Compact: drop Nones
        compact = {k: v for k, v in info.items() if v is not None}
        return compact


__all__ = ["RuntimeInfoEnricher"]

# Minimal PLUGIN_METADATA for discovery
PLUGIN_METADATA = {
    "name": "runtime-info-enricher",
    "version": "1.0.0",
    "plugin_type": "enricher",
    "entry_point": "fapilog.plugins.enrichers.runtime_info:RuntimeInfoEnricher",
    "description": "Adds runtime/system information such as host, pid, and python version.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "3.0.0"},
    "api_version": "1.0",
}
