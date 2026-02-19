"""
Concurrency utilities for the logging pipeline.

Exposes:
- BackpressurePolicy: WAIT or REJECT
- NonBlockingRingQueue: thread-safe bounded queue
- PriorityAwareQueue: thread-safe bounded queue with priority-aware eviction

BackpressureError remains imported to preserve the public surface for callers
that expect it from this module.
"""

from __future__ import annotations

import threading
from collections import deque
from enum import Enum
from typing import Generic, TypeVar

from .errors import BackpressureError

T = TypeVar("T")


class BackpressurePolicy(str, Enum):
    WAIT = "wait"  # Wait until space is available (potentially with timeout)
    REJECT = "reject"  # Raise BackpressureError immediately when full


class NonBlockingRingQueue(Generic[T]):
    """Thread-safe bounded queue.

    - All public methods are protected by a threading.Lock
    - No asyncio dependency — works across thread boundaries
    - Workers poll via try_dequeue(); callers use try_enqueue()
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._dq: deque[T] = deque()
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def qsize(self) -> int:
        with self._lock:
            return len(self._dq)

    def is_full(self) -> bool:
        with self._lock:
            return len(self._dq) >= self._capacity

    def is_empty(self) -> bool:
        with self._lock:
            return not self._dq

    def try_enqueue(self, item: T) -> bool:
        with self._lock:
            if len(self._dq) >= self._capacity:
                return False
            self._dq.append(item)
            return True

    def try_dequeue(self) -> tuple[bool, T | None]:
        with self._lock:
            if not self._dq:
                return False, None
            item = self._dq.popleft()
            return True, item


class PriorityAwareQueue(Generic[T]):
    """Thread-safe bounded queue with priority-aware eviction for protected log levels.

    .. deprecated:: 1.52
        Use :class:`DualQueue` instead. ``PriorityAwareQueue`` will be removed
        in a future release.

    When queue is full and a protected-level event arrives, an unprotected
    event is evicted to make room. Uses tombstoning for O(1) eviction.

    All public methods are protected by a threading.Lock for cross-thread safety.

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
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._protected = frozenset(protected_levels)
        self._dq: deque[T | None] = deque()  # None = compacted tombstone slot
        # Track unprotected events for O(1) eviction candidate lookup
        self._unprotected_refs: deque[T] = deque()
        self._tombstone_count: int = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        """Maximum live items the queue can hold."""
        with self._lock:
            return self._capacity

    def qsize(self) -> int:
        """Return count of live (non-tombstoned) items."""
        with self._lock:
            return len(self._dq) - self._tombstone_count

    def is_full(self) -> bool:
        """Check if queue is at capacity (counting live items only)."""
        with self._lock:
            return (len(self._dq) - self._tombstone_count) >= self._capacity

    def is_empty(self) -> bool:
        """Check if queue has no live items."""
        with self._lock:
            return (len(self._dq) - self._tombstone_count) == 0

    def _is_protected(self, item: T) -> bool:
        """Check if item has a protected level. Caller must hold _lock."""
        if not self._protected:
            return False
        if isinstance(item, dict):
            level = item.get("level", "INFO")
            if isinstance(level, str):
                return level.upper() in self._protected
        return False

    def try_enqueue(self, item: T) -> bool:
        """Try to enqueue item, with priority-aware eviction if needed.

        Returns:
            True if enqueued (possibly after eviction), False if dropped.
        """
        with self._lock:
            is_protected = self._is_protected(item)
            live_count = len(self._dq) - self._tombstone_count

            # Fast path: space available
            if live_count < self._capacity:
                self._dq.append(item)
                if not is_protected:
                    self._unprotected_refs.append(item)
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
        with self._lock:
            while self._dq:
                item = self._dq.popleft()
                if item is None:
                    # Compacted tombstone slot
                    continue
                if isinstance(item, dict) and item.get("_evicted"):
                    # Tombstoned item - skip and decrement count
                    self._tombstone_count -= 1
                    continue

                # Live item found
                # Strip _evicted marker if present (shouldn't be on live items)
                if isinstance(item, dict) and "_evicted" in item:
                    del item["_evicted"]

                return True, item

            # Queue is empty
            return False, None

    def _compact_if_needed(self) -> None:
        """Compact queue if tombstone ratio exceeds threshold. Caller must hold _lock."""
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


class DualQueue(Generic[T]):
    """Routes events to main or protected queue by level (Story 1.52).

    Protected-level events go to a dedicated bounded queue, isolating them
    from main queue pressure. Workers always drain the protected queue first.
    """

    def __init__(
        self,
        main_capacity: int,
        protected_capacity: int,
        protected_levels: frozenset[str],
    ) -> None:
        self._main = NonBlockingRingQueue[T](main_capacity)
        self._protected = NonBlockingRingQueue[T](protected_capacity)
        self._protected_levels = protected_levels
        self._main_drops = 0
        self._protected_drops = 0
        self._shedding = False

    def _is_protected(self, item: T) -> bool:
        if not self._protected_levels:
            return False
        if isinstance(item, dict):
            level = item.get("level", "INFO")
            if isinstance(level, str):
                return level.upper() in self._protected_levels
        return False

    @property
    def protected_capacity(self) -> int:
        return self._protected.capacity

    @property
    def is_shedding(self) -> bool:
        return self._shedding

    def activate_shedding(self) -> None:
        self._shedding = True

    def deactivate_shedding(self) -> None:
        self._shedding = False

    def try_enqueue(self, item: T) -> bool:
        if self._is_protected(item):
            ok = self._protected.try_enqueue(item)
            if not ok:
                self._protected_drops += 1
            return ok
        ok = self._main.try_enqueue(item)
        if not ok:
            self._main_drops += 1
        return ok

    def try_dequeue(self) -> tuple[bool, T | None]:
        ok, item = self._protected.try_dequeue()
        if ok:
            return ok, item
        if self._shedding:
            return False, None
        return self._main.try_dequeue()

    def drain_into(self, batch: list[T]) -> None:
        while True:
            ok, item = self._protected.try_dequeue()
            if not ok:
                break
            batch.append(item)  # type: ignore[arg-type]
        while True:
            ok, item = self._main.try_dequeue()
            if not ok:
                break
            batch.append(item)  # type: ignore[arg-type]

    # Size / state queries
    def main_qsize(self) -> int:
        return self._main.qsize()

    def protected_qsize(self) -> int:
        return self._protected.qsize()

    def qsize(self) -> int:
        return self._main.qsize() + self._protected.qsize()

    def is_empty(self) -> bool:
        return self._main.is_empty() and self._protected.is_empty()

    def is_full(self) -> bool:
        return self._main.is_full()

    def main_is_full(self) -> bool:
        return self._main.is_full()

    def protected_is_full(self) -> bool:
        return self._protected.is_full()

    @property
    def capacity(self) -> int:
        return self._main.capacity

    @property
    def main_drops(self) -> int:
        return self._main_drops

    @property
    def protected_drops(self) -> int:
        return self._protected_drops


__all__ = [
    "BackpressurePolicy",
    "BackpressureError",
    "DualQueue",
    "NonBlockingRingQueue",
    "PriorityAwareQueue",
]

# Mark public API for vulture (Story 1.52)
_VULTURE_USED: tuple[object, ...] = (
    DualQueue.main_is_full,
    DualQueue.protected_is_full,
    DualQueue.main_drops,
    DualQueue.protected_drops,
    DualQueue.main_qsize,
    DualQueue.protected_qsize,
    DualQueue.drain_into,
    DualQueue.protected_capacity,
    DualQueue.is_shedding,
    DualQueue.activate_shedding,
    DualQueue.deactivate_shedding,
)
