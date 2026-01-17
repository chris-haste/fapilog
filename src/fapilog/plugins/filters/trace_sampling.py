from __future__ import annotations

import hashlib
import random
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..utils import parse_plugin_config


class TraceSamplingConfig(BaseModel):
    """Configuration for trace-aware sampling."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    trace_id_field: str = "trace_id"
    always_pass_levels: list[str] = Field(default_factory=lambda: ["ERROR", "CRITICAL"])


class TraceSamplingFilter:
    """Sample consistently by trace ID."""

    name = "trace_sampling"

    def __init__(
        self, *, config: TraceSamplingConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(TraceSamplingConfig, config, **kwargs)
        self._rate = cfg.sample_rate
        self._trace_field = cfg.trace_id_field
        self._always_pass = {level.upper() for level in cfg.always_pass_levels}

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        level = str(event.get("level", "INFO")).upper()
        if level in self._always_pass:
            return event

        trace_id = event.get(self._trace_field)
        if trace_id is None:
            if random.random() > self._rate:
                return None
            return event

        hash_value = int(hashlib.md5(str(trace_id).encode()).hexdigest(), 16)
        threshold = int(self._rate * (2**128))
        if hash_value < threshold:
            return event
        return None

    @property
    def current_sample_rate(self) -> float:
        return self._rate

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "trace_sampling",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.trace_sampling:TraceSamplingFilter",
    "description": "Deterministic sampling keyed by trace_id.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
