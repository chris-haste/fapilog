"""
Fapilog Plugin System.

Provides base protocols for plugin authors.
"""

# Public protocols for plugin authors
from .enrichers import BaseEnricher
from .filters import BaseFilter
from .loader import (
    PluginLoadError,
    PluginNotFoundError,
    list_available_plugins,
    load_plugin,
    register_builtin,
)
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
from .utils import parse_plugin_config
from .versioning import PLUGIN_API_VERSION

__all__ = [
    # Authoring protocols
    "BaseEnricher",
    "BaseProcessor",
    "BaseSink",
    "BaseRedactor",
    "BaseFilter",
    # Loader helpers
    "load_plugin",
    "list_available_plugins",
    "register_builtin",
    "PluginLoadError",
    "PluginNotFoundError",
    # Metadata utilities
    "PluginCompatibility",
    "PluginInfo",
    "PluginMetadata",
    "create_plugin_metadata",
    "validate_fapilog_compatibility",
    "PLUGIN_API_VERSION",
    # Config parsing
    "parse_plugin_config",
]
