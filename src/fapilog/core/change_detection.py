"""
Configuration change detection utilities.
Provides lightweight filesystem change detection without external deps.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Tuple

FileSignature = Tuple[int, float, str]


@dataclass
class ChangeEvent:
    path: str
    previous: FileSignature | None
    current: FileSignature
    timestamp: datetime


def _hash_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


async def compute_file_signature(path: str) -> FileSignature:
    """Compute a stable signature for a file: (size, mtime, sha256)."""

    def _compute(p: str) -> FileSignature:
        file_path = Path(p)
        data = file_path.read_bytes()
        stat = file_path.stat()
        return (stat.st_size, stat.st_mtime, _hash_bytes(data))

    return await asyncio.to_thread(_compute, path)


def signatures_differ(a: FileSignature | None, b: FileSignature) -> bool:
    if a is None:
        return True
    return a != b


async def watch_file_changes(
    *,
    path: str,
    interval_seconds: float = 0.5,
    on_change: Callable[[ChangeEvent], Awaitable[None]],
    stop_event: asyncio.Event | None = None,
) -> None:
    """Watch a file for changes and invoke `on_change` when it changes.

    Note: This is a simple polling watcher to avoid extra dependencies.
    """

    previous: FileSignature | None = None
    event = stop_event or asyncio.Event()

    while not event.is_set():
        try:
            current = await compute_file_signature(path)
            if signatures_differ(previous, current):
                ce = ChangeEvent(
                    path=path,
                    previous=previous,
                    current=current,
                    timestamp=datetime.now(timezone.utc),
                )
                previous = current
                await on_change(ce)
        except FileNotFoundError:
            # If missing, just wait and try again (supports atomic replace)
            await asyncio.sleep(interval_seconds)
            continue
        await asyncio.sleep(interval_seconds)
