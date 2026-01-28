from __future__ import annotations

import random
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..utils import parse_plugin_config


class SamplingFilterConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    seed: int | None = None


class SamplingFilter:
    """Probabilistic sampling filter."""

    name = "sampling"

    def __init__(
        self, *, config: SamplingFilterConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(SamplingFilterConfig, config, **kwargs)
        self._rate = cfg.sample_rate
        self._rng = random.Random(cfg.seed)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        if self._rate >= 1.0:
            return event
        if self._rate <= 0.0:
            return None
        return event if self._rng.random() < self._rate else None

    @property
    def current_sample_rate(self) -> float:
        return self._rate

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "sampling",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.sampling:SamplingFilter",
    "description": "Probabilistic sampling filter.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
