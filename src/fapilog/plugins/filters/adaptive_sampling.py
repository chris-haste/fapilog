from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdaptiveSamplingConfig:
    """Configuration for adaptive sampling."""

    target_eps: float = 100.0
    min_sample_rate: float = 0.01
    max_sample_rate: float = 1.0
    window_seconds: float = 10.0
    always_pass_levels: list[str] = field(
        default_factory=lambda: ["ERROR", "CRITICAL", "FATAL"]
    )
    smoothing_factor: float = 0.3


class AdaptiveSamplingFilter:
    """Dynamically adjusts sampling based on recent throughput."""

    name = "adaptive_sampling"

    def __init__(
        self, *, config: AdaptiveSamplingConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = self._parse_config(config, kwargs)
        self._target_eps = max(0.0, float(cfg.target_eps))
        self._min_rate = max(0.0, min(1.0, float(cfg.min_sample_rate)))
        self._max_rate = max(self._min_rate, min(1.0, float(cfg.max_sample_rate)))
        self._window = max(0.001, float(cfg.window_seconds))
        self._always_pass = {level.upper() for level in cfg.always_pass_levels}
        self._smoothing = max(0.0, min(1.0, float(cfg.smoothing_factor)))

        self._current_rate = 1.0
        self._timestamps: deque[float] = deque()
        self._last_adjustment = time.monotonic()

    @staticmethod
    def _parse_config(
        config: AdaptiveSamplingConfig | dict | None, kwargs: dict[str, Any]
    ) -> AdaptiveSamplingConfig:
        if isinstance(config, dict):
            raw = config.get("config", config)
            return AdaptiveSamplingConfig(**raw)
        if config is None:
            raw_kwargs = kwargs.get("config", kwargs)
            return (
                AdaptiveSamplingConfig(**raw_kwargs)
                if raw_kwargs
                else AdaptiveSamplingConfig()
            )
        return config

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
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
}
