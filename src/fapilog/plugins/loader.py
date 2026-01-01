"""
Simple plugin loader using built-in registries plus Python entry points.

Supports name normalization (hyphens/underscores) and alias mapping so plugin
authors can choose either style without breaking compatibility. Built-ins are
preferred over entry points when names collide.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from typing import Any, Callable, Iterable, TypeVar

from ..core import diagnostics

T = TypeVar("T")


def _normalize_plugin_name(name: str) -> str:
    """Normalize plugin names to a canonical underscore/lower format."""
    return name.replace("-", "_").lower()


# Built-in plugin registry (group -> name -> class)
BUILTIN_SINKS: dict[str, type] = {}
BUILTIN_ENRICHERS: dict[str, type] = {}
BUILTIN_REDACTORS: dict[str, type] = {}
BUILTIN_PROCESSORS: dict[str, type] = {}

# Optional alias mapping per group (alias -> canonical name)
BUILTIN_ALIASES: dict[str, dict[str, str]] = {
    "fapilog.sinks": {},
    "fapilog.enrichers": {},
    "fapilog.redactors": {},
    "fapilog.processors": {},
}


class PluginNotFoundError(Exception):
    """Plugin not found in built-ins or entry points."""


class PluginLoadError(Exception):
    """Plugin found but failed to load/instantiate."""


def register_builtin(
    group: str, name: str, cls: type, *, aliases: Iterable[str] | None = None
) -> None:
    """Register a built-in plugin class and optional aliases."""

    registry = _registry_for_group(group)
    if registry is None:
        return
    canonical = _normalize_plugin_name(name)
    registry[canonical] = cls

    if aliases:
        alias_map = BUILTIN_ALIASES.setdefault(group, {})
        for alias in aliases:
            alias_map[_normalize_plugin_name(alias)] = canonical


def load_plugin(group: str, name: str, config: dict[str, Any] | None = None) -> Any:
    """Load a plugin by group and name from built-ins or entry points."""

    config = config or {}
    canonical = _normalize_plugin_name(name)
    registry = _registry_for_group(group) or {}
    alias_map = BUILTIN_ALIASES.get(group, {})

    # Alias lookup for built-ins
    target_name = alias_map.get(canonical, canonical)
    if target_name in registry:
        cls = registry[target_name]
        # Allow monkeypatching by resolving current attribute from module
        try:
            mod = getattr(cls, "__module__", None)
            qual = getattr(cls, "__name__", None)
            if mod and qual:
                mod_obj = importlib.import_module(mod)
                patched = getattr(mod_obj, qual, cls)
                cls = patched
        except Exception:
            pass
        return _instantiate(cls, config)

    # Entry point discovery
    try:
        eps = importlib.metadata.entry_points()
        candidates = _select_entry_points(eps, group)
        for ep in candidates:
            if _normalize_plugin_name(ep.name) == canonical:
                cls = ep.load()
                return _instantiate(cls, config)
    except Exception as exc:  # pragma: no cover - defensive
        raise PluginLoadError(
            f"Failed to load plugin '{name}' from {group}: {exc}"
        ) from exc

    raise PluginNotFoundError(f"Plugin '{name}' not found in group '{group}'")


def list_available_plugins(group: str) -> list[str]:
    """List available plugin names (built-in + entry points + aliases)."""

    names: set[str] = set()
    registry = _registry_for_group(group) or {}
    alias_map = BUILTIN_ALIASES.get(group, {})

    names.update(registry.keys())
    names.update(alias_map.keys())

    try:
        eps = importlib.metadata.entry_points()
        candidates = _select_entry_points(eps, group)
        for ep in candidates:
            names.add(_normalize_plugin_name(ep.name))
    except Exception:
        # Best-effort; ignore discovery errors
        pass

    return sorted(names)


def _registry_for_group(group: str) -> dict[str, type] | None:
    return {
        "fapilog.sinks": BUILTIN_SINKS,
        "fapilog.enrichers": BUILTIN_ENRICHERS,
        "fapilog.redactors": BUILTIN_REDACTORS,
        "fapilog.processors": BUILTIN_PROCESSORS,
    }.get(group)


def _select_entry_points(eps: Any, group: str) -> list[Any]:
    """Support both modern and legacy entry_points APIs."""
    if hasattr(eps, "select"):
        return list(eps.select(group=group))
    # Py3.8 path: eps is Mapping[str, list[EntryPoint]]
    return list(eps.get(group, []))


def _instantiate(cls: Callable[..., T] | type, config: dict[str, Any]) -> T:
    try:
        return cls(**config) if config else cls()
    except Exception as exc:  # pragma: no cover - defensive
        try:
            diagnostics.warn(
                "plugins",
                "plugin instantiation failed",
                plugin=str(cls),
                error=str(exc),
            )
        except Exception:
            pass
        raise PluginLoadError(str(exc)) from exc


__all__ = [
    "register_builtin",
    "load_plugin",
    "list_available_plugins",
    "PluginNotFoundError",
    "PluginLoadError",
]
