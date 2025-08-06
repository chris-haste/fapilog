"""
Async Component Registry for Fapilog v3.

This module provides the main plugin registry that manages plugin discovery,
loading, lifecycle, and integration with the async container.
"""

import asyncio
import uuid
import weakref
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from ..containers.container import AsyncLoggingContainer
from .discovery import AsyncPluginDiscovery
from .lifecycle import (
    AsyncComponentLifecycleManager,
    ComponentIsolationMixin,
)
from .metadata import PluginInfo, validate_fapilog_compatibility

T = TypeVar("T")


class PluginRegistryError(Exception):
    """Exception raised by the plugin registry."""

    pass


class PluginLoadError(Exception):
    """Exception raised when loading a plugin fails."""

    pass


class AsyncComponentRegistry(ComponentIsolationMixin):
    """
    Async component registry with plugin discovery and loading.

    This registry provides:
    - Async plugin discovery from multiple sources
    - Thread-safe component management with lifecycle isolation
    - Plugin versioning and compatibility validation
    - Component lifecycle management with async initialization and cleanup
    - Type-safe component creation with dependency injection
    - Component isolation between different container instances
    - Memory leak prevention with proper cleanup mechanisms
    """

    def __init__(
        self, container: AsyncLoggingContainer, container_id: Optional[str] = None
    ) -> None:
        """
        Initialize the component registry.

        Args:
            container: The async logging container to integrate with
            container_id: Unique container identifier (generated if not provided)
        """
        if container_id is None:
            container_id = str(uuid.uuid4())

        super().__init__(container_id)

        self._container = container
        self._discovery = AsyncPluginDiscovery()
        self._lifecycle_manager = AsyncComponentLifecycleManager(container_id)

        # Plugin instances and loaded state
        self._loaded_plugins: Dict[str, PluginInfo] = {}
        self._plugin_instances: Dict[str, Any] = {}

        # Thread safety
        self._lock = asyncio.Lock()
        self._initialized = False

        # Use weakref to avoid circular references
        self._weakref_self = weakref.ref(self)

    async def initialize(self) -> None:
        """Initialize the registry and discover plugins."""
        async with self._lock:
            if self._initialized:
                return

            try:
                # Discover all available plugins
                await self._discovery.discover_all_plugins()

                # Initialize lifecycle manager
                await self._lifecycle_manager.initialize_all()

                self._initialized = True

            except Exception as e:
                raise PluginRegistryError(f"Failed to initialize plugin registry: {e}") from e

    async def cleanup(self) -> None:
        """Clean up the registry and all loaded plugins."""
        async with self._lock:
            if not self._initialized:
                return

            try:
                # Cleanup lifecycle manager (cleans up all plugins)
                await self._lifecycle_manager.cleanup_all()

                # Clear plugin state
                self._loaded_plugins.clear()
                self._plugin_instances.clear()

                self._initialized = False

            except Exception:
                # Log error but continue
                pass

    async def discover_plugins(
        self, plugin_type: Optional[str] = None
    ) -> Dict[str, PluginInfo]:
        """
        Discover available plugins.

        Args:
            plugin_type: Optional plugin type filter

        Returns:
            Dictionary mapping plugin names to PluginInfo
        """
        if plugin_type:
            return await self._discovery.discover_plugins_by_type(plugin_type)
        else:
            return await self._discovery.discover_all_plugins()

    async def load_plugin(self, plugin_name: str) -> Any:
        """
        Load a plugin and return its instance.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Plugin instance

        Raises:
            PluginLoadError: If plugin loading fails
            PluginRegistryError: If plugin is not found or incompatible
        """
        async with self._lock:
            # Check if already loaded
            if plugin_name in self._loaded_plugins:
                return self._plugin_instances[plugin_name]

            # Get plugin info from discovery
            plugin_info = await self._discovery.get_plugin_info(plugin_name)
            if not plugin_info:
                raise PluginRegistryError(f"Plugin '{plugin_name}' not found")

            # Validate compatibility
            if not validate_fapilog_compatibility(plugin_info.metadata):
                raise PluginRegistryError(
                    f"Plugin '{plugin_name}' is incompatible with current Fapilog version"
                )

            try:
                # Load the plugin
                instance = await self._load_plugin_instance(plugin_info)

                # Register with lifecycle manager
                await self._lifecycle_manager.register_component(
                    plugin_name, plugin_info, instance
                )

                # Store loaded state
                plugin_info.loaded = True
                plugin_info.instance = instance
                self._loaded_plugins[plugin_name] = plugin_info
                self._plugin_instances[plugin_name] = instance

                # Register with container if appropriate
                await self._register_with_container(plugin_name, plugin_info, instance)

                return instance

            except Exception as e:
                plugin_info.load_error = str(e)
                raise PluginLoadError(f"Failed to load plugin '{plugin_name}': {e}") from e

    async def unload_plugin(self, plugin_name: str) -> None:
        """
        Unload a plugin and clean up its resources.

        Args:
            plugin_name: Name of the plugin to unload
        """
        async with self._lock:
            if plugin_name not in self._loaded_plugins:
                return

            try:
                # Unregister from lifecycle manager
                await self._lifecycle_manager.unregister_component(plugin_name)

                # Clean up state
                if plugin_name in self._loaded_plugins:
                    self._loaded_plugins[plugin_name].loaded = False
                    self._loaded_plugins[plugin_name].instance = None
                    del self._loaded_plugins[plugin_name]

                if plugin_name in self._plugin_instances:
                    del self._plugin_instances[plugin_name]

            except Exception:
                # Log error but continue
                pass

    async def get_plugin(self, plugin_name: str, plugin_type: Type[T]) -> Optional[T]:
        """
        Get a loaded plugin instance with type safety.

        Args:
            plugin_name: Name of the plugin
            plugin_type: Expected plugin type

        Returns:
            Plugin instance if loaded and type matches, None otherwise
        """
        instance = await self._lifecycle_manager.get_component(plugin_name)
        if instance and isinstance(instance, plugin_type):
            return instance
        return None

    async def load_plugins_by_type(self, plugin_type: str) -> Dict[str, Any]:
        """
        Load all available plugins of a specific type.

        Args:
            plugin_type: Type of plugins to load

        Returns:
            Dictionary mapping plugin names to instances
        """
        plugins = await self.discover_plugins(plugin_type)
        loaded_plugins = {}

        for plugin_name in plugins:
            try:
                instance = await self.load_plugin(plugin_name)
                loaded_plugins[plugin_name] = instance
            except Exception:
                # Log error but continue loading other plugins
                pass

        return loaded_plugins

    async def _load_plugin_instance(self, plugin_info: PluginInfo) -> Any:
        """
        Load a plugin instance from plugin info.

        Args:
            plugin_info: Plugin information

        Returns:
            Plugin instance
        """
        try:
            entry_point = plugin_info.metadata.entry_point

            if plugin_info.source == "entry_point":
                # Load via entry point
                import importlib.metadata

                entry_points = importlib.metadata.entry_points()

                # Find the entry point
                fapilog_entries = []
                if hasattr(entry_points, "select"):
                    fapilog_entries = entry_points.select(group="fapilog.plugins")
                else:
                    fapilog_entries = entry_points.get("fapilog.plugins", [])

                for ep in fapilog_entries:
                    if ep.name == plugin_info.metadata.name:
                        plugin_class = ep.load()
                        return plugin_class()

                raise PluginLoadError(f"Entry point not found: {entry_point}")

            elif plugin_info.source == "local":
                # Load from local file
                plugin_path = Path(entry_point)
                if not plugin_path.exists():
                    raise PluginLoadError(f"Plugin file not found: {entry_point}")

                # Import the module
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    plugin_info.metadata.name, plugin_path
                )
                if not spec or not spec.loader:
                    raise PluginLoadError(
                        f"Failed to create module spec for: {entry_point}"
                    )

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for plugin class
                if hasattr(module, "Plugin"):
                    return module.Plugin()
                elif hasattr(module, plugin_info.metadata.name):
                    plugin_class = getattr(module, plugin_info.metadata.name)
                    return plugin_class()
                else:
                    raise PluginLoadError(f"Plugin class not found in: {entry_point}")

            else:
                raise PluginLoadError(f"Unknown plugin source: {plugin_info.source}")

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin instance: {e}") from e

    async def _register_with_container(
        self, plugin_name: str, plugin_info: PluginInfo, instance: Any
    ) -> None:
        """
        Register plugin with the async container.

        Args:
            plugin_name: Plugin name
            plugin_info: Plugin information
            instance: Plugin instance
        """
        try:
            # Create an async factory for the plugin instance
            async def plugin_factory() -> Any:
                return instance

            # Get isolated component name
            isolated_name = self.get_isolated_name(plugin_name)

            # Register with container
            self._container.register_component(
                name=isolated_name,
                component_type=type(instance),
                factory=plugin_factory,
                is_singleton=True,
            )

        except Exception:
            # Log error but don't fail plugin loading
            pass

    def add_discovery_path(self, path: Union[str, Path]) -> None:
        """
        Add a path for local plugin discovery.

        Args:
            path: Directory path to add
        """
        self._discovery.add_discovery_path(path)

    def remove_discovery_path(self, path: Union[str, Path]) -> None:
        """
        Remove a path from local plugin discovery.

        Args:
            path: Directory path to remove
        """
        self._discovery.remove_discovery_path(path)

    @property
    def is_initialized(self) -> bool:
        """Check if registry is initialized."""
        return self._initialized

    @property
    def loaded_plugin_count(self) -> int:
        """Get the number of loaded plugins."""
        return len(self._loaded_plugins)

    def list_loaded_plugins(self) -> List[str]:
        """List all loaded plugin names."""
        return list(self._loaded_plugins.keys())

    def list_available_plugins(self) -> List[str]:
        """List all discovered plugin names."""
        return self._discovery.list_discovered_plugins()

    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """
        Get plugin information.

        Args:
            plugin_name: Plugin name

        Returns:
            PluginInfo if found, None otherwise
        """
        return self._lifecycle_manager.get_component_info(plugin_name)


async def create_component_registry(
    container: AsyncLoggingContainer, container_id: Optional[str] = None
) -> AsyncComponentRegistry:
    """
    Factory function to create a component registry.

    Args:
        container: Async logging container
        container_id: Optional container identifier

    Returns:
        AsyncComponentRegistry instance
    """
    registry = AsyncComponentRegistry(container, container_id)
    await registry.initialize()
    return registry
