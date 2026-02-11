"""Unit tests for WorkerPool dynamic worker scaling (Story 1.46)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from fapilog.core.pressure import PressureLevel
from fapilog.core.worker_pool import WORKER_SCALE, WorkerPool


def _make_pool(
    initial_count: int = 2,
    max_workers: int = 6,
    loop: asyncio.AbstractEventLoop | None = None,
) -> WorkerPool:
    """Create a WorkerPool with a mock worker factory."""
    factory = MagicMock()

    async def _fake_worker(stop_flag: Any) -> None:
        while not stop_flag():
            await asyncio.sleep(0.01)

    factory.side_effect = _fake_worker
    return WorkerPool(
        initial_count=initial_count,
        max_workers=max_workers,
        worker_factory=factory,
        loop=loop or asyncio.get_event_loop(),
    )


class TestWorkerScale:
    def test_scale_ladder_normal(self) -> None:
        assert WORKER_SCALE[PressureLevel.NORMAL] == 1.0

    def test_scale_ladder_elevated(self) -> None:
        assert WORKER_SCALE[PressureLevel.ELEVATED] == 1.0

    def test_scale_ladder_high(self) -> None:
        assert WORKER_SCALE[PressureLevel.HIGH] == 1.5

    def test_scale_ladder_critical(self) -> None:
        assert WORKER_SCALE[PressureLevel.CRITICAL] == 2.0


class TestWorkerPoolScaling:
    @pytest.mark.asyncio
    async def test_initial_worker_count(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        assert pool.current_count == 2
        assert pool.dynamic_count == 0

    @pytest.mark.asyncio
    async def test_scale_up_adds_dynamic_workers(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        pool.scale_to(4)
        assert pool.current_count == 4
        assert pool.dynamic_count == 2

    @pytest.mark.asyncio
    async def test_scale_down_retires_dynamic_workers(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        pool.scale_to(4)
        assert pool.dynamic_count == 2
        pool.scale_to(2)
        # Dynamic workers flagged to stop
        assert pool.dynamic_count == 0

    @pytest.mark.asyncio
    async def test_never_below_initial_count(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        pool.scale_to(1)  # Below initial
        assert pool.current_count == 2

    @pytest.mark.asyncio
    async def test_never_above_max_workers(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        pool.scale_to(10)  # Above max
        assert pool.current_count == 6
        assert pool.dynamic_count == 4

    @pytest.mark.asyncio
    async def test_scale_to_same_is_noop(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        pool.scale_to(2)
        assert pool.dynamic_count == 0

    @pytest.mark.asyncio
    async def test_target_from_pressure_level(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        target = pool.target_for_level(PressureLevel.HIGH)
        # 2 * 1.5 = 3.0 → ceil = 3
        assert target == 3

    @pytest.mark.asyncio
    async def test_target_from_critical_level(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        target = pool.target_for_level(PressureLevel.CRITICAL)
        # 2 * 2.0 = 4.0 → 4
        assert target == 4

    @pytest.mark.asyncio
    async def test_target_capped_at_max_workers(self) -> None:
        pool = _make_pool(initial_count=4, max_workers=6)
        target = pool.target_for_level(PressureLevel.CRITICAL)
        # 4 * 2.0 = 8.0, but max = 6
        assert target == 6


class TestWorkerPoolDrain:
    @pytest.mark.asyncio
    async def test_drain_all_returns_all_tasks(self) -> None:
        loop = asyncio.get_event_loop()

        async def _fake(stop_flag: Any) -> None:
            while not stop_flag():
                await asyncio.sleep(0.01)

        pool = WorkerPool(
            initial_count=2,
            max_workers=6,
            worker_factory=_fake,
            loop=loop,
        )
        # Simulate what logger does: register initial tasks
        initial = [loop.create_task(_fake(lambda: False)) for _ in range(2)]
        pool.register_initial_tasks(initial)
        pool.scale_to(4)
        tasks = pool.drain_all()
        # Should return initial + dynamic tasks
        assert len(tasks) == 4
        # Cleanup
        for t in initial:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_drain_sets_all_dynamic_stop_flags(self) -> None:
        pool = _make_pool(initial_count=2, max_workers=6)
        pool.scale_to(4)
        pool.drain_all()
        # All dynamic workers should be flagged
        assert pool.dynamic_count == 0


class TestWorkerPoolDynamicWorkerLifecycle:
    @pytest.mark.asyncio
    async def test_dynamic_worker_receives_stop_flag(self) -> None:
        """Dynamic workers get a stop_flag callable that returns True when retired."""
        stop_flags: list[Any] = []

        async def _capture_factory(stop_flag: Any) -> None:
            stop_flags.append(stop_flag)
            while not stop_flag():
                await asyncio.sleep(0.01)

        loop = asyncio.get_event_loop()
        pool = WorkerPool(
            initial_count=1,
            max_workers=4,
            worker_factory=_capture_factory,
            loop=loop,
        )
        pool.scale_to(2)  # Add 1 dynamic worker
        await asyncio.sleep(0.05)  # Let worker start
        assert len(stop_flags) == 1
        assert stop_flags[0]() is False  # Not stopped yet

        pool.scale_to(1)  # Retire
        assert stop_flags[0]() is True  # Now flagged to stop

    @pytest.mark.asyncio
    async def test_scale_down_retires_most_recent_first(self) -> None:
        """When scaling down, retire the most recently added workers first."""
        stop_flags: list[Any] = []

        async def _capture_factory(stop_flag: Any) -> None:
            stop_flags.append(stop_flag)
            while not stop_flag():
                await asyncio.sleep(0.01)

        loop = asyncio.get_event_loop()
        pool = WorkerPool(
            initial_count=1,
            max_workers=4,
            worker_factory=_capture_factory,
            loop=loop,
        )
        pool.scale_to(3)  # Add 2 dynamic workers
        await asyncio.sleep(0.05)

        pool.scale_to(2)  # Retire 1 (most recent)
        assert stop_flags[1]() is True  # 2nd added → retired first
        assert stop_flags[0]() is False  # 1st added → still active
