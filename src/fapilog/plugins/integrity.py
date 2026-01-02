"""
Integrity plugin loader for tamper-evident add-ons.

Core remains dependency-light; this module only loads optional plugins
exposed via the ``fapilog.integrity`` entry point group.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any, Protocol, runtime_checkable


class IntegrityPluginLoadError(Exception):
    """Raised when an integrity plugin cannot be loaded."""


@runtime_checkable
class IntegrityPlugin(Protocol):
    """Optional plugin contract for tamper-evident add-ons."""

    def get_enricher(
        self, config: dict[str, Any] | None = None
    ) -> Any:  # pragma: no cover - structural  # noqa: V102
        ...

    def wrap_sink(
        self, sink: Any, config: dict[str, Any] | None = None
    ) -> Any:  # pragma: no cover - structural  # noqa: V102
        ...


def load_integrity_plugin(name: str) -> IntegrityPlugin:  # noqa: V102
    """
    Load an integrity plugin by entry point name.

    Plugins are expected to register under the ``fapilog.integrity`` group
    and return an object implementing some or all of the IntegrityPlugin
    protocol.
    """
    import warnings

    warnings.warn(
        "load_integrity_plugin is deprecated; use standard plugins instead "
        "(core.enrichers=['integrity'], core.sinks=['sealed']).",
        DeprecationWarning,
        stacklevel=2,
    )
    eps = importlib.metadata.entry_points()
    candidates = []
    try:
        if hasattr(eps, "select"):
            candidates = [
                ep for ep in eps.select(group="fapilog.integrity") if ep.name == name
            ]
        else:  # pragma: no cover - Py3.8 compat path
            group: list[Any] = eps.get("fapilog.integrity", [])
            candidates = [ep for ep in group if getattr(ep, "name", None) == name]
    except Exception as exc:
        raise IntegrityPluginLoadError(
            f"Failed to enumerate integrity plugins: {exc}"
        ) from exc

    if not candidates:
        raise IntegrityPluginLoadError(f"Integrity plugin '{name}' not found")

    ep = candidates[0]
    try:
        plugin = ep.load()
    except Exception as exc:  # pragma: no cover - defensive path
        raise IntegrityPluginLoadError(
            f"Failed to load integrity plugin '{name}': {exc}"
        ) from exc

    # Plugin may not fully implement the protocol, but we return it as-is
    return plugin  # type: ignore[no-any-return]
