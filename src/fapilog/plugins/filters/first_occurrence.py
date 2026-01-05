from __future__ import annotations

import random
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class FirstOccurrenceConfig:
    """Configuration for first-occurrence filter."""

    key_fields: list[str] | None = None
    window_seconds: float = 60.0
    max_keys: int = 10000
    subsequent_sample_rate: float = 0.0

    def __post_init__(self) -> None:
        if self.key_fields is None:
            self.key_fields = ["message"]


class FirstOccurrenceFilter:
    """First occurrence of a unique key always passes."""

    name = "first_occurrence"

    def __init__(
        self, *, config: FirstOccurrenceConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = self._parse_config(config, kwargs)
        self._key_fields = cfg.key_fields
        self._window = max(0.0, float(cfg.window_seconds))
        self._max_keys = max(1, int(cfg.max_keys))
        self._subsequent_rate = max(0.0, min(1.0, float(cfg.subsequent_sample_rate)))
        self._seen: OrderedDict[str, float] = OrderedDict()

    @staticmethod
    def _parse_config(
        config: FirstOccurrenceConfig | dict | None, kwargs: dict[str, Any]
    ) -> FirstOccurrenceConfig:
        if isinstance(config, dict):
            raw = config.get("config", config)
            return FirstOccurrenceConfig(**raw)
        if config is None:
            raw_kwargs = kwargs.get("config", kwargs)
            return (
                FirstOccurrenceConfig(**raw_kwargs)
                if raw_kwargs
                else FirstOccurrenceConfig()
            )
        return config

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
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
}
