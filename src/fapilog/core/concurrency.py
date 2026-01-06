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
    """Asyncio-only non-blocking ring queue based on deque with capacity.

    - Provides try/await variants for enqueue/dequeue
    - No locks; relies on single-threaded event loop semantics
    - Fairness is best-effort; optimized for low overhead
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = int(capacity)
        self._dq: deque[T] = deque()

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
        return True

    def try_dequeue(self) -> tuple[bool, T | None]:
        if self.is_empty():
            return False, None
        return True, self._dq.popleft()

    async def await_enqueue(
        self,
        item: T,
        *,
        yield_every: int = 8,
        timeout: float | None = None,
    ) -> None:
        spins = 0
        start: float | None = None
        if timeout is not None:
            start = asyncio.get_event_loop().time()
        while not self.try_enqueue(item):
            if timeout is not None and start is not None:
                now = asyncio.get_event_loop().time()
                if (now - start) >= timeout:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to enqueue")
            spins += 1
            if (spins % yield_every) == 0:
                await asyncio.sleep(0)

    async def await_dequeue(
        self,
        *,
        yield_every: int = 8,
        timeout: float | None = None,
    ) -> T:
        spins = 0
        start: float | None = None
        if timeout is not None:
            start = asyncio.get_event_loop().time()
        while True:
            ok, item = self.try_dequeue()
            if ok:
                return item  # type: ignore[return-value]
            if timeout is not None and start is not None:
                now = asyncio.get_event_loop().time()
                if (now - start) >= timeout:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to dequeue")
            spins += 1
            if (spins % yield_every) == 0:
                await asyncio.sleep(0)


__all__ = ["BackpressurePolicy", "BackpressureError", "NonBlockingRingQueue"]
