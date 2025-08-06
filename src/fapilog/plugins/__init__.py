"""
Fapilog v3 Plugin System.

This package provides the async-first plugin system for Fapilog including:
- Plugin discovery and loading
- Component lifecycle management
- Plugin metadata validation
- Thread-safe component registry with isolation
"""

from .discovery import (
    AsyncPluginDiscovery,
    PluginDiscoveryError,
    discover_plugins,
    discover_plugins_by_type,
    get_discovery_instance,
)
from .lifecycle import (
    AsyncComponentLifecycleManager,
    ComponentIsolationMixin,
    ComponentLifecycleError,
    PluginLifecycleState,
    create_lifecycle_manager,
)
from .metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
    create_plugin_metadata,
    validate_fapilog_compatibility,
)
from .registry import (
    AsyncComponentRegistry,
    PluginLoadError,
    PluginRegistryError,
    create_component_registry,
)

__all__ = [
    # Discovery
    "AsyncPluginDiscovery",
    "PluginDiscoveryError",
    "discover_plugins",
    "discover_plugins_by_type",
    "get_discovery_instance",
    # Lifecycle
    "AsyncComponentLifecycleManager",
    "ComponentLifecycleError",
    "ComponentIsolationMixin",
    "PluginLifecycleState",
    "create_lifecycle_manager",
    # Metadata
    "PluginCompatibility",
    "PluginInfo",
    "PluginMetadata",
    "create_plugin_metadata",
    "validate_fapilog_compatibility",
    # Registry
    "AsyncComponentRegistry",
    "PluginLoadError",
    "PluginRegistryError",
    "create_component_registry",
]
