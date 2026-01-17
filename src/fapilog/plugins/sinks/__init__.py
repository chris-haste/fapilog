from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..loader import register_builtin
from .contrib.cloudwatch import CloudWatchSink
from .contrib.loki import LokiSink
from .contrib.postgres import PostgresSink
from .http_client import HttpSink
from .mmap_persistence import MemoryMappedPersistence, PersistenceStats
from .rotating_file import RotatingFileSink
from .routing import RoutingSink
from .stdout_json import StdoutJsonSink
from .stdout_pretty import StdoutPrettySink
from .webhook import WebhookSink


@runtime_checkable
class BaseSink(Protocol):
    """Authoring contract for sinks that emit finalized log entries.

    Expectations:
    - Async-first: methods are `async def` and must not block the event loop for
      long operations (perform I/O via threads or native async libraries).
    - Error signaling: On write failures, raise ``SinkWriteError`` or return
      ``False`` to trigger fallback behavior and circuit breaker integration.
      The core catches these signals, calls the fallback handler, and continues
      without crashing.
    - Deterministic output: each invocation of ``write`` produces one record in
      the configured destination (on success).
    - Optional fast path: sinks may expose ``write_serialized(view)`` to accept
      pre-serialized payloads when serialize_in_flush=True; if absent, fapilog
      automatically calls ``write`` instead.
    - Concurrency: implementations should be safe to call from multiple tasks or
      protect internal state with an ``asyncio.Lock``.

    Lifecycle:
    - ``start`` and ``stop`` are optional hooks. If implemented, they should be
      idempotent and tolerate repeated calls. These lifecycle methods should
      still contain errors (not propagate them).

    Attributes:
        name: Unique identifier for this sink type (e.g., "stdout_json").
    """

    name: str  # Plugin identifier for discovery and configuration

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

    async def write(self, _entry: dict) -> bool | None:  # noqa: ARG002, D401
        """Emit a single structured JSON-serializable mapping.

        Args:
            _entry: Finalized event mapping. Implementations may serialize to
                bytes/JSONL or transform to destination-native format.

        Returns:
            None or True on success, False on failure (triggers fallback).

        Raises:
            SinkWriteError: On write failure. The core catches this, triggers
                fallback, and increments the circuit breaker.

        Notes:
        - On failure, raise ``SinkWriteError`` (preferred) or return ``False``.
        - Keep per-call critical sections short; avoid event loop stalls.
        - The core pipeline contains errors, so sinks don't crash the logger.
        """
        ...

    async def health_check(self) -> bool:  # pragma: no cover - optional
        """Return True if the sink is healthy. Default: assume healthy."""
        return True


__all__ = [
    "BaseSink",
    "MemoryMappedPersistence",
    "PersistenceStats",
    "CloudWatchSink",
    "LokiSink",
    "PostgresSink",
    "RoutingSink",
]


# Register built-ins with aliases (hyphen/underscore)
register_builtin(
    "fapilog.sinks",
    "stdout_json",
    StdoutJsonSink,
    aliases=["stdout-json"],
)
register_builtin(
    "fapilog.sinks",
    "stdout_pretty",
    StdoutPrettySink,
    aliases=["stdout-pretty"],
)
register_builtin(
    "fapilog.sinks",
    "rotating_file",
    RotatingFileSink,
    aliases=["rotating-file"],
)
register_builtin(
    "fapilog.sinks",
    "http",
    HttpSink,
)
register_builtin(
    "fapilog.sinks",
    "webhook",
    WebhookSink,
)
register_builtin(
    "fapilog.sinks",
    "cloudwatch",
    CloudWatchSink,
    aliases=["cloud-watch"],
)
register_builtin(
    "fapilog.sinks",
    "loki",
    LokiSink,
    aliases=["grafana-loki"],
)
register_builtin(
    "fapilog.sinks",
    "postgres",
    PostgresSink,
    aliases=["postgresql"],
)
register_builtin(
    "fapilog.sinks",
    "routing",
    RoutingSink,
)

# NOTE: MemoryMappedPersistence is exported (in __all__) as a building block
# for custom sinks, but is NOT registered as a sink itself because it does not
# implement the BaseSink protocol (it uses open/close instead of start/stop,
# and append_line instead of write). See docs/api-reference/plugins/sinks.md.
