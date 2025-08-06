"""
Plugin discovery logic for Fapilog v3.

This module handles discovering plugins from various sources including
local filesystem, installed packages, and future marketplace integration.
"""

import asyncio
import importlib
import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from .metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
    validate_fapilog_compatibility,
)


class PluginDiscoveryError(Exception):
    """Exception raised during plugin discovery."""

    pass


class AsyncPluginDiscovery:
    """
    Async plugin discovery engine.

    Discovers plugins from multiple sources:
    - Local filesystem paths
    - Installed Python packages via entry points
    - Future: Plugin marketplace
    """

    def __init__(self) -> None:
        """Initialize plugin discovery."""
        self._discovered_plugins: Dict[str, PluginInfo] = {}
        self._discovery_paths: Set[Path] = set()
        self._lock = asyncio.Lock()

    async def discover_all_plugins(self) -> Dict[str, PluginInfo]:
        """
        Discover all available plugins from all sources.

        Returns:
            Dictionary mapping plugin names to PluginInfo
        """
        async with self._lock:
            # Clear previous discoveries
            self._discovered_plugins.clear()

            # Discover from different sources
            await self._discover_entry_point_plugins()
            await self._discover_local_plugins()

            return self._discovered_plugins.copy()

    async def discover_plugins_by_type(self, plugin_type: str) -> Dict[str, PluginInfo]:
        """
        Discover plugins of a specific type.

        Args:
            plugin_type: Type of plugins to discover (sink, processor, enricher, etc.)

        Returns:
            Dictionary mapping plugin names to PluginInfo
        """
        all_plugins = await self.discover_all_plugins()
        return {
            name: info
            for name, info in all_plugins.items()
            if info.metadata.plugin_type == plugin_type
        }

    async def _discover_entry_point_plugins(self) -> None:
        """Discover plugins via Python entry points."""
        try:
            # Discover Fapilog plugins via entry points
            entry_points = importlib.metadata.entry_points()

            # Look for fapilog plugins
            fapilog_entries = []
            if hasattr(entry_points, "select"):
                # Python 3.10+
                fapilog_entries = entry_points.select(group="fapilog.plugins")
            else:
                # Python 3.8-3.9
                fapilog_entries = entry_points.get("fapilog.plugins", [])

            for entry_point in fapilog_entries:
                try:
                    await self._process_entry_point(entry_point)
                except Exception as e:
                    # Log error but continue discovery
                    print(f"Error processing entry point {entry_point.name}: {e}")

        except Exception as e:
            raise PluginDiscoveryError(
                f"Failed to discover entry point plugins: {e}"
            ) from e

    async def _process_entry_point(
        self, entry_point: importlib.metadata.EntryPoint
    ) -> None:
        """Process a single entry point for plugin metadata."""
        try:
            # Load the entry point to get plugin metadata
            plugin_module = entry_point.load()

            # Look for plugin metadata
            if hasattr(plugin_module, "PLUGIN_METADATA"):
                metadata_dict = plugin_module.PLUGIN_METADATA
                metadata = PluginMetadata(**metadata_dict)

                # Validate compatibility
                if not validate_fapilog_compatibility(metadata):
                    plugin_info = PluginInfo(
                        metadata=metadata,
                        loaded=False,
                        load_error="Incompatible with current Fapilog version",
                        source="entry_point",
                    )
                else:
                    plugin_info = PluginInfo(
                        metadata=metadata, loaded=False, source="entry_point"
                    )

                self._discovered_plugins[metadata.name] = plugin_info

        except Exception as e:
            # Create error plugin info
            error_metadata = PluginMetadata(
                name=entry_point.name,
                version="0.0.0",
                plugin_type="sink",
                entry_point=str(entry_point),
                description=f"Failed to load: {e}",
                author="unknown",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )

            plugin_info = PluginInfo(
                metadata=error_metadata,
                loaded=False,
                load_error=str(e),
                source="entry_point",
            )

            self._discovered_plugins[entry_point.name] = plugin_info

    async def _discover_local_plugins(self) -> None:
        """Discover plugins from local filesystem paths."""
        for path in self._discovery_paths:
            if path.exists() and path.is_dir():
                await self._scan_directory_for_plugins(path)

    async def _scan_directory_for_plugins(self, directory: Path) -> None:
        """
        Scan a directory for plugin files.

        Args:
            directory: Directory to scan for plugins
        """
        try:
            # Look for Python files that might be plugins
            for plugin_file in directory.glob("*.py"):
                if plugin_file.name.startswith("_"):
                    continue  # Skip private files

                await self._process_local_plugin_file(plugin_file)

        except Exception as e:
            raise PluginDiscoveryError(
                f"Failed to scan directory {directory}: {e}"
            ) from e

    async def _process_local_plugin_file(self, plugin_file: Path) -> None:
        """
        Process a local plugin file for metadata.

        Args:
            plugin_file: Path to plugin file
        """
        try:
            # Add directory to Python path temporarily
            parent_dir = str(plugin_file.parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
                path_added = True
            else:
                path_added = False

            try:
                # Import the module
                module_name = plugin_file.stem
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Look for plugin metadata
                    if hasattr(module, "PLUGIN_METADATA"):
                        metadata_dict = module.PLUGIN_METADATA
                        metadata = PluginMetadata(**metadata_dict)

                        # Validate compatibility
                        if not validate_fapilog_compatibility(metadata):
                            plugin_info = PluginInfo(
                                metadata=metadata,
                                loaded=False,
                                load_error="Incompatible with current Fapilog version",
                                source="local",
                            )
                        else:
                            plugin_info = PluginInfo(
                                metadata=metadata, loaded=False, source="local"
                            )

                        self._discovered_plugins[metadata.name] = plugin_info

            finally:
                # Remove from path if we added it
                if path_added and parent_dir in sys.path:
                    sys.path.remove(parent_dir)

        except Exception as e:
            # Create error plugin info for local plugins
            error_metadata = PluginMetadata(
                name=plugin_file.stem,
                version="0.0.0",
                plugin_type="sink",
                entry_point=str(plugin_file),
                description=f"Failed to load local plugin: {e}",
                author="unknown",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )

            plugin_info = PluginInfo(
                metadata=error_metadata, loaded=False, load_error=str(e), source="local"
            )

            self._discovered_plugins[plugin_file.stem] = plugin_info

    def add_discovery_path(self, path: Union[str, Path]) -> None:
        """
        Add a path to search for local plugins.

        Args:
            path: Directory path to add for plugin discovery
        """
        self._discovery_paths.add(Path(path))

    def remove_discovery_path(self, path: Union[str, Path]) -> None:
        """
        Remove a path from plugin discovery.

        Args:
            path: Directory path to remove from plugin discovery
        """
        self._discovery_paths.discard(Path(path))

    def get_discovery_paths(self) -> Set[Path]:
        """Get all configured discovery paths."""
        return self._discovery_paths.copy()

    async def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """
        Get information about a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            PluginInfo if found, None otherwise
        """
        if plugin_name not in self._discovered_plugins:
            # Try to rediscover plugins
            await self.discover_all_plugins()

        return self._discovered_plugins.get(plugin_name)

    def list_discovered_plugins(self) -> List[str]:
        """List all discovered plugin names."""
        return list(self._discovered_plugins.keys())

    def get_plugins_by_type(self, plugin_type: str) -> Dict[str, PluginInfo]:
        """
        Get all discovered plugins of a specific type.

        Args:
            plugin_type: Type of plugins to retrieve

        Returns:
            Dictionary mapping plugin names to PluginInfo
        """
        return {
            name: info
            for name, info in self._discovered_plugins.items()
            if info.metadata.plugin_type == plugin_type
        }


# Global discovery instance
_discovery_instance: Optional[AsyncPluginDiscovery] = None


async def get_discovery_instance() -> AsyncPluginDiscovery:
    """Get the global plugin discovery instance."""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = AsyncPluginDiscovery()
    return _discovery_instance


async def discover_plugins() -> Dict[str, PluginInfo]:
    """Convenience function to discover all plugins."""
    discovery = await get_discovery_instance()
    return await discovery.discover_all_plugins()


async def discover_plugins_by_type(plugin_type: str) -> Dict[str, PluginInfo]:
    """Convenience function to discover plugins by type."""
    discovery = await get_discovery_instance()
    return await discovery.discover_plugins_by_type(plugin_type)
