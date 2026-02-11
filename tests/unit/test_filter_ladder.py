"""Unit tests for adaptive filter ladder builder (Story 1.45)."""

from __future__ import annotations

from typing import Any

from fapilog.core.pressure import PressureLevel
from fapilog.plugins.filters.adaptive_sampling import (
    AdaptiveSamplingConfig,
    AdaptiveSamplingFilter,
)
from fapilog.plugins.filters.level import LevelFilter, LevelFilterConfig


class TestBuildFilterLadder:
    """Tests for build_filter_ladder() factory."""

    def test_ladder_contains_all_four_levels(self) -> None:
        """Ladder returns a dict with all four PressureLevel keys."""
        from fapilog.core.filter_ladder import build_filter_ladder

        ladder = build_filter_ladder(
            base_filters=[],
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        assert set(ladder.keys()) == {
            PressureLevel.NORMAL,
            PressureLevel.ELEVATED,
            PressureLevel.HIGH,
            PressureLevel.CRITICAL,
        }

    def test_all_ladder_entries_are_tuples(self) -> None:
        """Each ladder entry is a tuple (immutable for lock-free swap)."""
        from fapilog.core.filter_ladder import build_filter_ladder

        ladder = build_filter_ladder(
            base_filters=[],
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        for level, filters in ladder.items():
            assert isinstance(filters, tuple), f"{level} entry is not a tuple"


class TestNormalLevel:
    """AC2: NORMAL level uses user-configured filters unchanged."""

    def test_normal_level_matches_user_config(self) -> None:
        """NORMAL level returns exact same filters as user configured."""
        from fapilog.core.filter_ladder import build_filter_ladder

        user_filters: list[Any] = [
            LevelFilter(config=LevelFilterConfig(min_level="INFO")),
        ]
        ladder = build_filter_ladder(
            base_filters=user_filters,
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        normal = ladder[PressureLevel.NORMAL]
        assert len(normal) == 1
        assert normal[0] is user_filters[0]

    def test_normal_preserves_multiple_user_filters(self) -> None:
        """NORMAL level preserves all user filters in order."""
        from fapilog.core.filter_ladder import build_filter_ladder

        f1 = LevelFilter(config=LevelFilterConfig(min_level="INFO"))
        f2 = LevelFilter(config=LevelFilterConfig(min_level="DEBUG"))
        ladder = build_filter_ladder(
            base_filters=[f1, f2],
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        normal = ladder[PressureLevel.NORMAL]
        assert normal == (f1, f2)


class TestElevatedLevel:
    """AC3: ELEVATED level tightens adaptive sampling."""

    def test_elevated_injects_adaptive_sampling(self) -> None:
        """When user has no adaptive sampling, ELEVATED injects one."""
        from fapilog.core.filter_ladder import build_filter_ladder

        user_filters: list[Any] = [
            LevelFilter(config=LevelFilterConfig(min_level="INFO")),
        ]
        ladder = build_filter_ladder(
            base_filters=user_filters,
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        elevated = ladder[PressureLevel.ELEVATED]
        # Should contain original filters + injected adaptive sampling
        adaptive_filters = [
            f for f in elevated if isinstance(f, AdaptiveSamplingFilter)
        ]
        assert len(adaptive_filters) == 1
        assert adaptive_filters[0]._target_eps == 50.0
        # Protected levels should include user-configured protected levels
        assert "ERROR" in adaptive_filters[0]._always_pass
        assert "CRITICAL" in adaptive_filters[0]._always_pass

    def test_elevated_tightens_existing_adaptive_sampling(self) -> None:
        """When user already has adaptive sampling, ELEVATED halves its target_eps."""
        from fapilog.core.filter_ladder import build_filter_ladder

        user_adaptive = AdaptiveSamplingFilter(
            config=AdaptiveSamplingConfig(target_eps=200.0)
        )
        user_filters: list[Any] = [user_adaptive]
        ladder = build_filter_ladder(
            base_filters=user_filters,
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        elevated = ladder[PressureLevel.ELEVATED]
        adaptive_filters = [
            f for f in elevated if isinstance(f, AdaptiveSamplingFilter)
        ]
        assert len(adaptive_filters) == 1
        # Should be halved from user's 200.0
        assert adaptive_filters[0]._target_eps == 100.0
        # Should be a different instance (not mutating the user's filter)
        assert adaptive_filters[0] is not user_adaptive

    def test_elevated_preserves_user_filters(self) -> None:
        """ELEVATED keeps non-adaptive user filters in place."""
        from fapilog.core.filter_ladder import build_filter_ladder

        level_f = LevelFilter(config=LevelFilterConfig(min_level="INFO"))
        user_filters: list[Any] = [level_f]
        ladder = build_filter_ladder(
            base_filters=user_filters,
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        elevated = ladder[PressureLevel.ELEVATED]
        assert level_f in elevated


class TestHighLevel:
    """AC4: HIGH level drops DEBUG and INFO entirely."""

    def test_high_drops_debug_and_info(self) -> None:
        """HIGH level injects a LevelFilter with min_level=WARNING."""
        from fapilog.core.filter_ladder import build_filter_ladder

        user_filters: list[Any] = [
            LevelFilter(config=LevelFilterConfig(min_level="INFO")),
        ]
        ladder = build_filter_ladder(
            base_filters=user_filters,
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        high = ladder[PressureLevel.HIGH]
        # Should have a level filter that blocks below WARNING
        level_filters = [f for f in high if isinstance(f, LevelFilter)]
        assert len(level_filters) == 2  # injected WARNING gate + user's INFO filter
        # The tightest level filter should block INFO
        from fapilog.core.levels import get_level_priority

        warning_priority = get_level_priority("WARNING")
        has_warning_gate = any(
            f._min_priority >= warning_priority for f in level_filters
        )
        assert has_warning_gate

    def test_high_preserves_user_filters(self) -> None:
        """HIGH level keeps remaining user filters after injecting level gate."""
        from fapilog.core.filter_ladder import build_filter_ladder

        user_level = LevelFilter(config=LevelFilterConfig(min_level="INFO"))
        user_filters: list[Any] = [user_level]
        ladder = build_filter_ladder(
            base_filters=user_filters,
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        high = ladder[PressureLevel.HIGH]
        # User filters should still be present
        assert user_level in high


class TestCriticalLevel:
    """AC5: CRITICAL level allows only protected levels."""

    def test_critical_allows_only_protected_levels(self) -> None:
        """CRITICAL level creates a filter that only passes protected levels."""
        from fapilog.core.filter_ladder import build_filter_ladder

        protected = frozenset({"ERROR", "CRITICAL", "FATAL", "AUDIT", "SECURITY"})
        ladder = build_filter_ladder(
            base_filters=[],
            protected_levels=protected,
        )
        critical = ladder[PressureLevel.CRITICAL]
        # Should have exactly one level filter for protected-only
        assert len(critical) == 1
        assert isinstance(critical[0], LevelFilter)
        # Verify it passes ERROR (priority 40) but not INFO (priority 20)
        from fapilog.core.levels import get_level_priority

        error_priority = get_level_priority("ERROR")
        assert critical[0]._min_priority <= error_priority

    def test_custom_protected_levels_respected(self) -> None:
        """CRITICAL level respects custom protected_levels set."""
        from fapilog.core.filter_ladder import build_filter_ladder

        # Only FATAL protected
        ladder = build_filter_ladder(
            base_filters=[],
            protected_levels=frozenset({"FATAL"}),
        )
        critical = ladder[PressureLevel.CRITICAL]
        assert len(critical) == 1
        from fapilog.core.levels import get_level_priority

        fatal_priority = get_level_priority("FATAL")
        assert critical[0]._min_priority == fatal_priority


class TestElevatedWithEmptyFilters:
    """Edge case: no user filters at all."""

    def test_elevated_with_no_user_filters(self) -> None:
        """ELEVATED still injects adaptive sampling when user has no filters."""
        from fapilog.core.filter_ladder import build_filter_ladder

        ladder = build_filter_ladder(
            base_filters=[],
            protected_levels=frozenset({"ERROR", "CRITICAL", "FATAL"}),
        )
        elevated = ladder[PressureLevel.ELEVATED]
        adaptive_filters = [
            f for f in elevated if isinstance(f, AdaptiveSamplingFilter)
        ]
        assert len(adaptive_filters) == 1
