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
