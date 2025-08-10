"""
Component lifecycle management for Fapilog v3 plugins.

This module provides async lifecycle management for plugin components
with proper initialization, cleanup, and isolation.
"""

import asyncio
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

from ..core.resources import ResourceManager
from .metadata import PluginInfo

T = TypeVar("T")
LifecycleCallback = Callable[[], None]
AsyncLifecycleCallback = Callable[[], Awaitable[None]]


class ComponentLifecycleError(Exception):
    """Exception raised during component lifecycle operations."""

    pass


class PluginLifecycleState:
    """Manages the lifecycle state of a single plugin component."""

    def __init__(
        self, plugin_info: PluginInfo, instance: Any, container_id: str
    ) -> None:
        """
        Initialize plugin lifecycle state.

        Args:
            plugin_info: Plugin information
            instance: Plugin instance
            container_id: ID of the container managing this plugin
        """
        self.plugin_info = plugin_info
        self.instance = instance
        self.container_id = container_id
        self.initialized = False
        self.cleanup_callbacks: List[AsyncLifecycleCallback] = []
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the plugin component."""
        async with self._lock:
            if self.initialized:
                return

            try:
                # Call plugin's async initialization if available
                if hasattr(self.instance, "initialize") and callable(
                    self.instance.initialize
                ):
                    if asyncio.iscoroutinefunction(self.instance.initialize):
                        await self.instance.initialize()
                    else:
                        # Sync initialization
                        self.instance.initialize()

                self.initialized = True

            except Exception as e:
                msg = (
                    f"Failed to initialize plugin {self.plugin_info.metadata.name}: {e}"
                )
                raise ComponentLifecycleError(msg) from e

    async def cleanup(self) -> None:
        """Clean up the plugin component."""
        async with self._lock:
            if not self.initialized:
                return

            # Run cleanup callbacks in reverse order
            for callback in reversed(self.cleanup_callbacks):
                try:
                    await callback()
                except Exception:
                    # Log error but continue cleanup
                    pass

            # Call plugin's async cleanup if available
            try:
                if hasattr(self.instance, "cleanup") and callable(
                    self.instance.cleanup
                ):
                    if asyncio.iscoroutinefunction(self.instance.cleanup):
                        await self.instance.cleanup()
                    else:
                        # Sync cleanup
                        self.instance.cleanup()
            except Exception:
                # Log error but continue
                pass

            self.cleanup_callbacks.clear()
            self.initialized = False

    def add_cleanup_callback(self, callback: AsyncLifecycleCallback) -> None:
        """Add a cleanup callback for this plugin."""
        self.cleanup_callbacks.append(callback)


class AsyncComponentLifecycleManager:
    """
    Manages lifecycle of plugin components with isolation between containers.

    This manager ensures:
    - Proper async initialization and cleanup of plugin components
    - Component isolation between different container instances
    - Memory leak prevention through proper cleanup
    - Thread-safe lifecycle operations
    """

    def __init__(self, container_id: str) -> None:
        """
        Initialize lifecycle manager for a specific container.

        Args:
            container_id: Unique identifier for the container instance
        """
        self.container_id = container_id
        self._components: Dict[str, PluginLifecycleState] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

        # Use weakref to avoid circular references
        self._weakref_self = weakref.ref(self)

        # Resource manager dedicated to plugins under this lifecycle
        self._resources = ResourceManager()

    async def register_component(
        self, plugin_name: str, plugin_info: PluginInfo, instance: Any
    ) -> None:
        """
        Register a plugin component for lifecycle management.

        Args:
            plugin_name: Unique name for the plugin
            plugin_info: Plugin information
            instance: Plugin instance
        """
        async with self._lock:
            if plugin_name in self._components:
                raise ComponentLifecycleError(
                    f"Plugin {plugin_name} is already registered"
                )

            lifecycle_state = PluginLifecycleState(
                plugin_info=plugin_info,
                instance=instance,
                container_id=self.container_id,
            )

            self._components[plugin_name] = lifecycle_state

            # Initialize immediately if manager is already initialized
            if self._initialized:
                await lifecycle_state.initialize()

    async def unregister_component(self, plugin_name: str) -> None:
        """
        Unregister and cleanup a plugin component.

        Args:
            plugin_name: Name of the plugin to unregister
        """
        async with self._lock:
            if plugin_name not in self._components:
                return

            lifecycle_state = self._components[plugin_name]
            await lifecycle_state.cleanup()
            del self._components[plugin_name]

    async def initialize_all(self) -> None:
        """Initialize all registered components."""
        async with self._lock:
            if self._initialized:
                return

            initialization_errors: list[str] = []

            for plugin_name, lifecycle_state in self._components.items():
                try:
                    await lifecycle_state.initialize()
                except Exception as e:
                    initialization_errors.append(f"{plugin_name}: {e}")

            if initialization_errors:
                joined = "; ".join(initialization_errors)
                raise ComponentLifecycleError(f"Failed to initialize plugins: {joined}")

            self._initialized = True

    async def cleanup_all(self) -> None:
        """Clean up all registered components."""
        async with self._lock:
            if not self._initialized:
                return

            # Cleanup in reverse order of registration
            for lifecycle_state in reversed(list(self._components.values())):
                try:
                    await lifecycle_state.cleanup()
                except Exception:
                    # Log error but continue cleanup
                    pass

            self._components.clear()
            self._initialized = False

            # Cleanup pooled plugin resources after components are down
            try:
                await self._resources.cleanup_all()
            except Exception:
                pass

    async def get_component(self, plugin_name: str) -> Optional[Any]:
        """
        Get a plugin component instance.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance if found and initialized, None otherwise
        """
        async with self._lock:
            lifecycle_state = self._components.get(plugin_name)
            if lifecycle_state and lifecycle_state.initialized:
                return lifecycle_state.instance
            return None

    def add_cleanup_callback(
        self, plugin_name: str, callback: AsyncLifecycleCallback
    ) -> None:
        """
        Add a cleanup callback for a specific plugin.

        Args:
            plugin_name: Name of the plugin
            callback: Async cleanup callback
        """
        if plugin_name in self._components:
            self._components[plugin_name].add_cleanup_callback(callback)

    @property
    def is_initialized(self) -> bool:
        """Check if lifecycle manager is initialized."""
        return self._initialized

    @property
    def component_count(self) -> int:
        """Get the number of registered components."""
        return len(self._components)

    def list_components(self) -> List[str]:
        """List all registered component names."""
        return list(self._components.keys())

    def get_component_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """
        Get plugin information for a component.

        Args:
            plugin_name: Name of the plugin

        Returns:
            PluginInfo if found, None otherwise
        """
        lifecycle_state = self._components.get(plugin_name)
        if lifecycle_state:
            return lifecycle_state.plugin_info
        return None

    @property
    def resources(self) -> ResourceManager:
        """Access plugin-scoped resource manager."""
        return self._resources


@asynccontextmanager
async def create_lifecycle_manager(
    container_id: str,
) -> AsyncIterator[AsyncComponentLifecycleManager]:
    """
    Factory to create and manage a lifecycle manager with proper cleanup.

    Args:
        container_id: Unique identifier for the container instance

    Yields:
        AsyncComponentLifecycleManager instance
    """
    manager = AsyncComponentLifecycleManager(container_id)
    try:
        yield manager
    finally:
        await manager.cleanup_all()


class ComponentIsolationMixin:
    """
    Mixin to provide component isolation capabilities.

    This ensures that plugin components are properly isolated
    between different container instances.
    """

    def __init__(self, container_id: str) -> None:
        """Initialize with container isolation."""
        self._container_id = container_id
        self._isolation_boundary = f"container_{container_id}"

    def get_isolated_name(self, component_name: str) -> str:
        """
        Get an isolated name for a component within this container.

        Args:
            component_name: Original component name

        Returns:
            Isolated component name
        """
        return f"{self._isolation_boundary}_{component_name}"

    def is_same_container(self, other_container_id: str) -> bool:
        """
        Check if another container ID belongs to the same container.

        Args:
            other_container_id: Container ID to check

        Returns:
            True if same container, False otherwise
        """
        return self._container_id == other_container_id

    @property
    def container_id(self) -> str:
        """Get the container ID."""
        return self._container_id
