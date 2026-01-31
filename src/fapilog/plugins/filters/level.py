from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from ...core.levels import get_level_priority
from ..utils import parse_plugin_config

# Maintain LEVEL_PRIORITY for backward compatibility (external code may import it)
# But internally we use get_level_priority() from the registry
LEVEL_PRIORITY = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
    "FATAL": 50,
}


class LevelFilterConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    min_level: str = "INFO"
    drop_below: bool = True


class LevelFilter:
    """Filter events by log level threshold."""

    name = "level"

    def __init__(
        self, *, config: LevelFilterConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(LevelFilterConfig, config, **kwargs)
        self._min_priority = get_level_priority(cfg.min_level)
        self._drop_below = bool(cfg.drop_below)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        level = str(event.get("level", "INFO")).upper()
        priority = get_level_priority(level)
        if self._drop_below and priority < self._min_priority:
            return None
        return event

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "level",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.level:LevelFilter",
    "description": "Filter events by minimum level threshold.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
