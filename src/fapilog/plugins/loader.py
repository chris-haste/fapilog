"""
Simple plugin loader using built-in registries plus Python entry points.

Supports name normalization (hyphens/underscores) and alias mapping so plugin
authors can choose either style without breaking compatibility. Built-ins are
preferred over entry points when names collide.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from enum import Enum
from typing import Any, Callable, Iterable, TypeVar

from ..core import diagnostics

T = TypeVar("T")


def _normalize_plugin_name(name: str) -> str:
    """Normalize plugin names to a canonical underscore/lower format."""
    return name.replace("-", "_").lower()


def _warn_on_name_mismatch(cls: type | Callable[..., Any]) -> None:
    """Emit a diagnostic when class.name and PLUGIN_METADATA['name'] disagree."""

    try:
        class_name = getattr(cls, "name", None)
        module_name = getattr(cls, "__module__", None)
        if not class_name or not isinstance(class_name, str) or not module_name:
            return

        mod = importlib.import_module(module_name)
        metadata = getattr(mod, "PLUGIN_METADATA", None)
        if not metadata or not isinstance(metadata, dict):
            return
        meta_name = metadata.get("name")
        if not meta_name or not isinstance(meta_name, str):
            return

        if _normalize_plugin_name(class_name) == _normalize_plugin_name(meta_name):
            return

        try:
            diagnostics.warn(
                "plugins",
                "plugin name mismatch",
                class_name=class_name,
                metadata_name=meta_name,
                plugin=cls.__name__,
            )
        except Exception:
            # Contain diagnostics failures
            pass
    except Exception:
        # Best-effort only; never raise
        return


# Built-in plugin registry (group -> name -> class)
BUILTIN_SINKS: dict[str, type] = {}
BUILTIN_ENRICHERS: dict[str, type] = {}
BUILTIN_REDACTORS: dict[str, type] = {}
BUILTIN_PROCESSORS: dict[str, type] = {}
BUILTIN_FILTERS: dict[str, type] = {}

# Optional alias mapping per group (alias -> canonical name)
BUILTIN_ALIASES: dict[str, dict[str, str]] = {
    "fapilog.sinks": {},
    "fapilog.enrichers": {},
    "fapilog.redactors": {},
    "fapilog.processors": {},
    "fapilog.filters": {},
}


class PluginNotFoundError(Exception):
    """Plugin not found in built-ins or entry points."""


class PluginLoadError(Exception):
    """Plugin found but failed to load/instantiate."""


class ValidationMode(Enum):
    DISABLED = "disabled"
    WARN = "warn"
    STRICT = "strict"


# Module-level default validation mode
_validation_mode: ValidationMode = ValidationMode.DISABLED


def set_validation_mode(mode: ValidationMode) -> None:
    """Set the default plugin validation mode for subsequent loads."""
    global _validation_mode
    _validation_mode = mode


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


def _validate_plugin(instance: Any, group: str, mode: ValidationMode) -> bool:
    """Validate a plugin against its protocol."""
    from ..testing.validators import (
        validate_enricher,
        validate_filter,
        validate_processor,
        validate_redactor,
        validate_sink,
    )

    validator_map = {
        "fapilog.sinks": validate_sink,
        "fapilog.enrichers": validate_enricher,
        "fapilog.redactors": validate_redactor,
        "fapilog.processors": validate_processor,
        "fapilog.filters": validate_filter,
    }
    validator = validator_map.get(group)
    if validator is None:
        return True

    result = validator(instance)
    plugin_name = getattr(instance, "name", type(instance).__name__)

    if not result.valid:
        error_summary = "; ".join(result.errors)
        if mode == ValidationMode.STRICT:
            raise PluginLoadError(
                f"Plugin '{plugin_name}' failed validation: {error_summary}"
            )
        try:
            diagnostics.warn(
                "plugins",
                "plugin validation failed",
                plugin=plugin_name,
                group=group,
                errors=result.errors,
                warnings=result.warnings,
            )
        except Exception:
            pass
        return False

    if result.warnings and mode != ValidationMode.DISABLED:
        try:
            diagnostics.warn(
                "plugins",
                "plugin validation warnings",
                plugin=plugin_name,
                warnings=result.warnings,
            )
        except Exception:
            pass

    return True


def load_plugin(
    group: str,
    name: str,
    config: dict[str, Any] | None = None,
    *,
    validation_mode: ValidationMode | None = None,
) -> Any:
    """Load a plugin by group and name from built-ins or entry points."""

    config = config or {}
    canonical = _normalize_plugin_name(name)
    registry = _registry_for_group(group) or {}
    alias_map = BUILTIN_ALIASES.get(group, {})
    mode = validation_mode if validation_mode is not None else _validation_mode

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
        return _instantiate(cls, config, group=group, validation_mode=mode)

    # Entry point discovery
    try:
        eps = importlib.metadata.entry_points()
        candidates = _select_entry_points(eps, group)
        for ep in candidates:
            if _normalize_plugin_name(ep.name) == canonical:
                cls = ep.load()
                return _instantiate(cls, config, group=group, validation_mode=mode)
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
        "fapilog.filters": BUILTIN_FILTERS,
    }.get(group)


def _select_entry_points(eps: Any, group: str) -> list[Any]:
    """Support both modern and legacy entry_points APIs."""
    if hasattr(eps, "select"):
        return list(eps.select(group=group))
    # Py3.8 path: eps is Mapping[str, list[EntryPoint]]
    return list(eps.get(group, []))


def _instantiate(
    cls: Callable[..., T] | type,
    config: dict[str, Any],
    *,
    group: str,
    validation_mode: ValidationMode,
) -> T:
    try:
        instance = cls(**config) if config else cls()
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
    if validation_mode != ValidationMode.DISABLED:
        _validate_plugin(instance, group, validation_mode)
    _warn_on_name_mismatch(cls)
    return instance


__all__ = [
    "register_builtin",
    "load_plugin",
    "list_available_plugins",
    "PluginNotFoundError",
    "PluginLoadError",
    "ValidationMode",
    "set_validation_mode",
]
