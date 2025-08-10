"""
Async Container Architecture for Fapilog v3.

This module provides the core async-first container with perfect isolation
and zero global state for the Fapilog logging library.
"""

import asyncio
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Type,
    TypeVar,
    cast,
)

from pydantic import BaseModel

from ..core.resources import ResourceManager

T = TypeVar("T")
ComponentFactory = Callable[..., Awaitable[T]]


class ComponentInfo(BaseModel):
    """Information about a registered component."""

    component_type: Type[Any]
    factory: ComponentFactory[Any]
    is_singleton: bool = True
    dependencies: list[str] = []


class AsyncLoggingContainer:
    """
    Async-first container with perfect isolation and zero global state.

    This container provides:
    - Perfect isolation between instances with zero global variables
    - Async lifecycle management with proper initialization and cleanup
    - Component dependency injection through async factory methods
    - Thread-safe component management with async locks
    - Memory efficient without global registry or shared state
    - Context manager support for scoped access and automatic cleanup
    """

    def __init__(self) -> None:
        """Initialize container with instance-specific state only."""
        self._components: Dict[str, ComponentInfo] = {}
        self._instances: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._cleanup_callbacks: list[Callable[[], Awaitable[None]]] = []

        # Use weakref to avoid circular references and memory leaks
        self._weakref_self = weakref.ref(self)

        # Resource manager for pooled external resources within this container
        self._resources = ResourceManager()

    async def __aenter__(self) -> "AsyncLoggingContainer":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize the container and all registered components."""
        async with self._lock:
            if self._initialized:
                return

            # Initialize all singleton components
            for name, info in self._components.items():
                if info.is_singleton and name not in self._instances:
                    instance = await self._create_instance(name, info)
                    self._instances[name] = instance

            self._initialized = True

    async def cleanup(self) -> None:
        """Clean up all components and resources."""
        async with self._lock:
            if not self._initialized:
                return

            # Run cleanup callbacks in reverse order
            for cleanup_callback in reversed(self._cleanup_callbacks):
                try:
                    await cleanup_callback()
                except Exception:
                    # Log error but continue cleanup
                    pass

            # Cleanup pooled resources last to ensure components can release
            try:
                await self._resources.cleanup_all()
            except Exception:
                # Defensive: never fail cleanup
                pass

            # Clear all instances
            self._instances.clear()
            self._cleanup_callbacks.clear()
            self._initialized = False

    def register_component(
        self,
        name: str,
        component_type: Type[T],
        factory: ComponentFactory[T],
        is_singleton: bool = True,
        dependencies: Optional[list[str]] = None,
    ) -> None:
        """
        Register a component with the container.

        Args:
            name: Unique component name
            component_type: Type of the component
            factory: Async factory function to create the component
            is_singleton: Whether to create single instance (default: True)
            dependencies: List of dependency component names
        """
        if dependencies is None:
            dependencies = []

        self._components[name] = ComponentInfo(
            component_type=component_type,
            factory=factory,
            is_singleton=is_singleton,
            dependencies=dependencies,
        )

    async def get_component(self, name: str, component_type: Type[T]) -> T:
        """
        Get a component instance by name and type.

        Args:
            name: Component name
            component_type: Expected component type

        Returns:
            Component instance

        Raises:
            KeyError: If component is not registered
            TypeError: If component type doesn't match
        """
        async with self._lock:
            if name not in self._components:
                raise KeyError(f"Component '{name}' is not registered")

            info = self._components[name]

            # Type safety check
            if not issubclass(info.component_type, component_type):
                raise TypeError(
                    f"Component '{name}' is of type "
                    f"{info.component_type.__name__}, "
                    f"not {component_type.__name__}"
                )

            # Return existing singleton instance
            if info.is_singleton and name in self._instances:
                instance = self._instances[name]
                # Safe cast - we've already verified the type above
                return cast(T, instance)

            # Create new instance
            instance = await self._create_instance(name, info)

            # Store singleton instance
            if info.is_singleton:
                self._instances[name] = instance

            # Safe cast - we've already verified the type above
            return cast(T, instance)

    async def _create_instance(self, name: str, info: ComponentInfo) -> Any:
        """Create a component instance with dependency injection."""
        dependencies = {}

        # Resolve dependencies
        for dep_name in info.dependencies:
            if dep_name not in self._components:
                raise KeyError(
                    f"Dependency '{dep_name}' not found for component '{name}'"
                )

            dep_info = self._components[dep_name]

            # Check if dependency is already created
            if dep_info.is_singleton and dep_name in self._instances:
                dependency = self._instances[dep_name]
            else:
                # Create dependency instance
                dependency = await self._create_instance(dep_name, dep_info)
                # Store singleton dependency
                if dep_info.is_singleton:
                    self._instances[dep_name] = dependency

            dependencies[dep_name] = dependency

        # Create instance using factory with dependencies
        return await info.factory(**dependencies)

    def add_cleanup_callback(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Add a cleanup callback to be called during container cleanup."""
        self._cleanup_callbacks.append(callback)

    @property
    def is_initialized(self) -> bool:
        """Check if container is initialized."""
        return self._initialized

    @property
    def component_count(self) -> int:
        """Get the number of registered components."""
        return len(self._components)

    def list_components(self) -> list[str]:
        """List all registered component names."""
        return list(self._components.keys())

    @property
    def resources(self) -> ResourceManager:
        """Access the container-scoped resource manager."""
        return self._resources


@asynccontextmanager
async def create_container() -> AsyncIterator[AsyncLoggingContainer]:
    """
    Factory function to create and manage a container with proper cleanup.

    This is the recommended way to create containers as it ensures
    proper initialization and cleanup.

    Usage:
        async with create_container() as container:
            # Use container
            pass
    """
    container = AsyncLoggingContainer()
    try:
        await container.initialize()
        yield container
    finally:
        await container.cleanup()
