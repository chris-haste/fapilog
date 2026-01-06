"""
Plugin utilities for name resolution and type detection.

Provides helpers for consistently identifying plugins by name and type.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel


def get_plugin_name(plugin: Any) -> str:
    """Get the canonical name of a plugin.

    Resolution order:
    1. plugin.name attribute (if non-empty string)
    2. PLUGIN_METADATA["name"] (if module has metadata)
    3. Class name (fallback)

    Args:
        plugin: Plugin instance or class

    Returns:
        Canonical plugin name
    """
    # Try name attribute
    name = getattr(plugin, "name", None)
    if name and isinstance(name, str) and name.strip():
        result: str = name.strip()
        return result

    # Try PLUGIN_METADATA from module
    try:
        import importlib

        cls = plugin if isinstance(plugin, type) else plugin.__class__
        module_name = getattr(cls, "__module__", None)
        if module_name:
            module = importlib.import_module(module_name)
            metadata = getattr(module, "PLUGIN_METADATA", None)
            if metadata and isinstance(metadata, dict):
                meta_name = metadata.get("name")
                if meta_name and isinstance(meta_name, str):
                    meta_result: str = meta_name
                    return meta_result
    except Exception:
        pass

    # Fallback to class name
    cls = plugin if isinstance(plugin, type) else plugin.__class__
    class_name: str = cls.__name__
    return class_name


def normalize_plugin_name(name: str) -> str:
    """Normalize a plugin name to canonical form.

    Converts hyphens to underscores and lowercases.

    Args:
        name: Raw plugin name

    Returns:
        Normalized plugin name
    """
    return name.replace("-", "_").lower()


def get_plugin_type(plugin: Any) -> str:
    """Determine the type of a plugin.

    Args:
        plugin: Plugin instance or class

    Returns:
        Plugin type: sink, enricher, redactor, processor, or unknown
    """
    if hasattr(plugin, "write"):
        return "sink"
    elif hasattr(plugin, "enrich"):
        return "enricher"
    elif hasattr(plugin, "redact"):
        return "redactor"
    elif hasattr(plugin, "filter"):
        return "filter"
    elif hasattr(plugin, "process"):
        return "processor"
    return "unknown"


TConfig = TypeVar("TConfig", bound=BaseModel)


def parse_plugin_config(
    config_cls: type[TConfig],
    raw_config: TConfig | dict[str, Any] | None = None,
    **kwargs: Any,
) -> TConfig:
    """Parse plugin configuration using a shared Pydantic helper.

    Supports config objects, plain dicts, nested {"config": {...}} wrappers,
    and keyword arguments. Falls back to config_cls() when nothing provided.
    """
    if isinstance(raw_config, config_cls):
        return raw_config

    if isinstance(raw_config, dict):
        nested = raw_config.get("config") if "config" in raw_config else raw_config
        if isinstance(nested, config_cls):
            return nested
        return config_cls.model_validate(nested)

    if raw_config is None:
        config_kwargs = dict(kwargs)
        if "config" in config_kwargs:
            nested = config_kwargs.pop("config")
            if isinstance(nested, config_cls):
                return nested
            if isinstance(nested, dict):
                return config_cls.model_validate(nested)
        if config_kwargs:
            return config_cls.model_validate(config_kwargs)
        return config_cls()

    raise TypeError(
        f"Cannot parse config: expected {config_cls.__name__}, dict, or None; "
        f"got {type(raw_config).__name__}"
    )


# Mark functions as used for static analysis (vulture)
_VULTURE_USED: tuple[object, ...] = (
    get_plugin_name,
    normalize_plugin_name,
    get_plugin_type,
    parse_plugin_config,
)
