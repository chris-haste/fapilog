"""
Async Lifecycle Management for Fapilog v3 Container Architecture.

This module provides lifecycle management utilities for async components
within the container system.
"""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Protocol, Union, runtime_checkable


@runtime_checkable
class AsyncInitializable(Protocol):
    """Protocol for components that support async initialization."""

    async def initialize(self) -> None:
        """Initialize the component asynchronously."""
        ...


@runtime_checkable
class AsyncCleanable(Protocol):
    """Protocol for components that support async cleanup."""

    async def cleanup(self) -> None:
        """Clean up the component asynchronously."""
        ...


class LifecycleManager:
    """
    Manages the lifecycle of async components.

    This class handles initialization and cleanup of components
    that implement the AsyncInitializable and/or AsyncCleanable protocols.
    """

    def __init__(self) -> None:
        """Initialize the lifecycle manager."""
        self._initialized_components: list[AsyncCleanable] = []
        self._lock = asyncio.Lock()

    async def initialize_component(self, component: Any) -> None:
        """
        Initialize a component if it supports async initialization.

        Args:
            component: Component to initialize
        """
        async with self._lock:
            if isinstance(component, AsyncInitializable):
                await component.initialize()

            # Track for cleanup if cleanable
            if isinstance(component, AsyncCleanable):
                self._initialized_components.append(component)

    async def cleanup_all(self) -> None:
        """Clean up all initialized components in reverse order."""
        async with self._lock:
            # Clean up in reverse order (LIFO)
            for component in reversed(self._initialized_components):
                try:
                    await component.cleanup()
                except Exception:
                    # Continue cleanup even if one component fails
                    pass

            self._initialized_components.clear()


class AsyncComponentBase(ABC):
    """
    Base class for async components with lifecycle management.

    This provides a standard foundation for components that need
    async initialization and cleanup.
    """

    def __init__(self) -> None:
        """Initialize the component base."""
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the component."""
        async with self._lock:
            if self._initialized:
                return

            await self._initialize_impl()
            self._initialized = True

    async def cleanup(self) -> None:
        """Clean up the component."""
        async with self._lock:
            if not self._initialized:
                return

            await self._cleanup_impl()
            self._initialized = False

    @abstractmethod
    async def _initialize_impl(self) -> None:
        """Implement component-specific initialization."""
        ...

    @abstractmethod
    async def _cleanup_impl(self) -> None:
        """Implement component-specific cleanup."""
        ...

    @property
    def is_initialized(self) -> bool:
        """Check if component is initialized."""
        return self._initialized


@asynccontextmanager
async def managed_component(
    component: Union[AsyncInitializable, AsyncCleanable],
) -> AsyncIterator[Any]:
    """
    Context manager for components with lifecycle management.

    Args:
        component: Component to manage

    Yields:
        The managed component
    """
    if isinstance(component, AsyncInitializable):
        await component.initialize()

    try:
        yield component
    finally:
        if isinstance(component, AsyncCleanable):
            await component.cleanup()
