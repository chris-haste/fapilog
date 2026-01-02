"""
Plugin utilities for name resolution and type detection.

Provides helpers for consistently identifying plugins by name and type.
"""

from __future__ import annotations

from typing import Any


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
    elif hasattr(plugin, "process"):
        return "processor"
    return "unknown"


# Mark functions as used for static analysis (vulture)
_VULTURE_USED: tuple[object, ...] = (
    get_plugin_name,
    normalize_plugin_name,
    get_plugin_type,
)
