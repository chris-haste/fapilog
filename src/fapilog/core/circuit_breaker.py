"""
Lightweight circuit breaker utilities for sink protection.

Only sink-level breakers are retained to isolate failing destinations without
the heavier async breaker machinery that isn't used.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if sink has recovered


@dataclass
class SinkCircuitBreakerConfig:
    """Lightweight configuration for sink-specific circuit breakers."""

    enabled: bool = True
    failure_threshold: int = 5  # Open after N consecutive failures
    recovery_timeout_seconds: float = 30.0  # Wait before probing
    half_open_max_calls: int = 1  # Probes before closing


class SinkCircuitBreaker:
    """Simple circuit breaker for individual sink protection.

    Thread Safety
    -------------
    This implementation is thread-safe. All state mutations are protected
    by an internal lock. Safe to use from multiple threads or async tasks.

    The lock is a standard threading.Lock which is also safe in async
    contexts (Python's GIL ensures atomicity of lock acquisition).

    The should_allow() method atomically checks AND increments the
    half_open_calls counter, preventing race conditions where multiple
    callers could bypass the call limit.
    """

    def __init__(
        self,
        sink_name: str,
        config: SinkCircuitBreakerConfig,
    ) -> None:
        self.sink_name = sink_name
        self._config = config
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN

    def should_allow(self) -> bool:
        """Return True if a call should be attempted."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout elapsed
                if self._last_failure_time is not None:
                    elapsed = time.monotonic() - self._last_failure_time
                    if elapsed >= self._config.recovery_timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 1  # Count this transition as first call
                        return True
                return False

            # self._state == CircuitState.HALF_OPEN
            # Atomically check and increment call count
            if self._half_open_calls < self._config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovery confirmed
                self._state = CircuitState.CLOSED
                self._emit_state_change("closed")
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed, back to open
                self._state = CircuitState.OPEN
                self._emit_state_change("open")
            elif self._failure_count >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                self._emit_state_change("open")

    def _emit_state_change(self, new_state: str) -> None:
        """Emit diagnostic for state change."""
        try:
            from .diagnostics import warn

            warn(
                "circuit-breaker",
                f"sink circuit {new_state}",
                sink=self.sink_name,
                failure_count=self._failure_count,
            )
        except Exception:
            pass
