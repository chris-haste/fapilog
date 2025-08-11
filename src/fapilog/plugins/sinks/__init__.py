from __future__ import annotations

from typing import Protocol, runtime_checkable

from .mmap_persistence import MemoryMappedPersistence, PersistenceStats


@runtime_checkable
class BaseSink(Protocol):
    """Base async sink interface.

    Sinks are responsible for emitting finalized log entries to an external
    destination (e.g., stdout, files, HTTP, SIEMs). Implementations should be
    non-blocking and resilient; errors must be contained and must not crash the
    core pipeline.

    Minimal contract aligns with AC: `write()` plus optional lifecycle hooks.
    """

    async def start(self) -> None:  # Optional lifecycle hook
        ...

    async def stop(self) -> None:  # Optional lifecycle hook
        ...

    async def write(self, _entry: dict) -> None:  # noqa: ARG002, D401
        """Write a single structured log entry to the sink destination."""
        ...


__all__ = [
    "BaseSink",
    "MemoryMappedPersistence",
    "PersistenceStats",
]
