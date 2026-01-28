"""
Concurrency utilities for the async pipeline.

Exposes:
- BackpressurePolicy: WAIT or REJECT
- NonBlockingRingQueue: asyncio-friendly bounded queue

BackpressureError remains imported to preserve the public surface for callers
that expect it from this module.
"""

from __future__ import annotations

import asyncio
from collections import deque
from enum import Enum
from typing import Generic, TypeVar

from .errors import BackpressureError

T = TypeVar("T")


class BackpressurePolicy(str, Enum):
    WAIT = "wait"  # Wait until space is available (potentially with timeout)
    REJECT = "reject"  # Raise BackpressureError immediately when full


class NonBlockingRingQueue(Generic[T]):
    """Asyncio-only bounded queue with event-based signaling.

    - Provides try/await variants for enqueue/dequeue
    - Uses asyncio.Event for efficient waiting (no spin-wait)
    - Relies on single-threaded event loop semantics
    - Fairness is best-effort; optimized for low overhead
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._dq: deque[T] = deque()
        # Event signaling for efficient waiting
        self._space_available = asyncio.Event()
        self._data_available = asyncio.Event()
        # Initially: space is available, data is not
        self._space_available.set()
        self._data_available.clear()

    @property
    def capacity(self) -> int:
        return self._capacity

    def qsize(self) -> int:
        return len(self._dq)

    def is_full(self) -> bool:
        return len(self._dq) >= self._capacity

    def is_empty(self) -> bool:
        return not self._dq

    def try_enqueue(self, item: T) -> bool:
        if self.is_full():
            return False
        self._dq.append(item)
        # Signal that data is available for dequeuers
        self._data_available.set()
        # If queue is now full, clear space_available
        if self.is_full():
            self._space_available.clear()
        return True

    def try_dequeue(self) -> tuple[bool, T | None]:
        if self.is_empty():
            return False, None
        item = self._dq.popleft()
        # Signal that space is available for enqueuers
        self._space_available.set()
        # If queue is now empty, clear data_available
        if self.is_empty():
            self._data_available.clear()
        return True, item

    async def await_enqueue(
        self,
        item: T,
        *,
        timeout: float | None = None,
    ) -> None:
        """Enqueue item, waiting for space if queue is full.

        Args:
            item: The item to enqueue.
            timeout: Maximum time to wait in seconds, or None for no timeout.

        Raises:
            TimeoutError: If timeout expires before space becomes available.
        """
        # Fast path: try to enqueue immediately
        if self.try_enqueue(item):
            return

        # Slow path: wait for space to become available
        start = asyncio.get_event_loop().time() if timeout is not None else None

        while True:
            # Calculate remaining timeout
            remaining: float | None = None
            if timeout is not None and start is not None:
                elapsed = asyncio.get_event_loop().time() - start
                remaining = timeout - elapsed
                if remaining <= 0:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to enqueue")

            # Wait for signal that space is available
            try:
                await asyncio.wait_for(self._space_available.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                from .errors import TimeoutError

                raise TimeoutError("Timed out waiting to enqueue") from None

            # Try to enqueue after wakeup (may fail if another waiter got there first)
            if self.try_enqueue(item):
                return
            # If full again, clear the event and retry
            self._space_available.clear()

    async def await_dequeue(
        self,
        *,
        timeout: float | None = None,
    ) -> T:
        """Dequeue item, waiting for data if queue is empty.

        Args:
            timeout: Maximum time to wait in seconds, or None for no timeout.

        Returns:
            The dequeued item.

        Raises:
            TimeoutError: If timeout expires before data becomes available.
        """
        # Fast path: try to dequeue immediately
        ok, item = self.try_dequeue()
        if ok:
            return item  # type: ignore[return-value]

        # Slow path: wait for data to become available
        start = asyncio.get_event_loop().time() if timeout is not None else None

        while True:
            # Calculate remaining timeout
            remaining: float | None = None
            if timeout is not None and start is not None:
                elapsed = asyncio.get_event_loop().time() - start
                remaining = timeout - elapsed
                if remaining <= 0:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to dequeue")

            # Wait for signal that data is available
            try:
                await asyncio.wait_for(self._data_available.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                from .errors import TimeoutError

                raise TimeoutError("Timed out waiting to dequeue") from None

            # Try to dequeue after wakeup (may fail if another waiter got there first)
            ok, item = self.try_dequeue()
            if ok:
                return item  # type: ignore[return-value]
            # If empty again, clear the event and retry
            self._data_available.clear()


__all__ = ["BackpressurePolicy", "BackpressureError", "NonBlockingRingQueue"]
