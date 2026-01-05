from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class RateLimitFilterConfig:
    capacity: int = 10  # tokens
    refill_rate_per_sec: float = 5.0  # tokens per second
    key_field: str | None = None  # event key used to partition buckets


class RateLimitFilter:
    """Token-bucket rate limiter."""

    name = "rate_limit"

    def __init__(
        self, *, config: RateLimitFilterConfig | dict | None = None, **kwargs: Any
    ) -> None:
        if isinstance(config, dict):
            raw = config.get("config", config)
            cfg = RateLimitFilterConfig(**raw)
        elif config is None:
            raw_kwargs = kwargs.get("config", kwargs)
            cfg = (
                RateLimitFilterConfig(**raw_kwargs)
                if raw_kwargs
                else RateLimitFilterConfig()
            )
        else:
            cfg = config
        self._capacity = max(1, int(cfg.capacity))
        self._refill_rate = max(0.0, float(cfg.refill_rate_per_sec))
        self._key_field = cfg.key_field
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, ts)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        key = self._resolve_key(event)
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (self._capacity, now))
        # Refill
        elapsed = max(0.0, now - last)
        tokens = min(self._capacity, tokens + elapsed * self._refill_rate)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return None
        tokens -= 1.0
        self._buckets[key] = (tokens, now)
        return event

    def _resolve_key(self, event: dict) -> str:
        if not self._key_field:
            return "global"
        return str(event.get(self._key_field, "global"))

    async def health_check(self) -> bool:
        return True


PLUGIN_METADATA = {
    "name": "rate_limit",
    "version": "1.0.0",
    "plugin_type": "filter",
    "entry_point": "fapilog.plugins.filters.rate_limit:RateLimitFilter",
    "description": "Token bucket rate limiter filter.",
    "author": "Fapilog Core",
    "compatibility": {"min_fapilog_version": "0.4.0"},
    "api_version": "1.0",
}
