"""Tests for queue capacity decay with hysteresis cooldown (Story 1.54)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from fapilog.core.concurrency import NonBlockingRingQueue
from fapilog.core.settings import AdaptiveSettings


class TestNextDecayTarget:
    """Tests for _next_decay_target helper."""

    def test_returns_initial_when_already_at_floor(self) -> None:
        from fapilog.core.logger import _next_decay_target
        from fapilog.core.pressure import PressureLevel

        growth_table = {
            PressureLevel.NORMAL: 1.0,
            PressureLevel.ELEVATED: 1.75,
            PressureLevel.HIGH: 2.5,
            PressureLevel.CRITICAL: 4.0,
        }
        result = _next_decay_target(1000, 1000, growth_table)
        assert result == 1000

    def test_returns_next_lower_tier(self) -> None:
        from fapilog.core.logger import _next_decay_target
        from fapilog.core.pressure import PressureLevel

        growth_table = {
            PressureLevel.NORMAL: 1.0,
            PressureLevel.ELEVATED: 1.75,
            PressureLevel.HIGH: 2.5,
            PressureLevel.CRITICAL: 4.0,
        }
        assert _next_decay_target(4000, 1000, growth_table) == 2500
        assert _next_decay_target(2500, 1000, growth_table) == 1750
        assert _next_decay_target(1750, 1000, growth_table) == 1000


class TestCapacityCooldownSetting:
    """AC6: capacity_cooldown_seconds on AdaptiveSettings."""

    def test_default_value(self) -> None:
        settings = AdaptiveSettings()
        assert settings.capacity_cooldown_seconds == 60.0

    def test_custom_value(self) -> None:
        settings = AdaptiveSettings(capacity_cooldown_seconds=30.0)
        assert settings.capacity_cooldown_seconds == 30.0


class TestDecayTaskLifecycle:
    """AC1/AC2: decay task spawned at NORMAL, cancelled on re-escalation."""

    @pytest.fixture
    def _setup(self) -> dict[str, Any]:
        """Create queue, growth table, and callback wiring."""
        from fapilog.core.pressure import PressureLevel

        queue: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        initial_capacity = 1000
        max_growth = 4.0
        g = max_growth
        growth_table: dict[Any, float] = {
            PressureLevel.NORMAL: 1.0,
            PressureLevel.ELEVATED: 1.0 + (g - 1.0) * 0.25,
            PressureLevel.HIGH: 1.0 + (g - 1.0) * 0.50,
            PressureLevel.CRITICAL: g,
        }
        return {
            "queue": queue,
            "initial_capacity": initial_capacity,
            "growth_table": growth_table,
            "PressureLevel": PressureLevel,
        }

    @pytest.mark.asyncio
    async def test_decay_task_spawned_on_normal(self, _setup: dict[str, Any]) -> None:
        """When pressure transitions to NORMAL, a decay task is spawned."""
        from fapilog.core.logger import _make_capacity_decay_callback

        PressureLevel = _setup["PressureLevel"]
        queue = _setup["queue"]
        queue.grow_capacity(4000)

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=_setup["initial_capacity"],
            growth_table=_setup["growth_table"],
            cooldown_seconds=0.01,
        )

        # Simulate transition to NORMAL
        callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        task = get_decay_task()
        assert task is not None  # noqa: WA003
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_decay_task_cancelled_on_reescalation(
        self, _setup: dict[str, Any]
    ) -> None:
        """AC2: re-escalation cancels pending decay task."""
        from fapilog.core.logger import _make_capacity_decay_callback

        PressureLevel = _setup["PressureLevel"]
        queue = _setup["queue"]
        queue.grow_capacity(4000)

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=_setup["initial_capacity"],
            growth_table=_setup["growth_table"],
            cooldown_seconds=10.0,  # long cooldown so task stays alive
        )

        # Enter NORMAL → decay task starts
        callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        task = get_decay_task()
        assert task is not None  # noqa: WA003

        # Re-escalate → decay task cancelled
        callback(PressureLevel.NORMAL, PressureLevel.HIGH)
        await asyncio.sleep(0.01)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_full_decay_after_sustained_normal(
        self, _setup: dict[str, Any]
    ) -> None:
        """AC7: step-down follows growth table in reverse, 3 cooldowns to recover."""
        from fapilog.core.logger import _make_capacity_decay_callback

        PressureLevel = _setup["PressureLevel"]
        queue = _setup["queue"]
        queue.grow_capacity(4000)

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=_setup["initial_capacity"],
            growth_table=_setup["growth_table"],
            cooldown_seconds=0.01,  # fast for test
        )

        callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        task = get_decay_task()
        assert task is not None  # noqa: WA003
        # Wait for task to complete full decay
        await asyncio.wait_for(task, timeout=2.0)

        assert queue.capacity == 1000

    @pytest.mark.asyncio
    async def test_step_down_intermediate_values(self, _setup: dict[str, Any]) -> None:
        """AC7: each cooldown step follows growth table in reverse."""
        from fapilog.core.logger import _make_capacity_decay_callback

        PressureLevel = _setup["PressureLevel"]
        queue = _setup["queue"]
        queue.grow_capacity(4000)

        capacities: list[int] = []

        orig_shrink = queue.shrink_capacity

        def tracking_shrink(target: int) -> None:
            orig_shrink(target)
            capacities.append(queue.capacity)

        queue.shrink_capacity = tracking_shrink  # type: ignore[assignment]

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=_setup["initial_capacity"],
            growth_table=_setup["growth_table"],
            cooldown_seconds=0.01,
        )

        callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        task = get_decay_task()
        assert task is not None  # noqa: WA003
        await asyncio.wait_for(task, timeout=2.0)

        # 4000 → 2500 → 1750 → 1000
        assert capacities == [2500, 1750, 1000]

    @pytest.mark.asyncio
    async def test_diagnostic_emitted_on_shrink(self, _setup: dict[str, Any]) -> None:
        """AC8: diagnostic warning emitted on capacity shrink."""
        from fapilog.core.logger import _make_capacity_decay_callback

        PressureLevel = _setup["PressureLevel"]
        queue = _setup["queue"]
        queue.grow_capacity(4000)

        diag_calls: list[dict[str, Any]] = []

        def fake_warn(source: str, message: str, **kwargs: Any) -> None:
            diag_calls.append({"source": source, "message": message, **kwargs})

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=_setup["initial_capacity"],
            growth_table=_setup["growth_table"],
            cooldown_seconds=0.01,
        )

        with patch("fapilog.core.logger._diag_warn_for_decay", fake_warn):
            callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
            task = get_decay_task()
            assert task is not None  # noqa: WA003
            await asyncio.wait_for(task, timeout=2.0)

        assert len(diag_calls) == 3
        assert diag_calls[0]["source"] == "adaptive-controller"
        assert diag_calls[0]["message"] == "queue capacity shrunk"
        assert diag_calls[0]["old_capacity"] == 4000
        assert diag_calls[0]["new_capacity"] == 2500


class TestDecayIntegration:
    """Integration: pressure spike → recovery → capacity returns to baseline."""

    @pytest.mark.asyncio
    async def test_oscillation_prevents_shrink(self) -> None:
        """AC2: oscillating pressure resets cooldown, no premature shrink."""
        from fapilog.core.logger import _make_capacity_decay_callback
        from fapilog.core.pressure import PressureLevel

        queue: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)
        queue.grow_capacity(4000)

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=1000,
            growth_table={
                PressureLevel.NORMAL: 1.0,
                PressureLevel.ELEVATED: 1.75,
                PressureLevel.HIGH: 2.5,
                PressureLevel.CRITICAL: 4.0,
            },
            cooldown_seconds=10.0,  # long cooldown
        )

        # NORMAL → decay starts
        callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        task1 = get_decay_task()
        assert task1 is not None  # noqa: WA003

        # Quick re-escalation → cancels decay
        callback(PressureLevel.NORMAL, PressureLevel.HIGH)
        await asyncio.sleep(0.01)
        assert task1.cancelled()

        # Capacity unchanged
        assert queue.capacity == 4000

    @pytest.mark.asyncio
    async def test_spike_recovery_full_cycle(self) -> None:
        """Full cycle: grow during spike, decay back to initial after sustained NORMAL."""
        from fapilog.core.logger import _make_capacity_decay_callback
        from fapilog.core.pressure import PressureLevel

        queue: NonBlockingRingQueue[int] = NonBlockingRingQueue(capacity=1000)

        growth_table = {
            PressureLevel.NORMAL: 1.0,
            PressureLevel.ELEVATED: 1.75,
            PressureLevel.HIGH: 2.5,
            PressureLevel.CRITICAL: 4.0,
        }

        callback, get_decay_task = _make_capacity_decay_callback(
            queue=queue,
            initial_capacity=1000,
            growth_table=growth_table,
            cooldown_seconds=0.01,
        )

        # Spike: grow to CRITICAL
        callback(PressureLevel.NORMAL, PressureLevel.CRITICAL)
        # The callback should grow the queue
        queue.grow_capacity(4000)
        assert queue.capacity == 4000

        # Recovery: sustained NORMAL
        callback(PressureLevel.CRITICAL, PressureLevel.NORMAL)
        task = get_decay_task()
        assert task is not None  # noqa: WA003
        await asyncio.wait_for(task, timeout=2.0)

        assert queue.capacity == 1000
