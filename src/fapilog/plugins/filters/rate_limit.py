from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from ...core import diagnostics


@dataclass
class RateLimitFilterConfig:
    capacity: int = 10  # tokens
    refill_rate_per_sec: float = 5.0  # tokens per second
    key_field: str | None = None  # event key used to partition buckets
    max_keys: int = 10000  # Max buckets to track
    overflow_action: str = "drop"  # "drop" or "mark"


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
        self._max_keys = max(1, int(cfg.max_keys))
        action = str(cfg.overflow_action).lower()
        self._overflow_action = action if action in {"drop", "mark"} else "drop"
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()
        self._warned_capacity = False

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def filter(self, event: dict) -> dict | None:
        key = self._resolve_key(event)
        now = time.monotonic()
        if key not in self._buckets and len(self._buckets) >= self._max_keys:
            self._evict_oldest()
        tokens, last = self._buckets.get(key, (self._capacity, now))
        # Refill
        elapsed = max(0.0, now - last)
        tokens = min(self._capacity, tokens + elapsed * self._refill_rate)
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
        self._buckets[key] = (tokens, now)
        self._buckets.move_to_end(key)
        self._check_capacity_warn()
        if not allowed:
            if self._overflow_action == "mark":
                cloned = dict(event)
                cloned["rate_limited"] = True
                return cloned
            return None
        return event

    def _resolve_key(self, event: dict) -> str:
        if not self._key_field:
            return "global"
        return str(event.get(self._key_field, "global"))

    def _evict_oldest(self) -> None:
        try:
            self._buckets.popitem(last=False)
        except Exception:
            return

    def _check_capacity_warn(self) -> None:
        size = len(self._buckets)
        threshold = int(self._max_keys * 0.9)
        if size >= threshold:
            if not self._warned_capacity:
                try:
                    diagnostics.warn(
                        "filter",
                        "rate_limit approaching max_keys",
                        filter="rate_limit",
                        max_keys=self._max_keys,
                        keys_tracked=size,
                    )
                except Exception:
                    pass
            self._warned_capacity = True
        elif size < max(1, int(self._max_keys * 0.8)):
            self._warned_capacity = False

    @property
    def tracked_key_count(self) -> int:
        return len(self._buckets)

    async def health_check(self) -> bool:
        if len(self._buckets) > self._max_keys * 0.9:
            self._check_capacity_warn()
            return False
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
