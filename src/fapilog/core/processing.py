"""
Core parallel processing utilities for the async-first pipeline (Story 2.2a).

This module provides:
- gather_with_limit: Run awaitables in parallel with bounded concurrency
- process_in_parallel: Helper to apply an async function to a collection with
  limits

Design goals:
- Pure async/await with `asyncio.gather`
- Controlled concurrency using `asyncio.Semaphore`
- Zero-copy friendly: values are passed through unchanged unless the worker
  transforms them
- Error isolation: first exception propagates; optional gather
  `return_exceptions` can be used by callers
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def _with_semaphore(
    semaphore: asyncio.Semaphore, coro_factory: Callable[[], Awaitable[R]]
) -> R:
    async with semaphore:
        return await coro_factory()


async def gather_with_limit(
    coroutines: Iterable[Callable[[], Awaitable[R]]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R | BaseException]:
    """
    Execute coroutine factories in parallel with a concurrency limit.

    Args:
        coroutines: Iterable of zero-arg callables that create coroutines when
            invoked.
        limit: Maximum number of concurrent tasks.
        return_exceptions: If True, exceptions are returned in the results
            list.

    Returns:
        List of results in the same order as the input.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")

    semaphore = asyncio.Semaphore(limit)
    tasks: list[asyncio.Task[R]] = []
    for factory in coroutines:
        tasks.append(asyncio.create_task(_with_semaphore(semaphore, factory)))

    results: list[R | BaseException] = await asyncio.gather(
        *tasks, return_exceptions=return_exceptions
    )
    return results


async def process_in_parallel(
    values: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R | BaseException]:
    """
    Apply an async worker to values in parallel with a concurrency limit.

    Preserves input order in results.
    """

    def make_factory(value: T) -> Callable[[], Awaitable[R]]:
        async def run() -> R:
            return await worker(value)

        return run

    factories: list[Callable[[], Awaitable[R]]] = [make_factory(v) for v in values]
    results: list[R | BaseException] = await gather_with_limit(
        factories, limit=limit, return_exceptions=return_exceptions
    )
    return results
