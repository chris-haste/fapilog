"""
Lightweight internal diagnostics for non-fatal events (worker/sink/etc.).

Design goals:
- Disabled by default; zero-crash, low-overhead guard path
- Structured JSON lines for machine-readability
- Minimal rate limiting to prevent log storms (token bucket per component)
- Test hook to override writer
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable


def _default_writer(
    payload: dict[str, Any],
) -> None:  # pragma: no cover - used via emit
    print(json.dumps(payload, separators=(",", ":")), flush=True)


_writer: Callable[[dict[str, Any]], None] = _default_writer


def set_writer_for_tests(
    writer: Callable[[dict[str, Any]], None],
) -> None:  # pragma: no cover - used by tests only
    global _writer
    _writer = writer


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class _RateLimiter:
    def __init__(self, *, capacity: int = 5, refill_per_sec: float = 5.0) -> None:
        self._capacity = float(capacity)
        self._refill_per_sec = float(refill_per_sec)
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=self._capacity, last_refill=now)
            self._buckets[key] = bucket
        # Refill
        elapsed = max(0.0, now - bucket.last_refill)
        bucket.tokens = min(
            self._capacity, bucket.tokens + elapsed * self._refill_per_sec
        )
        bucket.last_refill = now
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True
        return False


_limiter = _RateLimiter()


def _is_enabled() -> bool:
    try:
        from .settings import Settings

        return bool(Settings().core.internal_logging_enabled)
    except Exception:
        return False


def emit(
    *,
    component: str,
    level: str,
    message: str,
    **fields: Any,
) -> None:
    if not _is_enabled():
        return
    # Rate-limit per component
    # Allow callers to provide a distinct limiter key without affecting the
    # emitted component value. Special key is removed before payload emission.
    limiter_key_extra = fields.pop("_rate_limit_key", None)
    limiter_key = f"{component}:{limiter_key_extra}" if limiter_key_extra else component
    if not _limiter.allow(limiter_key):
        return
    # Correlation (best-effort)
    corr: str | None = None
    try:
        from .context import request_id_var

        corr = request_id_var.get(None)
    except Exception:
        corr = None

    payload: dict[str, Any] = {
        "ts": time.time(),
        "level": level,
        "component": component,
        "message": message,
    }
    if corr:
        payload["correlation_id"] = corr
    if fields:
        payload.update(fields)
    try:
        _writer(payload)
    except Exception:
        # Never raise
        return


def debug(
    component: str, message: str, **fields: Any
) -> None:  # pragma: no cover - convenience wrapper
    emit(component=component, level="DEBUG", message=message, **fields)


def warn(
    component: str, message: str, **fields: Any
) -> None:  # pragma: no cover - convenience wrapper
    emit(component=component, level="WARN", message=message, **fields)


# Tests-only hook: reset internal rate limiter to avoid cross-test suppression
def _reset_for_tests() -> None:  # pragma: no cover - used by tests only
    global _limiter
    _limiter = _RateLimiter()


# Mark as referenced for static analyzers (vulture)
_VULTURE_USED: tuple[object, ...] = (
    set_writer_for_tests,
    debug,
    warn,
    _reset_for_tests,
)
