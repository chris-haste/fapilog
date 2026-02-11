"""Unit tests for pressure level gauge metric."""

from __future__ import annotations

import pytest

from fapilog.metrics.metrics import MetricsCollector


class TestPressureLevelGauge:
    @pytest.mark.asyncio
    async def test_set_pressure_level_when_enabled(self) -> None:
        mc = MetricsCollector(enabled=True)
        await mc.set_pressure_level(2)
        # Verify gauge was set to expected value via prometheus registry
        assert mc._g_pressure_level._value.get() == 2.0

    @pytest.mark.asyncio
    async def test_set_pressure_level_noop_when_disabled(self) -> None:
        mc = MetricsCollector(enabled=False)
        await mc.set_pressure_level(1)
        assert mc._g_pressure_level is None
