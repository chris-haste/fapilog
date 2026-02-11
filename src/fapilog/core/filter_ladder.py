"""Adaptive filter ladder builder (Story 1.45).

Pre-builds filter tuples for each pressure level at startup.
Workers pick up the active tuple via lock-free snapshot swap.

Escalation ladder:
  NORMAL   — user-configured filters unchanged
  ELEVATED — tighten adaptive sampling (halve target_eps or inject one)
  HIGH     — inject WARNING-level gate (drop DEBUG/INFO)
  CRITICAL — protected-levels-only gate
"""

from __future__ import annotations

from typing import Any

from .pressure import PressureLevel


def build_filter_ladder(
    base_filters: list[Any],
    protected_levels: frozenset[str],
) -> dict[PressureLevel, tuple[Any, ...]]:
    """Pre-build filter tuples for each pressure level.

    Args:
        base_filters: User-configured filter instances (NORMAL level).
        protected_levels: Level names that must always pass (e.g. ERROR, CRITICAL).

    Returns:
        Dict mapping each PressureLevel to an immutable tuple of filter instances.
    """
    return {
        PressureLevel.NORMAL: tuple(base_filters),
        PressureLevel.ELEVATED: _build_elevated_filters(base_filters, protected_levels),
        PressureLevel.HIGH: _build_high_filters(base_filters),
        PressureLevel.CRITICAL: _build_critical_filters(protected_levels),
    }


def _build_elevated_filters(
    base_filters: list[Any],
    protected_levels: frozenset[str],
) -> tuple[Any, ...]:
    """ELEVATED: tighten or inject adaptive sampling.

    If user already has an AdaptiveSamplingFilter, create a copy with halved
    target_eps. Otherwise inject a new one with target_eps=50.
    """
    from ..plugins.filters.adaptive_sampling import (
        AdaptiveSamplingConfig,
        AdaptiveSamplingFilter,
    )

    result: list[Any] = []
    found_adaptive = False

    for f in base_filters:
        if isinstance(f, AdaptiveSamplingFilter):
            found_adaptive = True
            tightened = AdaptiveSamplingFilter(
                config=AdaptiveSamplingConfig(
                    target_eps=f._target_eps / 2.0,
                    min_sample_rate=f._min_rate,
                    max_sample_rate=f._max_rate,
                    window_seconds=f._window,
                    always_pass_levels=sorted(f._always_pass | protected_levels),
                    smoothing_factor=f._smoothing,
                )
            )
            result.append(tightened)
        else:
            result.append(f)

    if not found_adaptive:
        injected = AdaptiveSamplingFilter(
            config=AdaptiveSamplingConfig(
                target_eps=50.0,
                always_pass_levels=sorted(protected_levels),
            )
        )
        result.append(injected)

    return tuple(result)


def _build_high_filters(base_filters: list[Any]) -> tuple[Any, ...]:
    """HIGH: inject WARNING-level gate before user filters.

    Drops everything below WARNING (DEBUG, INFO) post-dequeue.
    """
    from ..plugins.filters.level import LevelFilter, LevelFilterConfig

    warning_gate = LevelFilter(config=LevelFilterConfig(min_level="WARNING"))
    return (warning_gate, *base_filters)


def _build_critical_filters(protected_levels: frozenset[str]) -> tuple[Any, ...]:
    """CRITICAL: allow only protected levels.

    Finds the minimum priority among protected levels and creates a
    single level filter at that threshold.
    """
    from ..plugins.filters.level import LevelFilter, LevelFilterConfig
    from .levels import get_level_priority

    if not protected_levels:
        # No protected levels — block everything by using FATAL
        return (LevelFilter(config=LevelFilterConfig(min_level="FATAL")),)

    # Find the lowest priority among protected levels
    min_priority_level = min(protected_levels, key=get_level_priority)
    return (LevelFilter(config=LevelFilterConfig(min_level=min_priority_level)),)


# Mark public API for vulture (Story 1.45)
_VULTURE_USED: tuple[object, ...] = (build_filter_ladder,)
