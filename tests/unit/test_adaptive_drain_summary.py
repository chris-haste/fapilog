"""Unit tests for AdaptiveDrainSummary dataclass and DrainResult.adaptive field."""

from __future__ import annotations

import pytest

from fapilog.core.logger import AdaptiveDrainSummary, DrainResult
from fapilog.core.pressure import PressureLevel


class TestAdaptiveDrainSummary:
    def test_dataclass_is_frozen(self) -> None:
        summary = AdaptiveDrainSummary(
            peak_pressure_level=PressureLevel.NORMAL,
            escalation_count=0,
            deescalation_count=0,
            time_at_level=dict.fromkeys(PressureLevel, 0.0),
            filters_swapped=0,
            workers_scaled=0,
            peak_workers=1,
            batch_resize_count=0,
        )
        with pytest.raises(AttributeError):
            summary.escalation_count = 5  # type: ignore[misc]

    def test_all_fields_required(self) -> None:
        with pytest.raises(TypeError):
            AdaptiveDrainSummary()  # type: ignore[call-arg]

    def test_construction_with_all_fields(self) -> None:
        summary = AdaptiveDrainSummary(
            peak_pressure_level=PressureLevel.HIGH,
            escalation_count=3,
            deescalation_count=2,
            time_at_level={
                PressureLevel.NORMAL: 45.2,
                PressureLevel.ELEVATED: 12.8,
                PressureLevel.HIGH: 3.1,
                PressureLevel.CRITICAL: 0.0,
            },
            filters_swapped=3,
            workers_scaled=2,
            peak_workers=6,
            batch_resize_count=8,
        )
        assert summary.peak_pressure_level == PressureLevel.HIGH
        assert summary.escalation_count == 3
        assert summary.deescalation_count == 2
        assert summary.time_at_level[PressureLevel.NORMAL] == 45.2
        assert summary.filters_swapped == 3
        assert summary.workers_scaled == 2
        assert summary.peak_workers == 6
        assert summary.batch_resize_count == 8


class TestDrainResultAdaptiveField:
    def test_drain_result_adaptive_defaults_to_none(self) -> None:
        result = DrainResult(
            submitted=10,
            processed=9,
            dropped=1,
            retried=0,
            queue_depth_high_watermark=5,
            flush_latency_seconds=0.1,
        )
        assert result.adaptive is None

    def test_drain_result_accepts_adaptive_summary(self) -> None:
        summary = AdaptiveDrainSummary(
            peak_pressure_level=PressureLevel.ELEVATED,
            escalation_count=1,
            deescalation_count=0,
            time_at_level=dict.fromkeys(PressureLevel, 1.0),
            filters_swapped=1,
            workers_scaled=0,
            peak_workers=2,
            batch_resize_count=0,
        )
        result = DrainResult(
            submitted=5,
            processed=5,
            dropped=0,
            retried=0,
            queue_depth_high_watermark=3,
            flush_latency_seconds=0.05,
            adaptive=summary,
        )
        assert result.adaptive is summary
        assert result.adaptive.peak_pressure_level == PressureLevel.ELEVATED


class TestAdaptiveDrainSummaryExport:
    def test_importable_from_fapilog(self) -> None:
        from fapilog import AdaptiveDrainSummary as Exported

        assert Exported is AdaptiveDrainSummary
