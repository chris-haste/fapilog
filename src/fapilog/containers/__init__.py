"""
Async Container Architecture for Fapilog v3.

This module provides the core async-first container system with perfect
isolation and zero global state.
"""

from .container import (
    AsyncLoggingContainer,
    ComponentInfo,
    create_container,
)
from .lifecycle import (
    AsyncCleanable,
    AsyncComponentBase,
    AsyncInitializable,
    LifecycleManager,
    managed_component,
)

__all__ = [
    # Core container
    "AsyncLoggingContainer",
    "ComponentInfo",
    "create_container",
    # Lifecycle management
    "AsyncInitializable",
    "AsyncCleanable",
    "LifecycleManager",
    "AsyncComponentBase",
    "managed_component",
]
