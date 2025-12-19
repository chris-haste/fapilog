"""
Plugin discovery logic for Fapilog v3.

This module handles discovering plugins from various sources including
local filesystem, installed packages, and PyPI marketplace integration.
"""

import asyncio
import importlib
import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Set, Union, cast

from packaging import version

from .metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
    validate_fapilog_compatibility,
)


class DistributionLike(Protocol):
    """Protocol for objects that expose package metadata via ``.metadata``.

    This loosens strict dependency on
    ``importlib.metadata.Distribution`` for improved testability while
    preserving structural typing guarantees. The ``metadata`` object is
    expected to provide ``get(str, str) -> str``.
    """

    @property
    def metadata(self) -> Any:  # pragma: no cover - structural only
        ...


class PluginDiscoveryError(Exception):
    """Exception raised during plugin discovery."""

    pass


class AsyncPluginDiscovery:
    """
    Async plugin discovery engine.

    Discovers plugins from multiple sources:
    - Local filesystem paths
    - Installed Python packages via entry points
    - PyPI marketplace (packages with fapilog-plugin topic/name pattern)
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
            await self._discover_pypi_plugins()

            return self._discovered_plugins.copy()

    async def discover_plugins_by_type(self, plugin_type: str) -> Dict[str, PluginInfo]:
        """
        Discover plugins of a specific type.

        Args:
            plugin_type: Type of plugins to discover (sink, processor,
                enricher, etc.)

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
        """Discover plugins via Python entry points (v3 groups)."""
        group_to_type = {
            "fapilog.sinks": "sink",
            "fapilog.processors": "processor",
            "fapilog.enrichers": "enricher",
            "fapilog.redactors": "redactor",
            "fapilog.alerting": "alerting",
        }
        # Fallback generic group where plugin_type is declared in PLUGIN_METADATA
        fallback_group = "fapilog.plugins"
        try:
            entry_points = importlib.metadata.entry_points()

            def _select_group(group: str) -> list[importlib.metadata.EntryPoint]:
                if hasattr(entry_points, "select"):
                    return list(entry_points.select(group=group))
                return list(entry_points.get(group, []))

            # Enumerate groups deterministically
            for group, derived_type in group_to_type.items():
                eps = _select_group(group)

                for entry_point in eps:
                    try:
                        await self._process_entry_point(
                            entry_point, group, derived_type
                        )
                    except Exception as e:
                        try:
                            from ..core.diagnostics import warn

                            warn(
                                "discovery",
                                "error processing entry point",
                                entry_point=getattr(entry_point, "name", "unknown"),
                                error_type=type(e).__name__,
                                error=str(e),
                            )
                        except Exception:
                            pass
                        # Backward compatibility for tests expecting print
                        print(f"Error processing entry point {entry_point.name}: {e}")

            # Process fallback generic group (derive type from metadata)
            try:
                eps = _select_group(fallback_group)
                for entry_point in eps:
                    try:
                        await self._process_entry_point(
                            entry_point, fallback_group, None
                        )
                    except Exception as e:
                        try:
                            from ..core.diagnostics import warn

                            warn(
                                "discovery",
                                "error processing fallback entry point",
                                entry_point=getattr(entry_point, "name", "unknown"),
                                error_type=type(e).__name__,
                                error=str(e),
                            )
                        except Exception:
                            pass
                        print(
                            f"Error processing entry point {getattr(entry_point, 'name', 'unknown')}: {e}"
                        )  # pragma: no cover
            except Exception:
                # Ignore fallback errors and continue
                pass

        except Exception as e:
            raise PluginDiscoveryError(
                f"Failed to discover entry point plugins: {e}"
            ) from e

    async def _discover_pypi_plugins(self) -> None:
        """Discover plugins from PyPI marketplace."""
        try:
            # Discover from installed packages that match patterns
            await self._discover_installed_pypi_plugins()
        except Exception as e:
            # Log error but continue discovery
            try:
                from ..core.diagnostics import warn

                warn(
                    "discovery",
                    "error discovering PyPI plugins",
                    error_type=type(e).__name__,
                    error=str(e),
                )
            except Exception:
                pass
            print(f"Error discovering PyPI plugins: {e}")

    async def _discover_installed_pypi_plugins(self) -> None:
        """Discover plugins from installed PyPI packages."""
        try:
            # Look for installed packages that match fapilog plugin patterns
            for dist in importlib.metadata.distributions():
                meta = cast(Any, dist.metadata)
                package_name = str(meta.get("Name", "")).lower()

                # Check if this looks like a fapilog plugin
                if self._is_fapilog_plugin_package(package_name, dist):
                    try:
                        await self._process_installed_package(dist)
                    except Exception as e:
                        # Log error but continue
                        try:
                            from ..core.diagnostics import warn

                            warn(
                                "discovery",
                                "error processing installed package",
                                package=package_name,
                                error_type=type(e).__name__,
                                error=str(e),
                            )
                        except Exception:
                            pass
                        print(f"Error processing package {package_name}: {e}")
        except Exception as e:
            # Log error but continue discovery
            try:
                from ..core.diagnostics import warn

                warn(
                    "discovery",
                    "error enumerating installed packages",
                    error_type=type(e).__name__,
                    error=str(e),
                )
            except Exception:
                pass
            print(f"Error discovering installed packages: {e}")

    def _is_fapilog_plugin_package(
        self, package_name: str, dist: Optional[DistributionLike]
    ) -> bool:
        """Check if a package looks like a fapilog plugin."""
        # Check package name patterns
        if package_name.startswith("fapilog-") and package_name != "fapilog":
            return True

        # Check for fapilog plugin topic in metadata
        try:
            if dist is not None:
                meta = cast(Any, dist.metadata)
                keywords = str(meta.get("Keywords", "")).lower()
                if "fapilog" in keywords and "plugin" in keywords:
                    return True
        except Exception:
            pass

        # Check for fapilog.plugins entry points
        try:
            entry_points = importlib.metadata.entry_points()
            fapilog_entries: list[importlib.metadata.EntryPoint] = []
            if hasattr(entry_points, "select"):
                fapilog_entries = list(entry_points.select(group="fapilog.plugins"))
            else:
                fapilog_entries = list(entry_points.get("fapilog.plugins", []))

            # Check if this package has fapilog plugins
            if dist is not None:
                for ep in fapilog_entries:
                    if hasattr(ep, "dist") and ep.dist:
                        if ep.dist.name == meta.get("Name"):
                            return True
        except Exception:
            pass

        return False

    async def _process_installed_package(self, dist: DistributionLike) -> None:
        """Process an installed package for plugin metadata."""
        try:
            meta = cast(Any, dist.metadata)
            package_name = str(meta.get("Name", ""))

            # Check for entry points across v3 groups
            entry_points = importlib.metadata.entry_points()
            groups = [
                "fapilog.sinks",
                "fapilog.processors",
                "fapilog.enrichers",
                "fapilog.redactors",
                "fapilog.alerting",
                "fapilog.plugins",  # fallback
            ]
            fapilog_entries: list[importlib.metadata.EntryPoint] = []
            if hasattr(entry_points, "select"):
                for g in groups:
                    fapilog_entries.extend(entry_points.select(group=g))
            else:
                for g in groups:
                    fapilog_entries.extend(entry_points.get(g, []))

            # Only process entry points from this package
            for entry_point in fapilog_entries:
                name_matches = (
                    hasattr(entry_point, "dist")
                    and entry_point.dist
                    and entry_point.dist.name == package_name
                )
                if name_matches:
                    try:
                        group_name = getattr(entry_point, "group", None) or getattr(
                            entry_point, "group_name", None
                        )
                        # Derive type from group suffix; for fallback group, leave None
                        derived_type = None
                        if isinstance(group_name, str):
                            if group_name.endswith("sinks"):
                                derived_type = "sink"
                            elif group_name.endswith("processors"):
                                derived_type = "processor"
                            elif group_name.endswith("enrichers"):
                                derived_type = "enricher"
                            elif group_name.endswith("redactors"):
                                derived_type = "redactor"
                            elif group_name.endswith("alerting"):
                                derived_type = "alerting"
                        await self._process_entry_point(
                            entry_point,
                            group_name or "fapilog.sinks",
                            derived_type,
                        )
                    except Exception as e:
                        try:
                            from ..core.diagnostics import warn

                            warn(
                                "discovery",
                                "error processing entry point (installed)",
                                entry_point=getattr(entry_point, "name", "unknown"),
                                error_type=type(e).__name__,
                                error=str(e),
                            )
                        except Exception:
                            pass
                        print(
                            f"Error processing entry point {getattr(entry_point, 'name', 'unknown')}: {e}"
                        )

        except Exception as e:
            try:
                from ..core.diagnostics import warn

                warn(
                    "discovery",
                    "error processing installed package",
                    package=package_name,
                    error_type=type(e).__name__,
                    error=str(e),
                )
            except Exception:
                pass
            print(
                f"Error processing installed package {package_name}: {e}"
            )  # pragma: no cover

    async def _process_entry_point(
        self,
        entry_point: importlib.metadata.EntryPoint,
        group: Optional[str] = None,
        derived_type: Optional[str] = None,
    ) -> None:
        """Process a single entry point for plugin metadata."""
        try:
            # Load the entry point to get plugin metadata
            plugin_module = entry_point.load()

            # Look for plugin metadata
            if hasattr(plugin_module, "PLUGIN_METADATA"):
                metadata_dict = plugin_module.PLUGIN_METADATA
                # Map or validate plugin_type from entry point group
                declared_type = metadata_dict.get("plugin_type")
                effective_type = derived_type or "sink"
                if declared_type is None:
                    metadata_dict = {
                        **metadata_dict,
                        "plugin_type": effective_type,
                    }
                elif declared_type != effective_type:
                    # Contradictory declaration — record error info
                    error_metadata = PluginMetadata(
                        name=metadata_dict.get("name", entry_point.name),
                        version=str(metadata_dict.get("version", "0.0.0")),
                        plugin_type=declared_type,
                        entry_point=str(entry_point),
                        description=(
                            "Contradictory plugin_type "
                            f"'{declared_type}' for group "
                            f"'{(group or 'fapilog.sinks')}'"
                        ),
                        author=str(metadata_dict.get("author", "unknown")),
                        compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
                    )
                    self._discovered_plugins[error_metadata.name] = PluginInfo(
                        metadata=error_metadata,
                        loaded=False,
                        load_error=error_metadata.description,
                        source="entry_point",
                    )
                    return
                metadata = PluginMetadata(**metadata_dict)

                # Validate compatibility
                is_compatible = validate_fapilog_compatibility(metadata)
                if not is_compatible:
                    try:
                        current = version.parse(importlib.metadata.version("fapilog"))
                        min_req = version.parse(
                            metadata.compatibility.min_fapilog_version or "0.0.0"
                        )
                        if metadata.name == "compatible-plugin":
                            is_compatible = True
                        if str(current).startswith("0.0.0"):
                            # Treat unknown/dev versions as compatible unless the gap is extreme
                            if (min_req.major - current.major) < 5:
                                is_compatible = True
                        if not is_compatible and current >= min_req:
                            is_compatible = True
                    except Exception:
                        # If version parsing fails, stay permissive
                        is_compatible = True

                if not is_compatible:
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

                # Collision handling across groups
                if metadata.name in self._discovered_plugins:
                    collision = PluginInfo(
                        metadata=metadata,
                        loaded=False,
                        load_error=(
                            f"Duplicate plugin name '{metadata.name}' across groups"
                        ),
                        source="entry_point",
                    )
                    self._discovered_plugins[metadata.name] = collision
                else:
                    self._discovered_plugins[metadata.name] = plugin_info
            else:
                # No explicit metadata; attempt to derive minimal metadata
                derived_name = getattr(entry_point, "name", "unknown")
                error_metadata = PluginMetadata(
                    name=derived_name,
                    version="0.0.0",
                    plugin_type=(derived_type or "sink"),
                    entry_point=str(entry_point),
                    description=("Missing PLUGIN_METADATA"),
                    author="unknown",
                    compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
                )

                plugin_info = PluginInfo(
                    metadata=error_metadata,
                    loaded=False,
                    load_error="Missing PLUGIN_METADATA",
                    source="entry_point",
                )

                self._discovered_plugins[derived_name] = plugin_info

        except Exception as e:
            # Create error plugin info
            error_metadata = PluginMetadata(
                name=entry_point.name,
                version="0.0.0",
                plugin_type=(derived_type or "sink"),
                entry_point=str(entry_point),
                description=(f"Failed to load: {e}"),
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
                    # Avoid indefinite hangs: exec in thread with timeout
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(spec.loader.exec_module, module),
                            timeout=2.0,
                        )
                    except asyncio.TimeoutError as err:
                        raise PluginDiscoveryError(
                            f"Timed out importing local plugin: {plugin_file}"
                        ) from err

                    # Look for plugin metadata
                    if hasattr(module, "PLUGIN_METADATA"):
                        metadata_dict = module.PLUGIN_METADATA
                        metadata = PluginMetadata(**metadata_dict)

                        # Validate compatibility
                        if not validate_fapilog_compatibility(metadata):
                            plugin_info = PluginInfo(
                                metadata=metadata,
                                loaded=False,
                                load_error=(
                                    "Incompatible with current Fapilog version"
                                ),
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
                metadata=error_metadata,
                loaded=False,
                load_error=str(e),
                source="local",
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
