"""Dynamic worker pool for adaptive scaling (Story 1.46).

Manages initial (static) and dynamic worker tasks. Dynamic workers can
be added and retired based on queue pressure levels. Initial workers
persist for the logger lifetime and are only stopped during drain.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Coroutine
from typing import Any

from .pressure import PressureLevel

# Scaling ladder: pressure level → worker count multiplier of initial count
WORKER_SCALE: dict[PressureLevel, float] = {
    PressureLevel.NORMAL: 1.0,
    PressureLevel.ELEVATED: 1.0,
    PressureLevel.HIGH: 1.5,
    PressureLevel.CRITICAL: 2.0,
}

# Type for the worker factory: takes a stop_flag callable, returns a coroutine
WorkerFactory = Callable[[Callable[[], bool]], Coroutine[Any, Any, None]]


class WorkerPool:
    """Pool that manages initial and dynamically-scaled worker tasks.

    Initial workers run for the logger lifetime. Dynamic workers are
    added/retired based on pressure levels via ``scale_to()``.

    Args:
        initial_count: Number of workers created at startup (never scaled below).
        max_workers: Maximum total workers (initial + dynamic).
        worker_factory: Async callable that accepts a stop_flag and runs a worker loop.
        loop: Event loop for creating tasks.
    """

    def __init__(
        self,
        initial_count: int,
        max_workers: int,
        worker_factory: WorkerFactory,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._initial_count = initial_count
        self._max_workers = max(initial_count, max_workers)
        self._factory = worker_factory
        self._loop = loop
        self._initial_tasks: list[asyncio.Task[None]] = []
        # Each dynamic entry: (task, stop_flag_setter)
        self._dynamic: list[tuple[asyncio.Task[None], _StopFlag]] = []

    @property
    def current_count(self) -> int:
        """Total active workers (initial + dynamic)."""
        return self._initial_count + len(self._dynamic)

    @property
    def dynamic_count(self) -> int:
        """Number of currently active dynamic workers."""
        return len(self._dynamic)

    def target_for_level(self, level: PressureLevel) -> int:
        """Compute target worker count for a pressure level.

        Multiplies initial_count by the scaling factor and rounds up.
        Result is clamped to [initial_count, max_workers].
        """
        raw = self._initial_count * WORKER_SCALE[level]
        target = math.ceil(raw)
        return max(self._initial_count, min(self._max_workers, target))

    def register_initial_tasks(self, tasks: list[asyncio.Task[None]]) -> None:
        """Register the initial worker tasks created by the logger."""
        self._initial_tasks = list(tasks)

    def scale_to(self, target: int) -> None:
        """Scale worker count to target (bounded by min/max).

        Adding workers creates new asyncio tasks via the factory.
        Retiring workers sets their individual stop flags; they finish
        their current batch and exit gracefully.
        """
        target = max(self._initial_count, min(self._max_workers, target))
        current = self.current_count

        if target > current:
            self._add_workers(target - current)
        elif target < current:
            self._retire_workers(current - target)

    def _add_workers(self, count: int) -> None:
        """Create additional dynamic worker tasks."""
        for _ in range(count):
            flag = _StopFlag()
            task = self._loop.create_task(self._factory(flag))
            self._dynamic.append((task, flag))

    def _retire_workers(self, count: int) -> None:
        """Retire the most recently added dynamic workers.

        Sets their stop flags so they exit after completing their
        current batch. Removes them from the active dynamic list.
        """
        to_retire = min(count, len(self._dynamic))
        for _ in range(to_retire):
            task, flag = self._dynamic.pop()  # LIFO: most recent first
            flag.set()

    def drain_all(self) -> list[asyncio.Task[None]]:
        """Stop all dynamic workers and return all tasks for awaiting.

        Sets stop flags on all remaining dynamic workers. Returns the
        combined list of initial + dynamic tasks so the caller can
        ``asyncio.gather()`` them.
        """
        all_tasks = list(self._initial_tasks)
        for task, flag in self._dynamic:
            flag.set()
            all_tasks.append(task)
        self._dynamic.clear()
        return all_tasks

    def all_tasks(self) -> list[asyncio.Task[None]]:
        """Return all active tasks (initial + dynamic) without stopping."""
        tasks = list(self._initial_tasks)
        tasks.extend(task for task, _ in self._dynamic)
        return tasks


class _StopFlag:
    """Mutable boolean callable for per-worker stop signaling."""

    __slots__ = ("_stopped",)

    def __init__(self) -> None:
        self._stopped = False

    def __call__(self) -> bool:
        return self._stopped

    def set(self) -> None:
        self._stopped = True


# Mark public API for vulture (Story 1.46)
_VULTURE_USED: tuple[object, ...] = (
    WorkerPool.target_for_level,
    WorkerPool.register_initial_tasks,
    WorkerPool.scale_to,
    WorkerPool.drain_all,
    WorkerPool.all_tasks,
    WorkerPool.current_count,
    WorkerPool.dynamic_count,
    WORKER_SCALE,
    WorkerFactory,
)
