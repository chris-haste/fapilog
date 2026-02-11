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


class PriorityAwareQueue(Generic[T]):
    """Bounded queue with priority-aware eviction for protected log levels.

    When queue is full and a protected-level event arrives, an unprotected
    event is evicted to make room. Uses tombstoning for O(1) eviction.

    - Enqueue (normal): O(1)
    - Enqueue (with eviction): O(1) - just marks tombstone, no scanning
    - Dequeue: O(1) amortized - skips tombstones, compacts lazily

    Events must be dicts with a "level" key for priority checking.
    """

    # Compact when tombstones exceed this ratio of total queue
    _COMPACTION_THRESHOLD = 0.25

    def __init__(
        self,
        capacity: int,
        protected_levels: frozenset[str] | set[str],
    ) -> None:
        """Initialize priority-aware queue.

        Args:
            capacity: Maximum live items in the queue.
            protected_levels: Set of level names (uppercase) that are protected
                from eviction. When a protected event arrives and queue is full,
                an unprotected event will be evicted.
        """
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._protected = frozenset(protected_levels)
        self._dq: deque[T | None] = deque()  # None = compacted tombstone slot
        # Track unprotected events for O(1) eviction candidate lookup
        self._unprotected_refs: deque[T] = deque()
        self._tombstone_count: int = 0
        # Event signaling for async waiting
        self._space_available = asyncio.Event()
        self._data_available = asyncio.Event()
        self._space_available.set()
        self._data_available.clear()

    @property
    def capacity(self) -> int:
        """Maximum live items the queue can hold."""
        return self._capacity

    def grow_capacity(self, new_capacity: int) -> None:
        """Increase queue capacity. Grow-only — ignored if new_capacity <= current.

        Re-signals ``_space_available`` so blocked enqueuers wake up.
        Thread-safe: CPython GIL makes the int write atomic.
        """
        if new_capacity <= self._capacity:
            return
        self._capacity = new_capacity
        self._space_available.set()

    def qsize(self) -> int:
        """Return count of live (non-tombstoned) items."""
        return len(self._dq) - self._tombstone_count

    def is_full(self) -> bool:
        """Check if queue is at capacity (counting live items only)."""
        return self.qsize() >= self._capacity

    def is_empty(self) -> bool:
        """Check if queue has no live items."""
        return self.qsize() == 0

    def _is_protected(self, item: T) -> bool:
        """Check if item has a protected level."""
        if not self._protected:
            return False
        if isinstance(item, dict):
            level = item.get("level", "INFO")
            if isinstance(level, str):
                return level.upper() in self._protected
        return False

    def try_enqueue(self, item: T) -> bool:
        """Try to enqueue item, with priority-aware eviction if needed.

        Args:
            item: The item to enqueue (dict with "level" key for priority).

        Returns:
            True if enqueued (possibly after eviction), False if dropped.
        """
        is_protected = self._is_protected(item)

        # Fast path: space available
        if not self.is_full():
            self._dq.append(item)
            if not is_protected:
                self._unprotected_refs.append(item)
            self._data_available.set()
            if self.is_full():
                self._space_available.clear()
            return True

        # Overflow path: try eviction if protected event
        if is_protected and self._unprotected_refs:
            # Tombstone oldest unprotected event (O(1))
            evict = self._unprotected_refs.popleft()
            if isinstance(evict, dict):
                evict["_evicted"] = True
            self._tombstone_count += 1

            # Enqueue the protected event
            self._dq.append(item)
            self._data_available.set()

            # Compact if tombstone ratio is high
            self._compact_if_needed()
            return True

        # No eviction possible - drop the event
        return False

    def try_dequeue(self) -> tuple[bool, T | None]:
        """Try to dequeue the next live item.

        Skips tombstoned entries automatically.

        Returns:
            Tuple of (success, item). Item is None if queue is empty.
        """
        while self._dq:
            item = self._dq.popleft()
            if item is None:
                # Compacted tombstone slot
                continue
            if isinstance(item, dict) and item.get("_evicted"):
                # Tombstoned item - skip and decrement count
                self._tombstone_count -= 1
                # Strip the internal marker before returning would happen here
                # but we skip evicted items, so no need
                continue

            # Live item found
            self._space_available.set()
            if self.is_empty():
                self._data_available.clear()

            # Strip _evicted marker if present (shouldn't be on live items)
            if isinstance(item, dict) and "_evicted" in item:
                del item["_evicted"]

            return True, item

        # Queue is empty
        self._data_available.clear()
        return False, None

    def _compact_if_needed(self) -> None:
        """Compact queue if tombstone ratio exceeds threshold."""
        if len(self._dq) == 0:
            return
        ratio = self._tombstone_count / len(self._dq)
        if ratio > self._COMPACTION_THRESHOLD:
            # Rebuild queue without tombstoned entries
            new_dq: deque[T | None] = deque()
            new_unprotected: deque[T] = deque()

            for item in self._dq:
                if item is None:
                    continue
                if isinstance(item, dict) and item.get("_evicted"):
                    continue
                new_dq.append(item)
                if not self._is_protected(item):
                    new_unprotected.append(item)

            self._dq = new_dq
            self._unprotected_refs = new_unprotected
            self._tombstone_count = 0

    async def await_enqueue(
        self,
        item: T,
        *,
        timeout: float | None = None,
    ) -> None:
        """Enqueue item, waiting for space if queue is full.

        Note: Priority eviction happens in try_enqueue, so this may
        succeed immediately for protected events even when full.

        Args:
            item: The item to enqueue.
            timeout: Maximum time to wait in seconds, or None for no timeout.

        Raises:
            TimeoutError: If timeout expires before space becomes available.
        """
        if self.try_enqueue(item):
            return

        start = asyncio.get_event_loop().time() if timeout is not None else None

        while True:
            remaining: float | None = None
            if timeout is not None and start is not None:
                elapsed = asyncio.get_event_loop().time() - start
                remaining = timeout - elapsed
                if remaining <= 0:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to enqueue")

            try:
                await asyncio.wait_for(self._space_available.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                from .errors import TimeoutError

                raise TimeoutError("Timed out waiting to enqueue") from None

            if self.try_enqueue(item):
                return
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
        ok, item = self.try_dequeue()
        if ok:
            return item  # type: ignore[return-value]

        start = asyncio.get_event_loop().time() if timeout is not None else None

        while True:
            remaining: float | None = None
            if timeout is not None and start is not None:
                elapsed = asyncio.get_event_loop().time() - start
                remaining = timeout - elapsed
                if remaining <= 0:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to dequeue")

            try:
                await asyncio.wait_for(self._data_available.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                from .errors import TimeoutError

                raise TimeoutError("Timed out waiting to dequeue") from None

            ok, item = self.try_dequeue()
            if ok:
                return item  # type: ignore[return-value]
            self._data_available.clear()


__all__ = [
    "BackpressurePolicy",
    "BackpressureError",
    "NonBlockingRingQueue",
    "PriorityAwareQueue",
]

# Mark public API for vulture (Story 1.48)
_VULTURE_USED: tuple[object, ...] = (PriorityAwareQueue.grow_capacity,)
