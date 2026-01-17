from __future__ import annotations

import random
import time
from collections import OrderedDict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..utils import parse_plugin_config


class FirstOccurrenceConfig(BaseModel):
    """Configuration for first-occurrence filter."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    key_fields: list[str] = Field(default_factory=lambda: ["message"])
    window_seconds: float = Field(default=60.0, ge=0.0)
    max_keys: int = Field(default=10000, ge=1)
    subsequent_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class FirstOccurrenceFilter:
    """First occurrence of a unique key always passes."""

    name = "first_occurrence"

    def __init__(
        self, *, config: FirstOccurrenceConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(FirstOccurrenceConfig, config, **kwargs)
        self._key_fields = cfg.key_fields
        self._window = cfg.window_seconds
        self._max_keys = cfg.max_keys
        self._subsequent_rate = cfg.subsequent_sample_rate
        self._seen: OrderedDict[str, float] = OrderedDict()

    async def start(self) -> None:
        self._seen.clear()

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        key = self._make_key(event)
        now = time.monotonic()
        self._prune_expired(now)

        if key not in self._seen:
            self._seen[key] = now
            self._seen.move_to_end(key)
            while len(self._seen) > self._max_keys:
                self._seen.popitem(last=False)
            return event

        if self._subsequent_rate <= 0.0:
            return None

        if random.random() < self._subsequent_rate:
            return event
        return None

    def _make_key(self, event: dict) -> str:
        parts = [str(event.get(field, "")) for field in (self._key_fields or [])]
        return "|".join(parts)

    def _prune_expired(self, now: float) -> None:
        cutoff = now - self._window
        while self._seen:
            _, oldest_time = next(iter(self._seen.items()))
            if oldest_time < cutoff:
                self._seen.popitem(last=False)
            else:
                break

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "first_occurrence",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.first_occurrence:FirstOccurrenceFilter",
    "description": "Pass first occurrences of unique messages with optional sampling.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}
