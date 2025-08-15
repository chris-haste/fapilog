from __future__ import annotations

from typing import Protocol, runtime_checkable

from .mmap_persistence import MemoryMappedPersistence, PersistenceStats


@runtime_checkable
class BaseSink(Protocol):
    """Authoring contract for sinks that emit finalized log entries.

    Expectations:
    - Async-first: methods are `async def` and must not block the event loop for
      long operations (perform I/O via threads or native async libraries).
    - Resilient: exceptions MUST be contained; never allow sink errors to crash
      the core pipeline. If an error occurs, swallow it or emit diagnostics.
    - Deterministic output: each invocation of ``write`` produces one record in
      the configured destination.
    - Concurrency: implementations should be safe to call from multiple tasks or
      protect internal state with an ``asyncio.Lock``.

    Lifecycle:
    - ``start`` and ``stop`` are optional hooks. If implemented, they should be
      idempotent and tolerate repeated calls.
    """

    async def start(self) -> None:  # Optional lifecycle hook
        """Initialize resources for the sink.

        If unimplemented, the default no-op is acceptable. Implementations that
        allocate resources (files, connections) should do so here and must not
        raise upstream.
        """

    async def stop(self) -> None:  # Optional lifecycle hook
        """Flush and release resources for the sink.

        Implementations must contain all exceptions. This hook should be safe to
        call multiple times.
        """

    async def write(self, _entry: dict) -> None:  # noqa: ARG002, D401
        """Emit a single structured JSON-serializable mapping.

        Args:
            _entry: Finalized event mapping. Implementations may serialize to
                bytes/JSONL or transform to destination-native format.

        Notes:
        - Must never raise upstream; contain errors internally.
        - Keep per-call critical sections short; avoid event loop stalls.
        """
        ...


__all__ = [
    "BaseSink",
    "MemoryMappedPersistence",
    "PersistenceStats",
]
