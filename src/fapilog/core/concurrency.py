"""
Concurrency control and lock-free utilities for the async pipeline.

This module now contains:
- BackpressurePolicy: WAIT or REJECT
- AsyncBoundedExecutor: bounded-concurrency executor with a bounded queue
- LockFreeRingBuffer: single-producer/single-consumer lock-free ring buffer

Design:
- Async-first using asyncio primitives
- Controlled concurrency via semaphore and worker tasks
- Backpressure on queue full with configurable policy
- Lock-free ring buffer uses atomic-like index arithmetic under the GIL for
  SPSC scenarios without locks; provides async helpers for awaiting space/data
"""

from __future__ import annotations

import asyncio
import types
from enum import Enum
from typing import Awaitable, Callable, Generic, Iterable, TypeVar

from .errors import BackpressureError

T = TypeVar("T")


class BackpressurePolicy(str, Enum):
    WAIT = "wait"  # Wait until space is available (potentially with timeout)
    REJECT = "reject"  # Raise BackpressureError immediately when full


class AsyncBoundedExecutor(Generic[T]):
    """Bounded-concurrency executor with backpressure.

    Usage:
        async with AsyncBoundedExecutor(
            max_concurrency=5, max_queue_size=100
        ) as ex:
            fut = await ex.submit(lambda: worker(1))
            result = await fut
    """

    def __init__(
        self,
        *,
        max_concurrency: int,
        max_queue_size: int,
        backpressure_policy: BackpressurePolicy = BackpressurePolicy.WAIT,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be > 0")
        if max_queue_size <= 0:
            raise ValueError("max_queue_size must be > 0")
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        # Capacity semaphore accounts for both running and queued items
        self._capacity_sem = asyncio.Semaphore(max_concurrency + max_queue_size)
        # Unbounded internal queue; capacity enforced by _capacity_sem
        self._queue: asyncio.Queue[
            tuple[Callable[[], Awaitable[T]], asyncio.Future[T]]
        ] = asyncio.Queue()
        self._policy = backpressure_policy
        self._workers: list[asyncio.Task[None]] = []
        self._closed = False

    async def __aenter__(self) -> AsyncBoundedExecutor[T]:
        # Spawn worker tasks equal to max_concurrency
        for _ in range(self._max_concurrency):
            self._workers.append(asyncio.create_task(self._worker_loop()))
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: types.TracebackType | None,
    ) -> None:
        await self._shutdown()

    async def submit(
        self,
        factory: Callable[[], Awaitable[T]],
        *,
        timeout: float | None = None,
    ) -> asyncio.Future[T]:
        """Submit a coroutine factory to be executed.

        Returns a Future that can be awaited for the result.

        Backpressure behavior when queue is full:
        - WAIT: waits until space is available (respecting timeout if provided)
        - REJECT: raises BackpressureError immediately
        """
        if self._closed:
            raise RuntimeError("Executor is closed")

        loop = asyncio.get_event_loop()
        future: asyncio.Future[T] = loop.create_future()

        # Acquire capacity slot according to policy
        try:
            if self._policy is BackpressurePolicy.REJECT:
                # Fast-path: if no capacity, reject immediately
                available = getattr(self._capacity_sem, "_value", 0)
                if available <= 0:
                    raise BackpressureError("Queue is full; submission rejected")
                await self._capacity_sem.acquire()
            else:
                if timeout is not None:
                    await asyncio.wait_for(
                        self._capacity_sem.acquire(), timeout=timeout
                    )
                else:
                    await self._capacity_sem.acquire()
        except asyncio.TimeoutError as e:
            # Timeout or immediate no-capacity for REJECT policy
            raise BackpressureError("Timed out waiting for queue space") from e
        except BackpressureError:
            raise

        # Enqueue after capacity acquired
        self._queue.put_nowait((factory, future))
        return future

    async def run_all(self, factories: Iterable[Callable[[], Awaitable[T]]]) -> list[T]:
        """Convenience method to run many tasks respecting backpressure.

        Returns results in submission order.
        """
        futures: list[asyncio.Future[T]] = []
        for f in factories:
            fut = await self.submit(f)
            futures.append(fut)
        # Await all futures concurrently
        results: list[T] = await asyncio.gather(*futures)
        return list(results)

    async def _worker_loop(self) -> None:
        try:
            while True:
                factory, future = await self._queue.get()
                if future.cancelled():
                    self._queue.task_done()
                    continue
                async with self._semaphore:
                    try:
                        result = await factory()
                    except Exception as e:  # noqa: BLE001
                        if not future.done():
                            future.set_exception(e)
                    else:
                        if not future.done():
                            future.set_result(result)
                    finally:
                        self._queue.task_done()
                        # Release capacity slot
                        self._capacity_sem.release()
        except asyncio.CancelledError:
            # Drain exit
            return

    async def _shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Wait for queue to be fully processed
        await self._queue.join()
        # Cancel workers
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()


class LockFreeRingBuffer(Generic[T]):
    """Single-producer/single-consumer lock-free ring buffer.

    - Fixed capacity; overwriting is not allowed (push fails when full).
    - Implemented using modulo arithmetic indices guarded by GIL (CPython),
      avoiding explicit locks for SPSC.
    - Provides async helpers ``await_push`` and ``await_pop`` that spin/yield
      cooperatively without blocking the event loop.
    """

    __slots__ = ("_buffer", "_capacity", "_head", "_tail")

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        # Use list with pre-allocated None slots
        self._buffer: list[T | None] = [None] * capacity
        self._capacity = capacity
        self._head = 0  # next index to read
        self._tail = 0  # next index to write

    @property
    def capacity(self) -> int:
        return self._capacity

    def _size(self) -> int:
        return (self._tail - self._head) % (2 * self._capacity)

    def is_empty(self) -> bool:
        return self._head == self._tail

    def is_full(self) -> bool:
        return self._size() == self._capacity

    def try_push(self, item: T) -> bool:
        """Attempt to push an item; returns False if buffer is full."""
        if self.is_full():
            return False
        idx = self._tail % self._capacity
        self._buffer[idx] = item
        # Advance tail; modulo arithmetic on potentially unbounded tail
        self._tail = (self._tail + 1) % (2 * self._capacity)
        return True

    def try_pop(self) -> tuple[bool, T | None]:
        """Attempt to pop an item; returns (False, None) if empty."""
        if self.is_empty():
            return False, None
        idx = self._head % self._capacity
        item = self._buffer[idx]
        self._buffer[idx] = None
        self._head = (self._head + 1) % (2 * self._capacity)
        return True, item

    async def await_push(self, item: T, *, yield_every: int = 8) -> None:
        """Async push that yields to loop while waiting for space.

        yield_every controls how often to ``await asyncio.sleep(0)`` while
        spinning to avoid starving the loop under high contention.
        """
        spins = 0
        while not self.try_push(item):
            spins += 1
            if (spins % yield_every) == 0:
                await asyncio.sleep(0)

    async def await_pop(self, *, yield_every: int = 8) -> T:
        """Async pop that yields to loop while waiting for data."""
        spins = 0
        while True:
            ok, item = self.try_pop()
            if ok:
                # mypy: item may be Optional; guarded by ok
                return item  # type: ignore[return-value]
            spins += 1
            if (spins % yield_every) == 0:
                await asyncio.sleep(0)
