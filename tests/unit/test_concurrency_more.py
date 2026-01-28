import asyncio

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.errors import TimeoutError


@pytest.mark.asyncio
async def test_non_blocking_ring_queue():
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert (await q.await_enqueue(1)) is None
    with pytest.raises(TimeoutError):
        await q.await_enqueue(2, timeout=0.01)
    ok, v = q.try_dequeue()
    assert ok and v == 1


def test_ring_queue_rejects_invalid_capacity() -> None:
    with pytest.raises(ValueError, match="capacity must be > 0"):
        NonBlockingRingQueue(capacity=0)


def test_ring_queue_try_enqueue_and_dequeue_edges() -> None:
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert q.try_enqueue(1) is True
    assert q.try_enqueue(2) is False
    ok, item = q.try_dequeue()
    assert ok is True
    assert item == 1
    ok, item = q.try_dequeue()
    assert ok is False
    assert item is None


@pytest.mark.asyncio
async def test_ring_queue_dequeue_timeout() -> None:
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    with pytest.raises(TimeoutError):
        await q.await_dequeue(timeout=0.01)


# Story 12.23: Event signaling tests


@pytest.mark.asyncio
async def test_await_enqueue_uses_event_not_spin() -> None:
    """await_enqueue should use event signaling, not spin-wait.

    Verifies that the queue has _space_available Event attribute,
    indicating event-based signaling is implemented.
    """
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)

    # Queue should have event attributes for signaling
    assert hasattr(q, "_space_available"), "Queue should have _space_available event"
    assert isinstance(q._space_available, asyncio.Event), (
        "_space_available should be an asyncio.Event"
    )


@pytest.mark.asyncio
async def test_await_dequeue_uses_event_not_spin() -> None:
    """await_dequeue should use event signaling, not spin-wait.

    Verifies that the queue has _data_available Event attribute,
    indicating event-based signaling is implemented.
    """
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)

    # Queue should have event attributes for signaling
    assert hasattr(q, "_data_available"), "Queue should have _data_available event"
    assert isinstance(q._data_available, asyncio.Event), (
        "_data_available should be an asyncio.Event"
    )


@pytest.mark.asyncio
async def test_dequeue_signals_waiting_enqueuer() -> None:
    """Dequeue should wake up a waiting enqueuer via event signaling."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    # Fill the queue
    assert q.try_enqueue(1) is True

    enqueue_completed = False

    async def enqueue_waiter() -> None:
        nonlocal enqueue_completed
        await q.await_enqueue(2, timeout=1.0)
        enqueue_completed = True

    # Start waiting enqueuer
    task = asyncio.create_task(enqueue_waiter())
    # Give it time to start waiting
    await asyncio.sleep(0.01)

    # Dequeue should signal the waiter
    ok, item = q.try_dequeue()
    assert ok is True
    assert item == 1

    # Wait for enqueue to complete
    await asyncio.wait_for(task, timeout=0.5)
    assert enqueue_completed is True

    # Verify item was enqueued
    ok, item = q.try_dequeue()
    assert ok is True
    assert item == 2


@pytest.mark.asyncio
async def test_enqueue_signals_waiting_dequeuer() -> None:
    """Enqueue should wake up a waiting dequeuer via event signaling."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    # Queue is empty

    dequeue_result: int | None = None

    async def dequeue_waiter() -> None:
        nonlocal dequeue_result
        dequeue_result = await q.await_dequeue(timeout=1.0)

    # Start waiting dequeuer
    task = asyncio.create_task(dequeue_waiter())
    # Give it time to start waiting
    await asyncio.sleep(0.01)

    # Enqueue should signal the waiter
    assert q.try_enqueue(42) is True

    # Wait for dequeue to complete
    await asyncio.wait_for(task, timeout=0.5)
    assert dequeue_result == 42


@pytest.mark.asyncio
async def test_multiple_enqueuers_wake_correctly() -> None:
    """Multiple waiting enqueuers should be awakened as space becomes available."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    # Fill the queue
    assert q.try_enqueue(0) is True

    results: list[int] = []

    async def enqueue_waiter(value: int) -> None:
        await q.await_enqueue(value, timeout=2.0)
        results.append(value)

    # Start multiple waiting enqueuers
    tasks = [asyncio.create_task(enqueue_waiter(i)) for i in range(1, 4)]
    # Give them time to start waiting
    await asyncio.sleep(0.01)

    # Dequeue repeatedly to make space and wake waiters
    for _ in range(3):
        q.try_dequeue()
        await asyncio.sleep(0.01)  # Let awakened task run

    # Wait for all tasks
    await asyncio.gather(*tasks, return_exceptions=True)

    # All should have completed
    assert len(results) == 3
    assert set(results) == {1, 2, 3}


@pytest.mark.asyncio
async def test_multiple_dequeuers_wake_correctly() -> None:
    """Multiple waiting dequeuers should be awakened as data becomes available."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=3)
    # Queue is empty

    results: list[int] = []

    async def dequeue_waiter() -> None:
        item = await q.await_dequeue(timeout=2.0)
        results.append(item)

    # Start multiple waiting dequeuers
    tasks = [asyncio.create_task(dequeue_waiter()) for _ in range(3)]
    # Give them time to start waiting
    await asyncio.sleep(0.01)

    # Enqueue items to wake waiters
    for i in range(3):
        q.try_enqueue(i + 1)
        await asyncio.sleep(0.01)  # Let awakened task run

    # Wait for all tasks
    await asyncio.gather(*tasks, return_exceptions=True)

    # All should have completed
    assert len(results) == 3
    assert set(results) == {1, 2, 3}


@pytest.mark.asyncio
async def test_timeout_during_retry_loop_enqueue() -> None:
    """Timeout should be checked during retry loop, not just on wait."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    assert q.try_enqueue(0) is True  # Fill queue

    # Create a situation where waiter wakes but can't enqueue, times out on retry
    async def slow_consumer() -> None:
        await asyncio.sleep(0.05)  # Let enqueuer start waiting
        q.try_dequeue()  # Wake enqueuer
        # Immediately fill queue again before enqueuer can act
        q.try_enqueue(99)

    task = asyncio.create_task(slow_consumer())

    # Very short timeout - should timeout during retry check
    with pytest.raises(TimeoutError):
        await q.await_enqueue(1, timeout=0.06)

    await task


@pytest.mark.asyncio
async def test_timeout_during_retry_loop_dequeue() -> None:
    """Timeout should be checked during retry loop for dequeue."""
    q: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1)
    # Queue is empty

    async def tease_dequeuer() -> None:
        await asyncio.sleep(0.05)  # Let dequeuer start waiting
        q.try_enqueue(1)  # Wake dequeuer
        # Immediately empty queue again before dequeuer can act
        q.try_dequeue()

    task = asyncio.create_task(tease_dequeuer())

    # Very short timeout - should timeout during retry check
    with pytest.raises(TimeoutError):
        await q.await_dequeue(timeout=0.06)

    await task
