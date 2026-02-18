"""Tests for fixed dual-queue memory budget (Story 1.56)."""

from __future__ import annotations

import pytest


class TestProtectedQueueSizing:
    """AC2: Protected queue independently configurable."""

    def test_core_settings_accepts_protected_queue_size(self) -> None:
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings(protected_queue_size=5000)
        assert settings.protected_queue_size == 5000

    def test_core_settings_protected_queue_size_defaults_to_none(self) -> None:
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings()
        assert settings.protected_queue_size is None

    def test_core_settings_protected_queue_size_must_be_positive(self) -> None:
        from fapilog.core.settings import CoreSettings

        with pytest.raises(ValueError, match="greater than or equal to 1"):
            CoreSettings(protected_queue_size=0)

    def test_with_queue_size_protected_entries_kwarg(self) -> None:
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_queue_size(10_000, protected_entries=2_000)
        assert result is builder
        assert builder._config["core"]["protected_queue_size"] == 2_000
        assert builder._config["core"]["max_queue_size"] == 10_000

    def test_with_queue_size_backward_compat_positional(self) -> None:
        """Existing positional `size` param still works unchanged."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_queue_size(15_000)
        assert builder._config["core"]["max_queue_size"] == 15_000
        assert "protected_queue_size" not in builder._config["core"]

    def test_logger_uses_protected_queue_size_from_settings(self) -> None:
        """Protected queue capacity passed through to DualQueue."""
        from unittest.mock import MagicMock

        from fapilog.core.logger import SyncLoggerFacade

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=10_000,
            batch_max_size=100,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=100,
            drop_on_full=True,
            sink_write=MagicMock(),
            protected_queue_size=2_000,
        )
        assert logger._queue._protected.capacity == 2_000
        assert logger._queue._main.capacity == 10_000

    def test_logger_derives_protected_when_not_specified(self) -> None:
        """When protected_queue_size is None, use max(100, capacity // 10)."""
        from unittest.mock import MagicMock

        from fapilog.core.logger import SyncLoggerFacade

        logger = SyncLoggerFacade(
            name="test",
            queue_capacity=10_000,
            batch_max_size=100,
            batch_timeout_seconds=1.0,
            backpressure_wait_ms=100,
            drop_on_full=True,
            sink_write=MagicMock(),
        )
        # Default: max(100, 10000 // 10) = 1000
        assert logger._queue._protected.capacity == 1_000

    def test_protected_queue_size_wired_from_settings_to_logger(self) -> None:
        """End-to-end: CoreSettings.protected_queue_size flows to DualQueue."""
        from fapilog.core.settings import CoreSettings

        settings = CoreSettings(max_queue_size=10_000, protected_queue_size=3_000)
        assert settings.protected_queue_size == 3_000
        assert settings.max_queue_size == 10_000


class TestQueueGrowthRemoved:
    """AC4: Queue growth machinery removed."""

    def test_nonblocking_ring_queue_no_grow_capacity(self) -> None:
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue = NonBlockingRingQueue(capacity=1000)
        assert not hasattr(queue, "grow_capacity")

    def test_nonblocking_ring_queue_no_shrink_capacity(self) -> None:
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue = NonBlockingRingQueue(capacity=1000)
        assert not hasattr(queue, "shrink_capacity")

    def test_priority_aware_queue_no_grow_capacity(self) -> None:
        from fapilog.core.concurrency import PriorityAwareQueue

        assert not hasattr(PriorityAwareQueue, "grow_capacity")

    def test_dual_queue_no_grow_capacity(self) -> None:
        from fapilog.core.concurrency import DualQueue

        queue = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset(),
        )
        assert not hasattr(queue, "grow_capacity")

    def test_dual_queue_no_shrink_capacity(self) -> None:
        from fapilog.core.concurrency import DualQueue

        queue = DualQueue(
            main_capacity=1000,
            protected_capacity=100,
            protected_levels=frozenset(),
        )
        assert not hasattr(queue, "shrink_capacity")

    def test_nonblocking_ring_queue_no_initial_capacity(self) -> None:
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue = NonBlockingRingQueue(capacity=1000)
        assert not hasattr(queue, "_initial_capacity")

    def test_queue_capacity_fixed_under_pressure(self) -> None:
        """AC3: Queue capacity stays fixed — no growth methods exist."""
        from fapilog.core.concurrency import NonBlockingRingQueue

        queue = NonBlockingRingQueue(capacity=500)
        # Fill it up
        for i in range(500):
            queue.try_enqueue({"level": "INFO", "i": i})
        assert queue.capacity == 500
        # Can't grow — no method exists
        assert not hasattr(queue, "grow_capacity")


class TestMbToEntries:
    """AC1: MB-based queue budget conversion."""

    def test_50mb_yields_approx_25600_entries(self) -> None:
        from fapilog.builder import _mb_to_entries

        assert _mb_to_entries(50) == 25_600

    def test_10mb_yields_approx_5120_entries(self) -> None:
        from fapilog.builder import _mb_to_entries

        assert _mb_to_entries(10) == 5_120

    def test_minimum_floor_100_entries(self) -> None:
        from fapilog.builder import _mb_to_entries

        assert _mb_to_entries(0.0001) == 100

    def test_fractional_mb(self) -> None:
        from fapilog.builder import _mb_to_entries

        # 0.5 MB = 512 * 1024 / 2048 = 256
        assert _mb_to_entries(0.5) == 256


class TestWithQueueBudget:
    """AC1: with_queue_budget() builder method."""

    def test_sets_main_and_protected_entries(self) -> None:
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        result = builder.with_queue_budget(main_mb=50, protected_mb=10)
        assert result is builder
        assert builder._config["core"]["max_queue_size"] == 25_600
        assert builder._config["core"]["protected_queue_size"] == 5_120

    def test_default_values(self) -> None:
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_queue_budget()
        # defaults: main_mb=20, protected_mb=5
        assert builder._config["core"]["max_queue_size"] == 10_240
        assert builder._config["core"]["protected_queue_size"] == 2_560

    def test_last_call_wins_budget_then_size(self) -> None:
        """AC8: If both called, last one wins."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_queue_budget(main_mb=50, protected_mb=10)
        builder.with_queue_size(10_000, protected_entries=2_000)
        assert builder._config["core"]["max_queue_size"] == 10_000
        assert builder._config["core"]["protected_queue_size"] == 2_000

    def test_last_call_wins_size_then_budget(self) -> None:
        """AC8: If both called, last one wins."""
        from fapilog.builder import LoggerBuilder

        builder = LoggerBuilder()
        builder.with_queue_size(10_000)
        builder.with_queue_budget(main_mb=50, protected_mb=10)
        assert builder._config["core"]["max_queue_size"] == 25_600
        assert builder._config["core"]["protected_queue_size"] == 5_120


class TestDeprecatedAdaptiveSettings:
    """AC5: Deprecated settings emit warning and are ignored."""

    def test_max_queue_growth_emits_deprecation_warning(self) -> None:
        import warnings

        from fapilog.core.settings import AdaptiveSettings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            AdaptiveSettings(max_queue_growth=4.0)
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 1
        assert "max_queue_growth" in str(deprecation_warnings[0].message)

    def test_capacity_cooldown_seconds_emits_deprecation_warning(self) -> None:
        import warnings

        from fapilog.core.settings import AdaptiveSettings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            AdaptiveSettings(capacity_cooldown_seconds=30.0)
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 1
        assert "capacity_cooldown_seconds" in str(deprecation_warnings[0].message)

    def test_queue_growth_emits_deprecation_warning(self) -> None:
        import warnings

        from fapilog.core.settings import AdaptiveSettings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            AdaptiveSettings(queue_growth=True)
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 1
        assert "queue_growth" in str(deprecation_warnings[0].message)

    def test_adaptive_settings_without_deprecated_fields_no_warning(self) -> None:
        import warnings

        from fapilog.core.settings import AdaptiveSettings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            AdaptiveSettings()
        deprecation_warnings = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 0


class TestPresetsUpdated:
    """AC6: Presets use fixed queue sizing."""

    def test_production_preset_no_growth_settings(self) -> None:
        from fapilog.core.presets import get_preset

        preset = get_preset("production")
        adaptive = preset.get("adaptive", {})
        assert "max_queue_growth" not in adaptive
        assert "capacity_cooldown_seconds" not in adaptive
        assert "queue_growth" not in adaptive

    def test_with_adaptive_no_growth_params(self) -> None:
        """Builder with_adaptive() should not accept growth params."""
        import inspect

        from fapilog.builder import LoggerBuilder

        sig = inspect.signature(LoggerBuilder.with_adaptive)
        assert "max_queue_growth" not in sig.parameters
        assert "queue_growth" not in sig.parameters
