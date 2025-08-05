"""
Plugin registry for fapilog v3 universal plugin ecosystem.

This module provides the PluginRegistry class that manages the discovery,
loading, and lifecycle of plugins in the universal plugin ecosystem.
"""

import asyncio
from typing import Any, Dict, List, Optional, Protocol

from ..core.settings import UniversalSettings


class AsyncSinkPlugin(Protocol):
    """Async sink plugin interface."""

    async def write(self, events: List[Dict[str, Any]]) -> None:
        """Write events to sink."""
        ...

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize sink plugin."""
        ...

    async def cleanup(self) -> None:
        """Cleanup sink plugin resources."""
        ...


class AsyncProcessorPlugin(Protocol):
    """Async processor plugin interface."""

    async def process(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process events and return modified events."""
        ...

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize processor plugin."""
        ...

    async def cleanup(self) -> None:
        """Cleanup processor plugin resources."""
        ...


class AsyncEnricherPlugin(Protocol):
    """Async enricher plugin interface."""

    async def enrich(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich event with additional data."""
        ...

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize enricher plugin."""
        ...

    async def cleanup(self) -> None:
        """Cleanup enricher plugin resources."""
        ...


class PluginRegistry:
    """Universal plugin registry for fapilog v3."""

    def __init__(self, settings: UniversalSettings):
        """Initialize plugin registry."""
        self.settings = settings
        self._sink_plugins: Dict[str, AsyncSinkPlugin] = {}
        self._processor_plugins: Dict[str, AsyncProcessorPlugin] = {}
        self._enricher_plugins: Dict[str, AsyncEnricherPlugin] = {}
        self._lock = asyncio.Lock()

    async def register_sink_plugin(self, name: str, plugin: AsyncSinkPlugin) -> None:
        """Register a sink plugin."""
        async with self._lock:
            self._sink_plugins[name] = plugin

    async def register_processor_plugin(
        self, name: str, plugin: AsyncProcessorPlugin
    ) -> None:
        """Register a processor plugin."""
        async with self._lock:
            self._processor_plugins[name] = plugin

    async def register_enricher_plugin(
        self, name: str, plugin: AsyncEnricherPlugin
    ) -> None:
        """Register an enricher plugin."""
        async with self._lock:
            self._enricher_plugins[name] = plugin

    async def get_sink_plugin(self, name: str) -> Optional[AsyncSinkPlugin]:
        """Get sink plugin by name."""
        async with self._lock:
            return self._sink_plugins.get(name)

    async def get_processor_plugin(self, name: str) -> Optional[AsyncProcessorPlugin]:
        """Get processor plugin by name."""
        async with self._lock:
            return self._processor_plugins.get(name)

    async def get_enricher_plugin(self, name: str) -> Optional[AsyncEnricherPlugin]:
        """Get enricher plugin by name."""
        async with self._lock:
            return self._enricher_plugins.get(name)

    async def list_sink_plugins(self) -> List[str]:
        """List all registered sink plugins."""
        async with self._lock:
            return list(self._sink_plugins.keys())

    async def list_processor_plugins(self) -> List[str]:
        """List all registered processor plugins."""
        async with self._lock:
            return list(self._processor_plugins.keys())

    async def list_enricher_plugins(self) -> List[str]:
        """List all registered enricher plugins."""
        async with self._lock:
            return list(self._enricher_plugins.keys())

    async def cleanup(self) -> None:
        """Cleanup all plugins."""
        async with self._lock:
            # Cleanup sink plugins
            for sink_plugin in self._sink_plugins.values():
                await sink_plugin.cleanup()

            # Cleanup processor plugins
            for processor_plugin in self._processor_plugins.values():
                await processor_plugin.cleanup()

            # Cleanup enricher plugins
            for enricher_plugin in self._enricher_plugins.values():
                await enricher_plugin.cleanup()

            self._sink_plugins.clear()
            self._processor_plugins.clear()
            self._enricher_plugins.clear()
