"""
Fapilog Plugin System.

Provides base protocols for plugin authors and the integrity hook.
"""

# Public protocols for plugin authors
from .enrichers import BaseEnricher
from .integrity import IntegrityPlugin, IntegrityPluginLoadError, load_integrity_plugin
from .metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
    create_plugin_metadata,
    validate_fapilog_compatibility,
)
from .processors import BaseProcessor
from .redactors import BaseRedactor
from .sinks import BaseSink
from .versioning import PLUGIN_API_VERSION

__all__ = [
    # Authoring protocols
    "BaseEnricher",
    "BaseProcessor",
    "BaseSink",
    "BaseRedactor",
    # Integrity hook
    "IntegrityPlugin",
    "IntegrityPluginLoadError",
    "load_integrity_plugin",
    # Metadata utilities
    "PluginCompatibility",
    "PluginInfo",
    "PluginMetadata",
    "create_plugin_metadata",
    "validate_fapilog_compatibility",
    "PLUGIN_API_VERSION",
]
