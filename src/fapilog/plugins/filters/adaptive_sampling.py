from __future__ import annotations

import random
import time
from collections import deque
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..utils import parse_plugin_config


class AdaptiveSamplingConfig(BaseModel):
    """Configuration for adaptive sampling."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    target_eps: float = Field(default=100.0, ge=0.0)
    min_sample_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    max_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    window_seconds: float = Field(default=10.0, gt=0.0)
    always_pass_levels: list[str] = Field(
        default_factory=lambda: ["ERROR", "CRITICAL", "FATAL"]
    )
    smoothing_factor: float = Field(default=0.3, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_ranges(self) -> AdaptiveSamplingConfig:
        if self.max_sample_rate < self.min_sample_rate:
            raise ValueError("max_sample_rate must be >= min_sample_rate")
        return self


class AdaptiveSamplingFilter:
    """Dynamically adjusts sampling based on recent throughput."""

    name = "adaptive_sampling"

    def __init__(
        self, *, config: AdaptiveSamplingConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(AdaptiveSamplingConfig, config, **kwargs)
        self._target_eps = cfg.target_eps
        self._min_rate = cfg.min_sample_rate
        self._max_rate = cfg.max_sample_rate
        self._window = cfg.window_seconds
        self._always_pass = {level.upper() for level in cfg.always_pass_levels}
        self._smoothing = cfg.smoothing_factor

        self._current_rate = 1.0
        self._timestamps: deque[float] = deque()
        self._last_adjustment = time.monotonic()

    async def start(self) -> None:
        self._timestamps.clear()
        self._current_rate = 1.0
        self._last_adjustment = time.monotonic()

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        level = str(event.get("level", "INFO")).upper()

        if level in self._always_pass:
            self._record_event()
            return event

        if random.random() > self._current_rate:
            return None

        self._record_event()
        self._maybe_adjust_rate()
        return event

    def _record_event(self) -> None:
        now = time.monotonic()
        self._timestamps.append(now)
        cutoff = now - self._window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def _maybe_adjust_rate(self) -> None:
        now = time.monotonic()
        if now - self._last_adjustment < 1.0:
            return

        self._last_adjustment = now

        if not self._timestamps:
            current_eps = 0.0
        else:
            elapsed = max(now - self._timestamps[0], 0.001)
            current_eps = len(self._timestamps) / elapsed

        if current_eps <= 0:
            ideal_rate = self._max_rate
        else:
            ideal_rate = self._target_eps / current_eps

        ideal_rate = max(self._min_rate, min(self._max_rate, ideal_rate))
        self._current_rate = (
            self._smoothing * ideal_rate + (1.0 - self._smoothing) * self._current_rate
        )

    @property
    def current_sample_rate(self) -> float:
        return self._current_rate

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "adaptive_sampling",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.adaptive_sampling:AdaptiveSamplingFilter",
    "description": "Dynamically adjusts sample rate based on throughput.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}

# Mark Pydantic validators as used for vulture
_VULTURE_USED: tuple[object, ...] = (AdaptiveSamplingConfig._validate_ranges,)
