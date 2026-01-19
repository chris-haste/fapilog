"""
Class-based sink writer for fanout operations (Story 5.29).

This module provides SinkWriterGroup, a class that encapsulates sink writing
logic with explicit state. It replaces the closure-based _fanout_writer function
to improve code clarity and testability.

Key improvements over closure-based approach:
- Explicit instance state instead of captured closure variables
- No nested function definitions
- All imports at module top level
- Methods are independently testable
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

from ..plugins.sinks.fallback import handle_sink_write_failure

if TYPE_CHECKING:
    from .circuit_breaker import SinkCircuitBreaker, SinkCircuitBreakerConfig

# Type alias for redact mode
RedactMode = Literal["inherit", "minimal", "none"]


def make_sink_writer(sink: Any) -> tuple[Any, Any]:
    """Create write functions for a single sink.

    Returns a tuple of (write, write_serialized) async functions that handle
    sink lifecycle (start on first write) and return values.

    Args:
        sink: Sink instance with write() and optionally write_serialized() methods.

    Returns:
        Tuple of (write_fn, write_serialized_fn) async callables.
    """

    async def _sink_write(entry: dict[str, Any]) -> bool | None:
        if hasattr(sink, "start") and not getattr(sink, "_started", False):
            try:
                await sink.start()
                sink._started = True
            except Exception:
                try:
                    from .diagnostics import warn as _warn

                    _warn(
                        "sink",
                        "sink start failed",
                        sink_type=type(sink).__name__,
                    )
                except Exception:
                    pass
        result: bool | None = await sink.write(entry)
        return result

    async def _sink_write_serialized(view: object) -> bool | None:
        try:
            result: bool | None = await sink.write_serialized(view)
            return result
        except AttributeError:
            return None

    return _sink_write, _sink_write_serialized


class SinkWriterGroup:
    """Manages writing to multiple sinks with circuit breaker protection.

    This class encapsulates the fanout logic for writing log entries to multiple
    sinks, with optional parallel execution and circuit breaker fault isolation.

    Attributes:
        _sinks: List of sink instances.
        _writers: List of (write, write_serialized) tuples from make_sink_writer.
        _breakers: Mapping from sink id to SinkCircuitBreaker instance.
        _parallel: Whether to write to sinks in parallel.
        _redact_mode: Redaction mode for fallback output.

    Example:
        >>> group = SinkWriterGroup(
        ...     [sink1, sink2],
        ...     parallel=True,
        ...     circuit_config=SinkCircuitBreakerConfig(enabled=True),
        ... )
        >>> await group.write({"message": "test", "level": "INFO"})
    """

    __slots__ = ("_sinks", "_writers", "_breakers", "_parallel", "_redact_mode")

    def __init__(
        self,
        sinks: list[object],
        *,
        parallel: bool = False,
        circuit_config: SinkCircuitBreakerConfig | None = None,
        redact_mode: RedactMode = "minimal",
    ) -> None:
        """Initialize SinkWriterGroup with sinks and configuration.

        Args:
            sinks: List of sink instances to write to.
            parallel: If True, write to sinks in parallel when >1 sink.
            circuit_config: Optional circuit breaker config for fault isolation.
            redact_mode: Redaction mode for fallback output (Story 4.46).
        """
        from .circuit_breaker import SinkCircuitBreaker

        self._sinks = sinks
        self._writers = [make_sink_writer(s) for s in sinks]
        self._parallel = parallel
        self._redact_mode = redact_mode

        # Create circuit breakers for each sink if enabled
        self._breakers: dict[int, SinkCircuitBreaker] = {}
        if circuit_config is not None and getattr(circuit_config, "enabled", False):
            for sink in sinks:
                name = getattr(sink, "name", type(sink).__name__)
                self._breakers[id(sink)] = SinkCircuitBreaker(name, circuit_config)

    async def write(self, entry: dict[str, Any]) -> None:
        """Write entry to all sinks (parallel or sequential based on config).

        Args:
            entry: Log entry dictionary to write.
        """
        if self._parallel and len(self._writers) > 1:
            await self._write_parallel(entry)
        else:
            await self._write_sequential(entry)

    async def write_serialized(self, view: object) -> None:
        """Write serialized view to all sinks.

        Args:
            view: Serialized view object to write.
        """
        for i, (_, write_s) in enumerate(self._writers):
            await self._write_one_serialized(i, write_s, view)

    async def _write_sequential(self, entry: dict[str, Any]) -> None:
        """Write to sinks sequentially."""
        for i, (write, _) in enumerate(self._writers):
            await self._write_one(i, write, entry)

    async def _write_parallel(self, entry: dict[str, Any]) -> None:
        """Write to sinks in parallel using asyncio.gather."""
        if len(self._writers) <= 1:
            # Single sink, no need for gather
            if self._writers:
                await self._write_one(0, self._writers[0][0], entry)
            return

        tasks = []
        for i, (write, _) in enumerate(self._writers):
            sink = self._sinks[i]
            breaker = self._breakers.get(id(sink))

            if breaker and not breaker.should_allow():
                continue  # Skip - circuit is open

            tasks.append(self._write_one(i, write, entry))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _write_one(
        self,
        idx: int,
        write_fn: Any,
        entry: dict[str, Any],
    ) -> None:
        """Write to a single sink with circuit breaker protection.

        Args:
            idx: Index of the sink in self._sinks.
            write_fn: Async write function from make_sink_writer.
            entry: Log entry dictionary to write.
        """
        sink = self._sinks[idx]
        breaker = self._breakers.get(id(sink))

        if breaker and not breaker.should_allow():
            return  # Skip - circuit is open

        try:
            result = await write_fn(entry)
            # False return signals failure (Story 4.41)
            if result is False:
                if breaker:
                    breaker.record_failure()
                try:
                    await handle_sink_write_failure(
                        entry,
                        sink=sink,
                        error=RuntimeError("Sink returned False"),
                        serialized=False,
                        redact_mode=self._redact_mode,
                    )
                except Exception:
                    pass
            elif breaker:
                breaker.record_success()
        except Exception as exc:
            if breaker:
                breaker.record_failure()
            try:
                await handle_sink_write_failure(
                    entry,
                    sink=sink,
                    error=exc,
                    serialized=False,
                    redact_mode=self._redact_mode,
                )
            except Exception:
                pass
            # Contain error - don't propagate

    async def _write_one_serialized(
        self,
        idx: int,
        write_fn: Any,
        view: object,
    ) -> None:
        """Write serialized view to a single sink with circuit breaker protection.

        Args:
            idx: Index of the sink in self._sinks.
            write_fn: Async write_serialized function from make_sink_writer.
            view: Serialized view object to write.
        """
        sink = self._sinks[idx]
        breaker = self._breakers.get(id(sink))

        if breaker and not breaker.should_allow():
            return  # Skip - circuit is open

        try:
            result = await write_fn(view)
            # False return signals failure (Story 4.41)
            if result is False:
                if breaker:
                    breaker.record_failure()
                try:
                    await handle_sink_write_failure(
                        view,
                        sink=sink,
                        error=RuntimeError("Sink returned False"),
                        serialized=True,
                        redact_mode=self._redact_mode,
                    )
                except Exception:
                    pass
            elif breaker:
                breaker.record_success()
        except Exception as exc:
            if breaker:
                breaker.record_failure()
            try:
                await handle_sink_write_failure(
                    view,
                    sink=sink,
                    error=exc,
                    serialized=True,
                    redact_mode=self._redact_mode,
                )
            except Exception:
                pass
            # Contain errors


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    SinkWriterGroup,
    make_sink_writer,
)
