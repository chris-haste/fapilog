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
        """Return runtime info targeting the diagnostics semantic group.

        Returns:
            Dict with structure: {"diagnostics": {"host": ..., "pid": ..., ...}}
        """
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
        return {"diagnostics": compact}

    async def health_check(self) -> bool:
        """Verify runtime info can be collected.

        Checks that essential system calls succeed.
        """
        try:
            # Verify we can get hostname (most likely to fail in containers)
            _ = socket.gethostname()
            return True
        except Exception:
            return False


__all__ = ["RuntimeInfoEnricher"]

# Minimal PLUGIN_METADATA for discovery
PLUGIN_METADATA = {
    "name": "runtime_info",
    "version": "1.1.0",
    "plugin_type": "enricher",
    "entry_point": "fapilog.plugins.enrichers.runtime_info:RuntimeInfoEnricher",
    "description": "Adds runtime/system info (host, pid, python) to diagnostics group.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.1",
}
