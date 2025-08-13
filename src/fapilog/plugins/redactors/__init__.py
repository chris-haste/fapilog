"""
Redactors plugin protocol and helpers.

This module defines the `BaseRedactor` protocol and a sequential helper to
apply a list of redactors in deterministic order. All APIs are async-first and
non-blocking by design.
"""

from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ...metrics.metrics import MetricsCollector, plugin_timer


@runtime_checkable
class BaseRedactor(Protocol):
    """Redactor contract for transforming events before sink emission.

    Implementations MUST be async and non-blocking. Any I/O must be awaitable.
    """

    name: str

    async def start(self) -> None:  # pragma: no cover - optional lifecycle
        ...

    async def stop(self) -> None:  # pragma: no cover - optional lifecycle
        ...

    async def redact(self, event: dict) -> dict:  # noqa: D401
        """Return a redacted copy of the event mapping."""


async def redact_in_order(
    event: dict,
    redactors: Iterable[BaseRedactor],
    *,
    metrics: MetricsCollector | None = None,
) -> dict:
    """Apply redactors sequentially and deterministically.

    - Each redactor runs in the given order inside a plugin timing context
    - Exceptions are contained; the last good snapshot is preserved
    - Metrics are recorded via the shared metrics collector when enabled
    """

    current: dict = dict(event)
    for r in list(redactors):
        plugin_name = getattr(r, "__class__", type(r)).__name__
        try:
            async with plugin_timer(metrics, plugin_name):
                next_event = await r.redact(dict(current))
            # Shallow replacement to preserve mapping semantics
            if isinstance(next_event, dict):
                current = next_event
        except Exception:
            # Contain failure and continue with last good snapshot
            # Errors are recorded by plugin_timer when metrics is enabled
            continue
    return current
