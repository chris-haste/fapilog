"""Integration tests for DualQueue protected drain (Story 1.52)."""

from __future__ import annotations

from typing import Any

import pytest

from fapilog.core.concurrency import DualQueue
from fapilog.metrics.metrics import MetricsCollector


class TestProtectedEventsSurviveMainQueuePressure:
    """Protected events survive when main queue is under pressure."""

    def test_protected_events_survive_main_queue_pressure(self) -> None:
        dq = DualQueue(
            main_capacity=5,
            protected_capacity=10,
            protected_levels=frozenset({"ERROR", "CRITICAL"}),
        )
        # Fill main queue completely
        for i in range(5):
            dq.try_enqueue({"level": "INFO", "msg": f"info-{i}"})
        assert dq.main_is_full()

        # Protected events still get through
        for i in range(3):
            result = dq.try_enqueue({"level": "ERROR", "msg": f"error-{i}"})
            assert result is True

        assert dq.protected_qsize() == 3
        assert dq.main_qsize() == 5


class TestDrainOrderProtectedBeforeMain:
    """Drain always returns protected events first."""

    def test_drain_order_protected_before_main(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        # Enqueue alternating
        for i in range(10):
            level = "ERROR" if i % 3 == 0 else "INFO"
            dq.try_enqueue({"level": level, "msg": f"event-{i}"})

        batch: list[dict[str, Any]] = []
        dq.drain_into(batch)

        # All ERROR events come first
        error_indices = [i for i, e in enumerate(batch) if e["level"] == "ERROR"]
        info_indices = [i for i, e in enumerate(batch) if e["level"] == "INFO"]
        assert max(error_indices) < min(info_indices)


class TestProtectedDropEmitsDiagnostic:
    """Protected queue drops are tracked separately."""

    def test_protected_drop_tracked(self) -> None:
        dq = DualQueue(
            main_capacity=100,
            protected_capacity=2,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "ERROR", "msg": "1"})
        dq.try_enqueue({"level": "ERROR", "msg": "2"})
        result = dq.try_enqueue({"level": "ERROR", "msg": "3"})
        assert result is False
        assert dq.protected_drops == 1

    def test_main_drop_tracked_separately(self) -> None:
        dq = DualQueue(
            main_capacity=2,
            protected_capacity=100,
            protected_levels=frozenset({"ERROR"}),
        )
        dq.try_enqueue({"level": "INFO", "msg": "1"})
        dq.try_enqueue({"level": "INFO", "msg": "2"})
        dq.try_enqueue({"level": "INFO", "msg": "3"})  # dropped
        assert dq.main_drops == 1
        assert dq.protected_drops == 0


class TestPressureMonitorReadsDualQueue:
    """Pressure monitor uses main_qsize() for DualQueue fill ratio."""

    @pytest.mark.asyncio
    async def test_pressure_uses_main_qsize_not_total(self) -> None:
        from fapilog.core.pressure import PressureMonitor

        dq = DualQueue(
            main_capacity=100,
            protected_capacity=50,
            protected_levels=frozenset({"ERROR"}),
        )
        # Fill protected queue (should not affect pressure)
        for i in range(30):
            dq.try_enqueue({"level": "ERROR", "msg": f"err-{i}"})

        monitor = PressureMonitor(
            queue=dq,
            check_interval_seconds=1.0,
            cooldown_seconds=0.0,
        )
        # Tick should use main_qsize() = 0, not qsize() = 30
        monitor._tick()
        # Should still be NORMAL since main queue is empty
        from fapilog.core.pressure import PressureLevel

        assert monitor._state_machine.current_level == PressureLevel.NORMAL


class TestQueueDepthGauge:
    """AC6: Queue depth gauges with queue label."""

    @pytest.mark.asyncio
    async def test_set_queue_depth_main(self) -> None:
        mc = MetricsCollector(enabled=True)
        await mc.set_queue_depth("main", 42)
        # Verify gauge was set (no exception)
        sample = mc._g_queue_depth.labels(queue="main")._value.get()
        assert sample == 42.0

    @pytest.mark.asyncio
    async def test_set_queue_depth_protected(self) -> None:
        mc = MetricsCollector(enabled=True)
        await mc.set_queue_depth("protected", 7)
        sample = mc._g_queue_depth.labels(queue="protected")._value.get()
        assert sample == 7.0

    @pytest.mark.asyncio
    async def test_set_queue_depth_disabled_noop(self) -> None:
        mc = MetricsCollector(enabled=False)
        await mc.set_queue_depth("main", 42)  # Should not raise
