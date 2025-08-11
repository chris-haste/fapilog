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
from collections import deque
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

    async def close(self) -> None:
        """Alias for ``_shutdown`` for symmetry with context management.

        This mirrors the behavior of ``__aexit__`` and is provided as a
        convenience when using the executor outside ``async with`` blocks.
        """
        await self._shutdown()


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

    async def await_push(
        self,
        item: T,
        *,
        yield_every: int = 8,
        timeout: float | None = None,
    ) -> None:
        """Async push that yields to loop while waiting for space.

        yield_every controls how often to ``await asyncio.sleep(0)`` while
        spinning to avoid starving the loop under high contention.
        """
        spins = 0
        start: float | None = None
        if timeout is not None:
            start = asyncio.get_event_loop().time()
        while not self.try_push(item):
            if timeout is not None and start is not None:
                now = asyncio.get_event_loop().time()
                if (now - start) >= timeout:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to push to ring buffer")
            spins += 1
            if (spins % yield_every) == 0:
                await asyncio.sleep(0)

    async def await_pop(
        self,
        *,
        yield_every: int = 8,
        timeout: float | None = None,
    ) -> T:
        """Async pop that yields to loop while waiting for data.

        Raises TimeoutError if timeout elapses before an item is available.
        """
        spins = 0
        start: float | None = None
        if timeout is not None:
            start = asyncio.get_event_loop().time()
        while True:
            ok, item = self.try_pop()
            if ok:
                # mypy: item may be Optional; guarded by ok
                return item  # type: ignore[return-value]
            if timeout is not None and start is not None:
                now = asyncio.get_event_loop().time()
                if (now - start) >= timeout:
                    from .errors import TimeoutError

                    raise TimeoutError("Timed out waiting to pop from ring buffer")
            spins += 1
            if (spins % yield_every) == 0:
                await asyncio.sleep(0)


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


class AsyncWorkStealingExecutor(Generic[T]):
    """Async work-stealing executor with bounded capacity.

    Design principles:
    - Pure async/await, no blocking calls
    - Zero global state; all state lives within the executor instance
    - Lock-free operations based on deque operations executed within the
      single-threaded asyncio event loop (atomic per step under GIL)

    Behavior:
    - Submissions target a shard (queue). By default, shard is chosen via
      round-robin. Callers may explicitly target a shard via ``shard_key``.
    - Workers primarily consume from their own shard; when empty they steal
      from other shards (oldest-first) to maximize utilization.
    - Backpressure is enforced across the total of running + queued items via
      a capacity semaphore, mirroring ``AsyncBoundedExecutor``.

    Notes:
    - Asyncio-only: This executor is designed for a single asyncio event loop
      and is not thread-safe. Do not submit work from multiple threads.
    - Fairness: Work distribution is best-effort. Stealing improves overall
      utilization but does not guarantee strict fairness across shards.
    """

    def __init__(
        self,
        *,
        max_concurrency: int,
        max_queue_size: int,
        backpressure_policy: BackpressurePolicy = BackpressurePolicy.WAIT,
        num_shards: int | None = None,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be > 0")
        if max_queue_size <= 0:
            raise ValueError("max_queue_size must be > 0")
        if num_shards is None:
            num_shards = max_concurrency
        if num_shards <= 0:
            raise ValueError("num_shards must be > 0")

        self._max_concurrency = max_concurrency
        self._num_shards = num_shards
        self._policy = backpressure_policy

        # Capacity semaphore accounts for both running and queued items
        self._capacity_sem = asyncio.Semaphore(max_concurrency + max_queue_size)
        # Sharded local deques (each primarily used by corresponding worker)
        self._shards: list[
            deque[tuple[Callable[[], Awaitable[T]], asyncio.Future[T]]]
        ] = [deque() for _ in range(self._num_shards)]

        # Worker control
        self._workers: list[asyncio.Task[None]] = []
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._closed = False
        self._rr_index = 0
        # Condition variable to wake idle workers upon new task submissions
        self._cv = asyncio.Condition()

    async def __aenter__(self) -> AsyncWorkStealingExecutor[T]:
        # Spawn worker tasks equal to max_concurrency
        for worker_index in range(self._max_concurrency):
            self._workers.append(asyncio.create_task(self._worker_loop(worker_index)))
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
        shard_key: int | None = None,
    ) -> asyncio.Future[T]:
        """Submit a coroutine factory to be executed.

        If ``shard_key`` is provided, the target shard will be
        ``shard_key % num_shards``; otherwise round-robin assignment is used.
        """
        if self._closed:
            raise RuntimeError("Executor is closed")

        loop = asyncio.get_event_loop()
        future: asyncio.Future[T] = loop.create_future()

        # Acquire capacity slot according to policy
        try:
            if self._policy is BackpressurePolicy.REJECT:
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
            raise BackpressureError("Timed out waiting for queue space") from e

        # Choose shard and enqueue
        if shard_key is not None:
            shard_index = shard_key % self._num_shards
        else:
            shard_index = self._rr_index % self._num_shards
            self._rr_index = (self._rr_index + 1) % (1 << 30)

        self._shards[shard_index].append((factory, future))

        # Notify workers that new work is available
        async with self._cv:
            self._cv.notify_all()

        return future

    async def run_all(
        self,
        factories: Iterable[Callable[[], Awaitable[T]]],
        *,
        shard_key: int | None = None,
    ) -> list[T]:
        futures: list[asyncio.Future[T]] = []
        for f in factories:
            fut = await self.submit(f, shard_key=shard_key)
            futures.append(fut)
        results: list[T] = await asyncio.gather(*futures)
        return list(results)

    def _try_take_from_shard(
        self, shard_index: int
    ) -> tuple[bool, tuple[Callable[[], Awaitable[T]], asyncio.Future[T]] | None]:
        shard = self._shards[shard_index]
        if shard:
            # Pop newest from own shard
            item = shard.pop()
            return True, item
        return False, None

    def _try_steal_from_others(
        self, self_index: int
    ) -> tuple[bool, tuple[Callable[[], Awaitable[T]], asyncio.Future[T]] | None]:
        # Oldest-first from other shards
        for offset in range(1, self._num_shards + 1):
            idx = (self_index + offset) % self._num_shards
            shard = self._shards[idx]
            if shard:
                item = shard.popleft()
                return True, item
        return False, None

    async def _worker_loop(self, worker_index: int) -> None:
        try:
            while True:
                # Attempt to get work from own shard first
                got, item = self._try_take_from_shard(worker_index % self._num_shards)
                if not got:
                    # Steal from others if own shard empty
                    got, item = self._try_steal_from_others(
                        worker_index % self._num_shards
                    )

                if not got:
                    # No work available; wait for signal
                    async with self._cv:
                        await self._cv.wait()
                    continue

                assert item is not None
                factory, future = item
                if future.cancelled():
                    # Release capacity for cancelled work
                    self._capacity_sem.release()
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
                        # Release capacity slot
                        self._capacity_sem.release()
        except asyncio.CancelledError:
            return

    async def _shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Wait until all shards are drained
        # Signal workers in case they are waiting
        async with self._cv:
            self._cv.notify_all()

        # Busy-wait cooperatively until all shards empty
        while any(self._shards):
            await asyncio.sleep(0)

        # Cancel workers and await completion
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def close(self) -> None:
        """Alias for ``_shutdown`` for symmetry with context management.

        This mirrors the behavior of ``__aexit__`` and is provided as a
        convenience when using the executor outside ``async with`` blocks.
        """
        await self._shutdown()


# Mark selected callables as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, object] = (
    NonBlockingRingQueue.await_enqueue,
    NonBlockingRingQueue.await_dequeue,
)
