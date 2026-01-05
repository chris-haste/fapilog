from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class SamplingFilterConfig:
    sample_rate: float = 1.0
    seed: int | None = None


class SamplingFilter:
    """Probabilistic sampling filter."""

    name = "sampling"

    def __init__(
        self, *, config: SamplingFilterConfig | dict | None = None, **kwargs: Any
    ) -> None:
        if isinstance(config, dict):
            raw = config.get("config", config)
            cfg = SamplingFilterConfig(**raw)
        elif config is None:
            raw_kwargs = kwargs.get("config", kwargs)
            cfg = (
                SamplingFilterConfig(**raw_kwargs)
                if raw_kwargs
                else SamplingFilterConfig()
            )
        else:
            cfg = config
        self._rate = max(0.0, min(1.0, float(cfg.sample_rate)))
        if cfg.seed is not None:
            random.seed(cfg.seed)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        if self._rate >= 1.0:
            return event
        if self._rate <= 0.0:
            return None
        return event if random.random() < self._rate else None

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "sampling",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.sampling:SamplingFilter",
    "description": "Probabilistic sampling filter.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
}
