"""Async context propagation helpers.

Provides utilities for preserving contextvars across async boundaries
where Python doesn't automatically propagate them:
- asyncio.create_task() (pre-Python 3.11)
- ThreadPoolExecutor / run_in_executor()
- asyncio.gather() with separately created tasks

Example:
    >>> import fapilog
    >>> from fapilog.context import create_task_with_context
    >>>
    >>> async def background_work():
    ...     logger = fapilog.get_logger()
    ...     logger.info("background task")  # includes parent context
    ...
    >>> async def main():
    ...     logger = fapilog.get_logger().bind(request_id="req-123")
    ...     task = create_task_with_context(background_work())
    ...     await task
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
from concurrent.futures import Executor
from typing import Any, Callable, Coroutine, TypeVar

__all__ = [
    "create_task_with_context",
    "run_in_executor_with_context",
    "preserve_context",
]

T = TypeVar("T")


def create_task_with_context(
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
) -> asyncio.Task[T]:
    """Create an asyncio task that inherits the current context.

    Unlike asyncio.create_task(), this explicitly copies all contextvars
    (including fapilog bindings) into the new task at call time.

    Args:
        coro: The coroutine to run.
        name: Optional task name for debugging.

    Returns:
        Task with copied context.

    Example:
        >>> async def worker():
        ...     # Context variables from parent are available here
        ...     pass
        ...
        >>> task = create_task_with_context(worker(), name="my-worker")
        >>> await task
    """
    ctx = contextvars.copy_context()

    async def _run_in_context() -> T:
        return await coro

    # Create task within the copied context
    return ctx.run(asyncio.create_task, _run_in_context(), name=name)


async def run_in_executor_with_context(
    executor: Executor | None,
    func: Callable[..., T],
    *args: Any,
) -> T:
    """Run a sync function in an executor with current context.

    Preserves all contextvars when executing synchronous code in a
    ThreadPoolExecutor or other executor.

    Args:
        executor: Executor to use (None for default loop executor).
        func: Sync function to run.
        *args: Arguments to pass to func.

    Returns:
        Result of func(*args).

    Example:
        >>> def sync_work():
        ...     # Context variables from caller are available here
        ...     pass
        ...
        >>> await run_in_executor_with_context(executor, sync_work)
    """
    ctx = contextvars.copy_context()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        executor,
        functools.partial(ctx.run, func, *args),
    )


def preserve_context(
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, T]]:
    """Decorator to preserve context when function is scheduled as a task.

    When an async function decorated with @preserve_context is called,
    it captures the current context and runs within that captured context.
    This ensures context is preserved even when the function is scheduled
    via asyncio.create_task() or similar.

    Example:
        >>> @preserve_context
        ... async def my_worker():
        ...     # Context is preserved even when called via create_task()
        ...     pass
        ...
        >>> asyncio.create_task(my_worker())  # Context preserved
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        # Capture context at call time, run coroutine within it
        ctx = contextvars.copy_context()
        return await ctx.run(func, *args, **kwargs)

    return wrapper
