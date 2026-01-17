from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core import diagnostics
from ..utils import parse_plugin_config


class RateLimitFilterConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    capacity: int = Field(default=10, ge=1)  # tokens
    refill_rate_per_sec: float = Field(default=5.0, ge=0.0)  # tokens per second
    key_field: str | None = None  # event key used to partition buckets
    max_keys: int = Field(default=10000, ge=1)  # Max buckets to track
    overflow_action: str = Field(default="drop")  # "drop" or "mark"

    @field_validator("overflow_action")
    @classmethod
    def _normalize_action(cls, value: str) -> str:
        normalized = str(value).lower()
        if normalized not in {"drop", "mark"}:
            raise ValueError("overflow_action must be 'drop' or 'mark'")
        return normalized


class RateLimitFilter:
    """Token-bucket rate limiter."""

    name = "rate_limit"

    def __init__(
        self, *, config: RateLimitFilterConfig | dict | None = None, **kwargs: Any
    ) -> None:
        cfg = parse_plugin_config(RateLimitFilterConfig, config, **kwargs)
        self._capacity = cfg.capacity
        self._refill_rate = cfg.refill_rate_per_sec
        self._key_field = cfg.key_field
        self._max_keys = cfg.max_keys
        self._overflow_action = cfg.overflow_action
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
    "compatibility": {"min_fapilog_version": "0.3.0"},
    "api_version": "1.0",
}

# Mark Pydantic validators as used for vulture
_VULTURE_USED: tuple[object, ...] = (RateLimitFilterConfig._normalize_action,)
