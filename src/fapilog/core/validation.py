"""
Async validation helpers for configuration models.
"""

from __future__ import annotations

import asyncio
import os


async def ensure_path_exists(  # pragma: no cover - used via async config validation
    path: str,
    *,
    message: str = "Path does not exist",
) -> None:
    """Ensure a filesystem path exists using an async-friendly check.

    Uses a thread offload to avoid blocking the event loop for filesystem
    calls.
    Raises FileNotFoundError with provided message if path is missing.
    """

    def _check() -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"{message}: {path}")

    await asyncio.to_thread(_check)
