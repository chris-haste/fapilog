"""
Comprehensive async tests for the plugin system.

Tests cover:
- Plugin metadata validation
- Plugin discovery from multiple sources
- Component lifecycle management
- Thread-safe component management
- Plugin loading and isolation
- Memory leak prevention
- Type safety validation
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fapilog.containers.container import create_container
from fapilog.plugins.discovery import (
    AsyncPluginDiscovery,
    PluginDiscoveryError,
    discover_plugins,
    discover_plugins_by_type,
    get_discovery_instance,
)
from fapilog.plugins.lifecycle import (
    AsyncComponentLifecycleManager,
    ComponentIsolationMixin,
    ComponentLifecycleError,
    PluginLifecycleState,
    ResourceManager,
    create_lifecycle_manager,
)
from fapilog.plugins.metadata import (
    PluginCompatibility,
    PluginInfo,
    PluginMetadata,
    create_plugin_metadata,
    validate_fapilog_compatibility,
)
from fapilog.plugins.registry import (
    AsyncComponentRegistry,
    PluginLoadError,
    PluginRegistryError,
    create_component_registry,
)


class MockPlugin:
    """Mock plugin for testing."""

    def __init__(self, name: str = "test_plugin"):
        self.name = name
        self.initialized = False
        self.cleaned_up = False
        self.initialization_count = 0
        self.initialize_should_fail = False
        self.cleanup_should_fail = False

    async def initialize(self) -> None:
        """Async initialization."""
        self.initialized = True
        self.initialization_count += 1
        if self.initialize_should_fail:
            raise ComponentLifecycleError(
                f"Failed to initialize plugin {self.name}: Mock error"
            )

    async def cleanup(self) -> None:
        """Async cleanup."""
        self.cleaned_up = True
        if self.cleanup_should_fail:
            raise ComponentLifecycleError(
                f"Failed to cleanup plugin {self.name}: Mock error"
            )

    def get_status(self) -> dict[str, Any]:
        """Get plugin status."""
        return {
            "name": self.name,
            "initialized": self.initialized,
            "cleaned_up": self.cleaned_up,
        }


class SyncMockPlugin:
    """Mock plugin with sync lifecycle for testing."""

    def __init__(self, name: str = "sync_test_plugin"):
        self.name = name
        self.initialized = False
        self.cleaned_up = False

    def initialize(self) -> None:
        """Sync initialization."""
        self.initialized = True

    def cleanup(self) -> None:
        """Sync cleanup."""
        self.cleaned_up = True


# Plugin Metadata Tests


class TestPluginMetadata:
    """Test plugin metadata validation and creation."""

    def test_plugin_compatibility_validation(self):
        """Test plugin compatibility validation."""
        # Valid compatibility
        compatibility = PluginCompatibility(min_fapilog_version="3.0.0")
        assert compatibility.min_fapilog_version == "3.0.0"
        assert compatibility.max_fapilog_version is None

        # With max version
        compatibility = PluginCompatibility(
            min_fapilog_version="3.0.0", max_fapilog_version="4.0.0"
        )
        assert compatibility.max_fapilog_version == "4.0.0"

    def test_plugin_compatibility_invalid_version(self):
        """Test plugin compatibility with invalid version."""
        with pytest.raises(ValueError, match="Invalid version string"):
            PluginCompatibility(min_fapilog_version="invalid-version")

    def test_plugin_metadata_creation(self):
        """Test plugin metadata creation and validation."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.plugin_type == "sink"
        assert metadata.compatibility.min_fapilog_version == "3.0.0"

    def test_plugin_metadata_invalid_type(self):
        """Test plugin metadata with invalid plugin type."""
        with pytest.raises(ValueError, match="Invalid plugin type"):
            PluginMetadata(
                name="test-plugin",
                version="1.0.0",
                description="Test plugin",
                author="Test Author",
                plugin_type="invalid_type",
                entry_point="test_plugin.main",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )

    def test_plugin_metadata_invalid_version(self):
        """Test plugin metadata with invalid version."""
        with pytest.raises(ValueError, match="Invalid version string"):
            PluginMetadata(
                name="test-plugin",
                version="invalid-version",
                description="Test plugin",
                author="Test Author",
                plugin_type="sink",
                entry_point="test_plugin.main",
                compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
            )

    def test_create_plugin_metadata_helper(self):
        """Test create_plugin_metadata helper function."""
        metadata = create_plugin_metadata(
            name="helper-plugin",
            version="1.0.0",
            plugin_type="processor",
            entry_point="helper.main",
            description="Helper plugin",
            author="Helper Author",
        )

        assert metadata.name == "helper-plugin"
        assert metadata.plugin_type == "processor"
        assert metadata.compatibility.min_fapilog_version == "3.0.0"

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_validate_fapilog_compatibility_compatible(self, mock_version):
        """Test compatibility validation with compatible versions."""
        mock_version.return_value = "3.1.0"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )

        assert validate_fapilog_compatibility(metadata) is True

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_validate_fapilog_compatibility_incompatible(self, mock_version):
        """Test compatibility validation with incompatible versions."""
        mock_version.return_value = "2.9.0"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0"),
        )

        assert validate_fapilog_compatibility(metadata) is False

    @patch("fapilog.plugins.metadata.importlib.metadata.version")
    def test_validate_fapilog_compatibility_max_version(self, mock_version):
        """Test compatibility validation with max version constraint."""
        mock_version.return_value = "4.1.0"

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type="sink",
            entry_point="test_plugin.main",
            compatibility=PluginCompatibility(
                min_fapilog_version="3.0.0", max_fapilog_version="4.0.0"
            ),
        )

        assert validate_fapilog_compatibility(metadata) is False


# Plugin Discovery Tests
@pytest.mark.asyncio
class TestPluginDiscovery:
    """Test plugin discovery functionality."""

    @pytest.fixture
    def discovery(self):
        """Create a plugin discovery instance."""
        return AsyncPluginDiscovery()

    @pytest.fixture
    def temp_plugin_dir(self, tmp_path):
        """Create a temporary plugin directory."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()
        return plugin_dir

    async def test_discover_all_plugins_empty(self, discovery):
        """Test discovering plugins when none exist."""
        plugins = await discovery.discover_all_plugins()
        assert isinstance(plugins, dict)
        assert len(plugins) == 0

    async def test_discover_plugins_by_type(self, discovery):
        """Test discovering plugins by type."""
        plugins = await discovery.discover_plugins_by_type("sink")
        assert isinstance(plugins, dict)

    async def test_add_remove_discovery_path(self, discovery, temp_plugin_dir):
        """Test adding and removing discovery paths."""
        # Add discovery path
        discovery.add_discovery_path(temp_plugin_dir)
        paths = discovery.get_discovery_paths()
        assert temp_plugin_dir in paths

        # Remove discovery path
        discovery.remove_discovery_path(temp_plugin_dir)
        paths = discovery.get_discovery_paths()
        assert temp_plugin_dir not in paths

    async def test_discover_local_plugins(self, discovery, temp_plugin_dir):
        """Test discovering local plugins."""
        discovery.add_discovery_path(temp_plugin_dir)
        plugins = await discovery.discover_all_plugins()
        assert isinstance(plugins, dict)

    async def test_get_plugin_info(self, discovery, temp_plugin_dir):
        """Test getting plugin info."""
        discovery.add_discovery_path(temp_plugin_dir)
        await discovery.discover_all_plugins()

        # Test getting non-existent plugin
        plugin_info = await discovery.get_plugin_info("test-local-plugin")
        assert plugin_info is None

        # Test getting non-existent plugin after rediscovery
        plugin_info = await discovery.get_plugin_info("non-existent")
        assert plugin_info is None

    async def test_list_discovered_plugins(self, discovery, temp_plugin_dir):
        """Test listing discovered plugins."""
        discovery.add_discovery_path(temp_plugin_dir)
        await discovery.discover_all_plugins()

        plugin_names = discovery.list_discovered_plugins()
        assert isinstance(plugin_names, list)

    async def test_get_plugins_by_type(self, discovery, temp_plugin_dir):
        """Test getting plugins by type."""
        discovery.add_discovery_path(temp_plugin_dir)
        await discovery.discover_all_plugins()

        sink_plugins = discovery.get_plugins_by_type("sink")
        assert isinstance(sink_plugins, dict)

        processor_plugins = discovery.get_plugins_by_type("processor")
        assert isinstance(processor_plugins, dict)

    async def test_pypi_marketplace_discovery(self):
        """Test PyPI marketplace discovery functionality."""
        discovery = AsyncPluginDiscovery()

        # Test that PyPI discovery doesn't crash
        await discovery._discover_pypi_plugins()

        # Test that installed package detection works
        result = discovery._is_fapilog_plugin_package("not-a-plugin", None)
        assert result is False  # No distribution provided

        # Test with a mock distribution
        class MockDist:
            def __init__(self, name, keywords=""):
                self.metadata = {"Name": name, "Keywords": keywords}

        # Test fapilog- prefix detection
        mock_dist = MockDist("fapilog-splunk-sink")
        result = discovery._is_fapilog_plugin_package("fapilog-splunk-sink", mock_dist)
        assert result is True

        # Test keyword detection
        mock_dist = MockDist("my-plugin", "fapilog plugin sink")
        result = discovery._is_fapilog_plugin_package("my-plugin", mock_dist)
        assert result is True

        # Test non-plugin package
        mock_dist = MockDist("requests")
        result = discovery._is_fapilog_plugin_package("requests", mock_dist)
        assert result is False

    async def test_entry_point_processing_error(self, discovery):
        """Test entry point processing with error."""

        # Create a mock entry point that will fail
        class MockEntryPoint:
            def __init__(self, name):
                self.name = name

            def load(self):
                raise ImportError("Failed to load module")

        mock_entry_point = MockEntryPoint("test-plugin")
        await discovery._process_entry_point(mock_entry_point)

        # Should create error plugin info
        assert "test-plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["test-plugin"]
        assert not plugin_info.loaded
        assert plugin_info.load_error is not None

    async def test_entry_point_with_metadata(self, discovery):
        """Test entry point processing with valid metadata."""

        # Create a mock entry point with metadata
        class MockModule:
            PLUGIN_METADATA = {
                "name": "test-plugin",
                "version": "1.0.0",
                "plugin_type": "sink",
                "entry_point": "test_plugin.main",
                "description": "Test plugin",
                "author": "test",
                "compatibility": {"min_fapilog_version": "3.0.0"},
            }

        class MockEntryPoint:
            def __init__(self, name):
                self.name = name

            def load(self):
                return MockModule()

        # Mock the compatibility validation to return True
        with patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=True,
        ):
            mock_entry_point = MockEntryPoint("test-plugin")
            await discovery._process_entry_point(mock_entry_point)

            # Should create plugin info
            assert "test-plugin" in discovery._discovered_plugins
            plugin_info = discovery._discovered_plugins["test-plugin"]
            assert not plugin_info.loaded
            assert plugin_info.load_error is None

    async def test_entry_point_incompatible_version(self, discovery):
        """Test entry point with incompatible version."""

        # Create a mock entry point with incompatible metadata
        class MockModule:
            PLUGIN_METADATA = {
                "name": "incompatible-plugin",
                "version": "1.0.0",
                "plugin_type": "sink",
                "entry_point": "incompatible_plugin",
                "description": "Incompatible plugin",
                "author": "test",
                "compatibility": {
                    "min_fapilog_version": "999.0.0"
                },  # Very high version
            }

        class MockEntryPoint:
            def __init__(self, name):
                self.name = name

            def load(self):
                return MockModule()

        # Mock the compatibility validation to return False
        with patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=False,
        ):
            mock_entry_point = MockEntryPoint("incompatible-plugin")
            await discovery._process_entry_point(mock_entry_point)

            # Should create plugin info with error
            assert "incompatible-plugin" in discovery._discovered_plugins
            plugin_info = discovery._discovered_plugins["incompatible-plugin"]
            assert not plugin_info.loaded
            assert "Incompatible" in plugin_info.load_error

    async def test_local_plugin_processing_error(self, discovery, tmp_path):
        """Test local plugin processing with error."""
        # Create a plugin file that will cause an error
        plugin_file = tmp_path / "broken_plugin.py"
        plugin_file.write_text("invalid python code {")

        discovery.add_discovery_path(tmp_path)
        await discovery._process_local_plugin_file(plugin_file)

        # Should create error plugin info
        assert "broken_plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["broken_plugin"]
        assert not plugin_info.loaded
        assert plugin_info.load_error is not None

    async def test_local_plugin_with_metadata(self, discovery, tmp_path):
        """Test local plugin processing with valid metadata."""
        # Create a plugin file with metadata
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("""
PLUGIN_METADATA = {
    "name": "test-local-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "test_local_plugin",
    "description": "Test local plugin",
    "author": "test",
    "compatibility": {"min_fapilog_version": "3.0.0"},
}
""")

        discovery.add_discovery_path(tmp_path)

        # Mock the compatibility validation to return True
        with patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=True,
        ):
            await discovery._process_local_plugin_file(plugin_file)

            # Should create plugin info
            assert "test-local-plugin" in discovery._discovered_plugins
            plugin_info = discovery._discovered_plugins["test-local-plugin"]
            assert not plugin_info.loaded
            assert plugin_info.load_error is None

    async def test_local_plugin_incompatible_version(self, discovery, tmp_path):
        """Test local plugin with incompatible version."""
        # Create a plugin file with incompatible metadata
        plugin_file = tmp_path / "incompatible_plugin.py"
        plugin_file.write_text("""
PLUGIN_METADATA = {
    "name": "incompatible-local-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "incompatible_local_plugin",
    "description": "Incompatible local plugin",
    "author": "test",
    "compatibility": {"min_fapilog_version": "999.0.0"},
}
""")

        discovery.add_discovery_path(tmp_path)

        # Mock the compatibility validation to return False
        with patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=False,
        ):
            await discovery._process_local_plugin_file(plugin_file)

            # Should create plugin info with error
            assert "incompatible-local-plugin" in discovery._discovered_plugins
            plugin_info = discovery._discovered_plugins["incompatible-local-plugin"]
            assert not plugin_info.loaded
            assert "Incompatible" in plugin_info.load_error

    async def test_scan_directory_error(self, discovery, tmp_path):
        """Test scanning directory with error."""
        # Create a directory that will cause an error
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create a file that will cause an error during processing
        plugin_file = plugin_dir / "broken_plugin.py"
        plugin_file.write_text("invalid python code {")

        discovery.add_discovery_path(plugin_dir)

        # Should not raise exception, should handle error gracefully
        await discovery._scan_directory_for_plugins(plugin_dir)

    async def test_scan_directory_private_files(self, discovery, tmp_path):
        """Test scanning directory skips private files."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Create private files that should be skipped
        private_file = plugin_dir / "_private.py"
        private_file.write_text("PLUGIN_METADATA = {}")

        # Create public file
        public_file = plugin_dir / "public.py"
        public_file.write_text("PLUGIN_METADATA = {}")

        discovery.add_discovery_path(plugin_dir)
        await discovery._scan_directory_for_plugins(plugin_dir)

        # Should not discover private files
        assert "_private" not in discovery._discovered_plugins

    async def test_process_installed_package_error(self, discovery):
        """Test processing installed package with error."""

        # Create a mock distribution that will cause an error
        class MockDist:
            def __init__(self, name):
                self.metadata = {"Name": name}

        mock_dist = MockDist("test-package")

        # Mock the entry points to cause an error
        with pytest.MonkeyPatch().context() as m:
            m.setattr(importlib.metadata, "entry_points", lambda: {})
            await discovery._process_installed_package(mock_dist)

    async def test_discovery_path_management(self, discovery):
        """Test discovery path management."""
        # Test adding paths
        path1 = Path("/tmp/plugins1")
        path2 = Path("/tmp/plugins2")

        discovery.add_discovery_path(path1)
        discovery.add_discovery_path(str(path2))

        paths = discovery.get_discovery_paths()
        assert path1 in paths
        assert path2 in paths

        # Test removing paths
        discovery.remove_discovery_path(path1)
        discovery.remove_discovery_path(str(path2))

        paths = discovery.get_discovery_paths()
        assert path1 not in paths
        assert path2 not in paths

    async def test_global_discovery_instance(self):
        """Test global discovery instance singleton."""
        # Test first call creates instance
        instance1 = await get_discovery_instance()
        assert isinstance(instance1, AsyncPluginDiscovery)

        # Test second call returns same instance
        instance2 = await get_discovery_instance()
        assert instance1 is instance2

    async def test_discover_plugins_convenience(self):
        """Test convenience functions."""
        # Test discover_plugins
        plugins = await discover_plugins()
        assert isinstance(plugins, dict)

        # Test discover_plugins_by_type
        sink_plugins = await discover_plugins_by_type("sink")
        assert isinstance(sink_plugins, dict)

    async def test_entry_point_discovery_error(self, discovery):
        """Test entry point discovery with error."""
        # Mock entry_points to raise an exception
        with patch(
            "importlib.metadata.entry_points",
            side_effect=Exception("Entry points error"),
        ):
            with pytest.raises(PluginDiscoveryError):
                await discovery._discover_entry_point_plugins()

    async def test_pypi_discovery_error(self, discovery):
        """Test PyPI discovery with error."""
        # Mock distributions to raise an exception
        with patch(
            "importlib.metadata.distributions",
            side_effect=Exception("Distributions error"),
        ):
            # Should not raise exception, should handle error gracefully
            await discovery._discover_installed_pypi_plugins()

    async def test_local_plugin_path_management(self, discovery, tmp_path):
        """Test local plugin path management."""
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("""
PLUGIN_METADATA = {
    "name": "test-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "test_plugin",
    "description": "Test plugin",
    "author": "test",
    "compatibility": {"min_fapilog_version": "3.0.0"},
}
""")

        # Test with path not in sys.path
        discovery.add_discovery_path(tmp_path)

        # Mock the compatibility validation to return True
        with patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=True,
        ):
            await discovery._process_local_plugin_file(plugin_file)

            # Should discover the plugin
            assert "test-plugin" in discovery._discovered_plugins

    async def test_local_plugin_path_already_in_sys_path(self, discovery, tmp_path):
        """Test local plugin processing when path is already in sys.path."""
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text("""
PLUGIN_METADATA = {
    "name": "test-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "test_plugin",
    "description": "Test plugin",
    "author": "test",
    "compatibility": {"min_fapilog_version": "3.0.0"},
}
""")

        # Add path to sys.path manually
        import sys

        original_path = sys.path.copy()
        sys.path.insert(0, str(tmp_path))

        try:
            discovery.add_discovery_path(tmp_path)

            # Mock the compatibility validation to return True
            with patch(
                "fapilog.plugins.discovery.validate_fapilog_compatibility",
                return_value=True,
            ):
                await discovery._process_local_plugin_file(plugin_file)

                # Should discover the plugin
                assert "test-plugin" in discovery._discovered_plugins
        finally:
            # Restore sys.path
            sys.path = original_path


# Component Lifecycle Tests


@pytest.mark.asyncio
class TestComponentLifecycle:
    """Test component lifecycle management."""

    @pytest.fixture
    def container_id(self):
        """Generate a unique container ID."""
        return str(uuid.uuid4())

    @pytest.fixture
    def plugin_info(self):
        """Create test plugin info."""
        metadata = create_plugin_metadata(
            name="lifecycle-test",
            version="1.0.0",
            plugin_type="sink",
            entry_point="test.Plugin",
        )
        return PluginInfo(metadata=metadata, source="test")

    async def test_lifecycle_manager_initialization(self, container_id):
        """Test lifecycle manager initialization."""
        manager = AsyncComponentLifecycleManager(container_id)
        assert manager.container_id == container_id
        assert not manager.is_initialized
        assert manager.component_count == 0

        await manager.initialize_all()
        assert manager.is_initialized

        await manager.cleanup_all()
        assert not manager.is_initialized

    async def test_component_registration(self, container_id, plugin_info):
        """Test component registration and lifecycle."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()

        # Register component
        await manager.register_component("test-plugin", plugin_info, plugin)
        assert manager.component_count == 1
        assert "test-plugin" in manager.list_components()

        # Initialize all components
        await manager.initialize_all()
        assert plugin.initialized

        # Get component
        retrieved = await manager.get_component("test-plugin")
        assert retrieved is plugin

        # Cleanup
        await manager.cleanup_all()
        assert plugin.cleaned_up

    async def test_component_unregistration(self, container_id, plugin_info):
        """Test component unregistration."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()

        await manager.register_component("test-plugin", plugin_info, plugin)
        await manager.initialize_all()

        # Unregister component
        await manager.unregister_component("test-plugin")
        assert manager.component_count == 0
        assert plugin.cleaned_up

    async def test_sync_plugin_lifecycle(self, container_id, plugin_info):
        """Test lifecycle with sync plugin methods."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = SyncMockPlugin()

        await manager.register_component("sync-plugin", plugin_info, plugin)
        await manager.initialize_all()
        assert plugin.initialized

        await manager.cleanup_all()
        assert plugin.cleaned_up

    async def test_cleanup_callbacks(self, container_id, plugin_info):
        """Test cleanup callbacks."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()
        callback_called = False

        async def cleanup_callback():
            nonlocal callback_called
            callback_called = True

        await manager.register_component("test-plugin", plugin_info, plugin)
        manager.add_cleanup_callback("test-plugin", cleanup_callback)

        await manager.initialize_all()
        await manager.cleanup_all()

        assert callback_called

    async def test_plugin_lifecycle_state(self, plugin_info):
        """Test plugin lifecycle state management."""
        plugin = MockPlugin()
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        assert not state.initialized
        await state.initialize()
        assert state.initialized
        assert plugin.initialized

        await state.cleanup()
        assert not state.initialized
        assert plugin.cleaned_up

    async def test_create_lifecycle_manager_context(self, container_id):
        """Test lifecycle manager context manager."""
        async with create_lifecycle_manager(container_id) as manager:
            assert isinstance(manager, AsyncComponentLifecycleManager)
            assert manager.container_id == container_id

    # NEW TESTS FOR MISSING COVERAGE

    async def test_plugin_lifecycle_state_idempotent_initialize(self, plugin_info):
        """Test that initialize is idempotent (line 53)."""
        plugin = MockPlugin()
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        # First initialization
        await state.initialize()
        assert state.initialized
        assert plugin.initialization_count == 1

        # Second initialization should not call plugin.initialize again
        await state.initialize()
        assert state.initialized
        assert plugin.initialization_count == 1  # Should not increment

    async def test_plugin_lifecycle_state_cleanup_not_initialized(self, plugin_info):
        """Test cleanup when not initialized (line 78)."""
        plugin = MockPlugin()
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        # Cleanup without initialization should do nothing
        await state.cleanup()
        assert not state.initialized
        assert not plugin.cleaned_up

    async def test_plugin_lifecycle_state_cleanup_callbacks_exception_handling(
        self, plugin_info
    ):
        """Test cleanup callback exception handling (lines 84-86)."""
        plugin = MockPlugin()
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        callback1_called = False
        callback2_called = False

        async def failing_callback():
            nonlocal callback1_called
            callback1_called = True
            raise RuntimeError("Callback failed")

        async def succeeding_callback():
            nonlocal callback2_called
            callback2_called = True

        state.add_cleanup_callback(failing_callback)
        state.add_cleanup_callback(succeeding_callback)

        await state.initialize()
        await state.cleanup()

        # Both callbacks should be called even if one fails
        assert callback1_called
        assert callback2_called
        assert not state.initialized

    async def test_plugin_lifecycle_state_plugin_cleanup_exception_handling(
        self, plugin_info
    ):
        """Test plugin cleanup exception handling (lines 98-100)."""
        plugin = MockPlugin()
        plugin.cleanup_should_fail = True  # Make cleanup fail
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        await state.initialize()
        # Cleanup should not raise exception even if plugin.cleanup fails
        await state.cleanup()
        assert not state.initialized

    async def test_lifecycle_manager_duplicate_registration_error(
        self, container_id, plugin_info
    ):
        """Test duplicate component registration error (lines 152, 166)."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin1 = MockPlugin()
        plugin2 = MockPlugin()

        # First registration should succeed
        await manager.register_component("test-plugin", plugin_info, plugin1)

        # Second registration with same name should fail
        with pytest.raises(
            ComponentLifecycleError, match="Plugin test-plugin is already registered"
        ):
            await manager.register_component("test-plugin", plugin_info, plugin2)

    async def test_lifecycle_manager_unregister_nonexistent_component(
        self, container_id
    ):
        """Test unregistering non-existent component (line 177)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Unregister non-existent component should not raise error
        await manager.unregister_component("nonexistent")
        assert manager.component_count == 0

    async def test_lifecycle_manager_initialize_all_with_errors(
        self, container_id, plugin_info
    ):
        """Test initialize_all with plugin errors (lines 187, 194-195, 198-199)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Create plugins that will fail initialization
        failing_plugin1 = MockPlugin()
        failing_plugin1.initialize_should_fail = True
        failing_plugin1.name = "failing-plugin-1"

        failing_plugin2 = MockPlugin()
        failing_plugin2.initialize_should_fail = True
        failing_plugin2.name = "failing-plugin-2"

        await manager.register_component("failing-1", plugin_info, failing_plugin1)
        await manager.register_component("failing-2", plugin_info, failing_plugin2)

        # Initialize all should fail with combined error message
        with pytest.raises(
            ComponentLifecycleError, match="Failed to initialize plugins:"
        ):
            await manager.initialize_all()

        assert not manager.is_initialized

    async def test_lifecycle_manager_cleanup_all_not_initialized(self, container_id):
        """Test cleanup_all when not initialized (line 213-215)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Cleanup without initialization should do nothing
        await manager.cleanup_all()
        assert not manager.is_initialized
        assert manager.component_count == 0

    async def test_lifecycle_manager_cleanup_all_with_plugin_errors(
        self, container_id, plugin_info
    ):
        """Test cleanup_all with plugin cleanup errors (lines 223-224)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Create plugin that will fail cleanup
        failing_plugin = MockPlugin()
        failing_plugin.cleanup_should_fail = True

        await manager.register_component("failing-plugin", plugin_info, failing_plugin)
        await manager.initialize_all()

        # Cleanup should not raise exception even if plugin.cleanup fails
        await manager.cleanup_all()
        assert not manager.is_initialized
        assert manager.component_count == 0

    async def test_lifecycle_manager_cleanup_all_resource_cleanup_error(
        self, container_id, plugin_info
    ):
        """Test cleanup_all with resource cleanup error (line 240)."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()

        await manager.register_component("test-plugin", plugin_info, plugin)
        await manager.initialize_all()

        # Mock resource manager to fail cleanup
        with patch.object(
            manager._resources,
            "cleanup_all",
            side_effect=RuntimeError("Resource cleanup failed"),
        ):
            # Cleanup should not raise exception even if resource cleanup fails
            await manager.cleanup_all()
            assert not manager.is_initialized
            assert manager.component_count == 0

    async def test_lifecycle_manager_get_component_not_initialized(
        self, container_id, plugin_info
    ):
        """Test get_component when component not initialized (line 279-282)."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()

        await manager.register_component("test-plugin", plugin_info, plugin)
        # Don't initialize

        # Get component should return None when not initialized
        retrieved = await manager.get_component("test-plugin")
        assert retrieved is None

    async def test_lifecycle_manager_get_component_nonexistent(self, container_id):
        """Test get_component with non-existent component (line 287)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Get non-existent component should return None
        retrieved = await manager.get_component("nonexistent")
        assert retrieved is None

    async def test_lifecycle_manager_add_cleanup_callback_nonexistent_component(
        self, container_id
    ):
        """Test add_cleanup_callback with non-existent component."""
        manager = AsyncComponentLifecycleManager(container_id)

        async def dummy_callback():
            pass

        # Adding callback to non-existent component should not raise error
        manager.add_cleanup_callback("nonexistent", dummy_callback)

    async def test_lifecycle_manager_get_component_info(
        self, container_id, plugin_info
    ):
        """Test get_component_info method."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()

        await manager.register_component("test-plugin", plugin_info, plugin)

        # Get component info should return plugin info
        retrieved_info = manager.get_component_info("test-plugin")
        assert retrieved_info is plugin_info

        # Get info for non-existent component should return None
        retrieved_info = manager.get_component_info("nonexistent")
        assert retrieved_info is None

    async def test_lifecycle_manager_resources_property(self, container_id):
        """Test resources property access."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Should return ResourceManager instance
        assert isinstance(manager.resources, ResourceManager)
        assert manager.resources is manager._resources

    async def test_lifecycle_manager_weakref_self(self, container_id):
        """Test weakref self reference."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Weakref should reference self
        weakref_self = manager._weakref_self()
        assert weakref_self is manager

    async def test_create_lifecycle_manager_exception_handling(
        self, container_id, plugin_info
    ):
        """Test create_lifecycle_manager exception handling."""
        # Test that cleanup happens even if exception occurs in context
        try:
            async with create_lifecycle_manager(container_id) as manager:
                await manager.register_component("test", plugin_info, MockPlugin())
                await manager.initialize_all()
                raise RuntimeError("Test exception")
        except RuntimeError:
            pass

        # Manager should be cleaned up even after exception
        # We can't directly check this, but the test should complete without hanging

    async def test_plugin_lifecycle_state_plugin_initialize_exception(
        self, plugin_info
    ):
        """Test plugin initialization exception handling."""
        plugin = MockPlugin()
        plugin.initialize_should_fail = True
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        # Initialization should fail with ComponentLifecycleError
        with pytest.raises(
            ComponentLifecycleError, match="Failed to initialize plugin lifecycle-test:"
        ):
            await state.initialize()

        assert not state.initialized

    async def test_plugin_lifecycle_state_plugin_cleanup_exception(self, plugin_info):
        """Test plugin cleanup exception handling."""
        plugin = MockPlugin()
        plugin.cleanup_should_fail = True
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        await state.initialize()
        # Cleanup should not raise exception even if plugin.cleanup fails
        await state.cleanup()
        assert not state.initialized

    async def test_plugin_lifecycle_state_cleanup_callbacks_order(self, plugin_info):
        """Test cleanup callbacks are executed in reverse order."""
        plugin = MockPlugin()
        state = PluginLifecycleState(plugin_info, plugin, "test-container")

        callback_order = []

        async def callback1():
            callback_order.append(1)

        async def callback2():
            callback_order.append(2)

        async def callback3():
            callback_order.append(3)

        state.add_cleanup_callback(callback1)
        state.add_cleanup_callback(callback2)
        state.add_cleanup_callback(callback3)

        await state.initialize()
        await state.cleanup()

        # Callbacks should be executed in reverse order (3, 2, 1)
        assert callback_order == [3, 2, 1]

    async def test_lifecycle_manager_register_component_immediate_initialization(
        self, container_id, plugin_info
    ):
        """Test immediate initialization when registering to already initialized manager (line 166)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Initialize the manager first
        await manager.initialize_all()
        assert manager.is_initialized

        # Now register a component - it should be initialized immediately
        plugin = MockPlugin()
        await manager.register_component("test-plugin", plugin_info, plugin)

        # Component should be initialized immediately since manager was already initialized
        assert plugin.initialized
        assert await manager.get_component("test-plugin") is plugin

    async def test_lifecycle_manager_initialize_all_idempotent(
        self, container_id, plugin_info
    ):
        """Test that initialize_all is idempotent (line 187)."""
        manager = AsyncComponentLifecycleManager(container_id)
        plugin = MockPlugin()

        await manager.register_component("test-plugin", plugin_info, plugin)

        # First initialization
        await manager.initialize_all()
        assert manager.is_initialized
        assert plugin.initialization_count == 1

        # Second initialization should not re-initialize components
        await manager.initialize_all()
        assert manager.is_initialized
        assert plugin.initialization_count == 1  # Should not increment

    async def test_lifecycle_manager_cleanup_all_idempotent(
        self, container_id, plugin_info
    ):
        """Test that cleanup_all is idempotent (lines 213-215)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Register and initialize components so cleanup loop body is executed
        plugin1 = MockPlugin()
        plugin2 = MockPlugin()
        await manager.register_component("plugin1", plugin_info, plugin1)
        await manager.register_component("plugin2", plugin_info, plugin2)
        await manager.initialize_all()

        # First cleanup should actually clean up components
        await manager.cleanup_all()
        assert not manager.is_initialized
        assert manager.component_count == 0
        assert plugin1.cleaned_up
        assert plugin2.cleaned_up

        # Second cleanup should do nothing
        await manager.cleanup_all()
        assert not manager.is_initialized
        assert manager.component_count == 0

    async def test_lifecycle_manager_cleanup_all_loop_execution(
        self, container_id, plugin_info
    ):
        """Test that cleanup_all loop body is executed (lines 213-215)."""
        manager = AsyncComponentLifecycleManager(container_id)

        # Create multiple plugins to ensure loop iteration
        plugins = []
        for i in range(3):
            plugin = MockPlugin()
            plugins.append(plugin)
            await manager.register_component(f"plugin-{i}", plugin_info, plugin)

        await manager.initialize_all()
        assert manager.component_count == 3

        # This should execute the cleanup loop for each component
        await manager.cleanup_all()
        assert not manager.is_initialized
        assert manager.component_count == 0

        # Verify all plugins were cleaned up
        for plugin in plugins:
            assert plugin.cleaned_up


# Component Isolation Tests


class TestComponentIsolation:
    """Test component isolation between containers."""

    def test_isolation_mixin(self):
        """Test component isolation mixin."""
        container_id = "test-container-123"
        mixin = ComponentIsolationMixin(container_id)

        assert mixin.container_id == container_id

        # Test isolated naming
        isolated_name = mixin.get_isolated_name("plugin-name")
        assert isolated_name == f"container_{container_id}_plugin-name"

        # Test container comparison
        assert mixin.is_same_container(container_id)
        assert not mixin.is_same_container("different-container")

    async def test_container_isolation(self):
        """Test that different containers have isolated components."""
        # Create two different lifecycle managers
        manager1 = AsyncComponentLifecycleManager("container-1")
        manager2 = AsyncComponentLifecycleManager("container-2")

        plugin_info = PluginInfo(
            metadata=create_plugin_metadata(
                name="isolation-test",
                version="1.0.0",
                plugin_type="sink",
                entry_point="test.Plugin",
            ),
            source="test",
        )

        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        # Register same plugin name in both containers
        await manager1.register_component("test-plugin", plugin_info, plugin1)
        await manager2.register_component("test-plugin", plugin_info, plugin2)

        await manager1.initialize_all()
        await manager2.initialize_all()

        # Each container should have its own instance
        retrieved1 = await manager1.get_component("test-plugin")
        retrieved2 = await manager2.get_component("test-plugin")

        assert retrieved1 is plugin1
        assert retrieved2 is plugin2
        assert retrieved1 is not retrieved2

        # Cleanup
        await manager1.cleanup_all()
        await manager2.cleanup_all()


# Plugin Registry Tests


@pytest.mark.asyncio
class TestPluginRegistry:
    """Test the complete plugin registry functionality."""

    @pytest.fixture
    async def container(self):
        """Create an async container for testing."""
        async with create_container() as container:
            yield container

    @pytest.fixture
    async def registry(self, container):
        """Create a plugin registry for testing."""
        registry = await create_component_registry(container)
        yield registry
        await registry.cleanup()

    @pytest.fixture
    def temp_plugin_dir(self):
        """Create a temporary directory with test plugins."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir)

            # Create a test plugin file
            plugin_file = plugin_dir / "registry_test_plugin.py"
            plugin_content = f"""
PLUGIN_METADATA = {{
    "name": "registry-test-plugin",
    "version": "1.0.0",
    "description": "Registry test plugin",
    "author": "Test Author",
    "plugin_type": "sink",
    "entry_point": "{plugin_file}",
    "compatibility": {{
        "min_fapilog_version": "3.0.0a1"
    }}
}}

class Plugin:
    def __init__(self):
        self.name = "registry-test-plugin"
        self.initialized = False

    async def initialize(self):
        self.initialized = True

    async def cleanup(self):
        self.initialized = False
"""
            plugin_file.write_text(plugin_content)
            yield plugin_dir

    async def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert registry.is_initialized
        assert registry.loaded_plugin_count == 0

    async def test_discover_plugins(self, registry, temp_plugin_dir):
        """Test plugin discovery through registry."""
        registry.add_discovery_path(temp_plugin_dir)
        plugins = await registry.discover_plugins()

        assert isinstance(plugins, dict)
        # Should rediscover and include our test plugin
        assert "registry-test-plugin" in plugins

    async def test_discover_plugins_by_type(self, registry, temp_plugin_dir):
        """Test discovering plugins by type through registry."""
        registry.add_discovery_path(temp_plugin_dir)
        sink_plugins = await registry.discover_plugins("sink")

        assert "registry-test-plugin" in sink_plugins

        processor_plugins = await registry.discover_plugins("processor")
        assert "registry-test-plugin" not in processor_plugins

    async def test_load_plugin(self, registry, temp_plugin_dir):
        """Test loading a plugin."""
        registry.add_discovery_path(temp_plugin_dir)
        await registry.discover_plugins()

        # Load the plugin
        plugin_instance = await registry.load_plugin("registry-test-plugin")
        assert plugin_instance is not None
        assert plugin_instance.name == "registry-test-plugin"
        assert registry.loaded_plugin_count == 1

        # Check plugin is in loaded list
        loaded_plugins = registry.list_loaded_plugins()
        assert "registry-test-plugin" in loaded_plugins

    async def test_load_nonexistent_plugin(self, registry):
        """Test loading a non-existent plugin."""
        with pytest.raises(PluginRegistryError, match="Plugin 'nonexistent' not found"):
            await registry.load_plugin("nonexistent")

    async def test_get_plugin_with_type_safety(self, registry, temp_plugin_dir):
        """Test getting plugin with type safety."""
        registry.add_discovery_path(temp_plugin_dir)
        await registry.load_plugin("registry-test-plugin")

        # Should work with correct type (using object as base type)
        plugin = await registry.get_plugin("registry-test-plugin", object)
        assert plugin is not None

        # Should return None for wrong type
        plugin = await registry.get_plugin("registry-test-plugin", int)
        assert plugin is None

    async def test_unload_plugin(self, registry, temp_plugin_dir):
        """Test unloading a plugin."""
        registry.add_discovery_path(temp_plugin_dir)
        await registry.load_plugin("registry-test-plugin")
        assert registry.loaded_plugin_count == 1

        # Unload the plugin
        await registry.unload_plugin("registry-test-plugin")
        assert registry.loaded_plugin_count == 0

        # Should not be in loaded list anymore
        loaded_plugins = registry.list_loaded_plugins()
        assert "registry-test-plugin" not in loaded_plugins

    async def test_load_plugins_by_type(self, registry, temp_plugin_dir):
        """Test loading all plugins of a specific type."""
        registry.add_discovery_path(temp_plugin_dir)
        sink_plugins = await registry.load_plugins_by_type("sink")

        assert "registry-test-plugin" in sink_plugins
        assert registry.loaded_plugin_count >= 1

    async def test_registry_cleanup(self, container):
        """Test registry cleanup and memory management."""
        registry = await create_component_registry(container)

        # Create a weakref to check if registry is properly cleaned up
        import weakref

        weak_registry = weakref.ref(registry)
        assert weak_registry() is not None

        await registry.cleanup()
        del registry

        # Force garbage collection to ensure cleanup
        import gc

        gc.collect()

        # Note: weakref test might not work in all Python implementations
        # The important thing is that cleanup() doesn't raise exceptions

    async def test_plugin_info_retrieval(self, registry, temp_plugin_dir):
        """Test retrieving plugin information."""
        registry.add_discovery_path(temp_plugin_dir)
        await registry.load_plugin("registry-test-plugin")

        plugin_info = registry.get_plugin_info("registry-test-plugin")
        assert plugin_info is not None
        assert plugin_info.metadata.name == "registry-test-plugin"
        assert plugin_info.loaded

    async def test_discovery_path_management(self, registry, temp_plugin_dir):
        """Test adding and removing discovery paths."""
        # Initially no plugins discovered
        plugins = await registry.discover_plugins()
        assert "registry-test-plugin" not in plugins

        # Add discovery path
        registry.add_discovery_path(temp_plugin_dir)
        plugins = await registry.discover_plugins()
        assert "registry-test-plugin" in plugins

        # Remove discovery path
        registry.remove_discovery_path(temp_plugin_dir)
        # Note: plugins already discovered remain in the registry until rediscovery


# Memory and Performance Tests


@pytest.mark.asyncio
class TestCoverageImprovement:
    """Test cases to improve code coverage for registry and discovery."""

    @pytest.mark.asyncio
    async def test_registry_initialization_failure(self, tmp_path):
        """Test registry initialization failure handling."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)

        # Mock discovery to raise an exception
        with patch.object(
            registry._discovery,
            "discover_all_plugins",
            new=AsyncMock(side_effect=Exception("Discovery failed")),
        ):
            with pytest.raises(
                PluginRegistryError, match="Failed to initialize plugin registry"
            ):
                await registry.initialize()

    @pytest.mark.asyncio
    async def test_registry_cleanup_when_not_initialized(self):
        """Test cleanup when registry is not initialized."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
            # Should not raise an exception
            await registry.cleanup()

    @pytest.mark.asyncio
    async def test_registry_cleanup_with_exception(self):
        """Test cleanup with exception handling."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
        await registry.initialize()

        # Mock lifecycle manager to raise exception during cleanup
        with patch.object(
            registry._lifecycle_manager,
            "cleanup_all",
            new=AsyncMock(side_effect=Exception("Cleanup failed")),
        ):
            # Should not raise an exception - errors are swallowed
            await registry.cleanup()

    @pytest.mark.asyncio
    async def test_unload_nonexistent_plugin(self):
        """Test unloading a plugin that doesn't exist."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
        await registry.initialize()
        # Should not raise an exception
        await registry.unload_plugin("nonexistent-plugin")

    @pytest.mark.asyncio
    async def test_plugin_load_failure_error_tracking(self, tmp_path):
        """Test that plugin load errors are tracked properly."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
        # Create a broken plugin file
        broken_plugin = tmp_path / "broken_plugin.py"
        broken_content = """
PLUGIN_METADATA = {
    "name": "broken-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "broken_plugin.py",
    "compatibility": {"min_fapilog_version": "3.0.0a1"}
}

# This will cause an import error
import nonexistent_module
"""
        broken_plugin.write_text(broken_content)

        registry.add_discovery_path(tmp_path)
        await registry.initialize()
        await registry.discover_plugins()

        # Check that the plugin was discovered but with an error
        plugin_info = await registry._discovery.get_plugin_info("broken_plugin")
        assert plugin_info is not None
        assert plugin_info.load_error is not None

    @pytest.mark.asyncio
    async def test_entry_point_loading_path(self):
        """Test entry point loading path (though we can't test real entry points)."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
        await registry.initialize()

        # Create a mock plugin info with entry_point source
        from fapilog.plugins.discovery import PluginInfo
        from fapilog.plugins.metadata import PluginCompatibility, PluginMetadata

        metadata = PluginMetadata(
            name="entry-point-plugin",
            version="1.0.0",
            plugin_type="sink",
            entry_point="test_plugin",
            description="Test entry point plugin",
            author="Test",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0a1"),
        )

        plugin_info = PluginInfo(metadata=metadata, loaded=False, source="entry_point")

        # Add to discovery manually
        registry._discovery._discovered_plugins["entry-point-plugin"] = plugin_info

        # This should fail because the entry point doesn't actually exist
        with pytest.raises(PluginLoadError):
            await registry.load_plugin("entry-point-plugin")

    @pytest.mark.asyncio
    async def test_local_plugin_file_not_found(self):
        """Test loading local plugin when file doesn't exist."""
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
        await registry.initialize()

        from fapilog.plugins.discovery import PluginInfo
        from fapilog.plugins.metadata import PluginCompatibility, PluginMetadata

        metadata = PluginMetadata(
            name="missing-local-plugin",
            version="1.0.0",
            plugin_type="sink",
            entry_point="/nonexistent/path/plugin.py",
            description="Test missing local plugin",
            author="Test",
            compatibility=PluginCompatibility(min_fapilog_version="3.0.0a1"),
        )

        plugin_info = PluginInfo(metadata=metadata, loaded=False, source="local")

        registry._discovery._discovered_plugins["missing-local-plugin"] = plugin_info

        with pytest.raises(PluginLoadError, match="Plugin file not found"):
            await registry.load_plugin("missing-local-plugin")

    @pytest.mark.asyncio
    async def test_discovery_entry_point_error_handling(self):
        """Test discovery error handling for entry points."""
        discovery = AsyncPluginDiscovery()

        # Mock entry points to test error handling
        mock_entry_point = Mock()
        mock_entry_point.name = "test-plugin"
        mock_entry_point.load.side_effect = ImportError("Module not found")

        # This should handle the error gracefully
        await discovery._process_entry_point(mock_entry_point)

        # Check that an error plugin was created
        assert "test-plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["test-plugin"]
        assert plugin_info.load_error is not None

    @pytest.mark.asyncio
    async def test_discovery_entry_point_incompatible_version(self):
        """Test discovery of entry point with incompatible version."""
        discovery = AsyncPluginDiscovery()

        # Mock entry point with incompatible plugin
        mock_module = Mock()
        mock_module.PLUGIN_METADATA = {
            "name": "incompatible-plugin",
            "version": "1.0.0",
            "plugin_type": "sink",
            "entry_point": "test",
            "description": "Incompatible plugin",
            "author": "Test",
            "compatibility": {"min_fapilog_version": "99.0.0"},  # Way too high
        }

        mock_entry_point = Mock()
        mock_entry_point.name = "incompatible-plugin"
        mock_entry_point.load.return_value = mock_module

        await discovery._process_entry_point(mock_entry_point)

        # Check that plugin was discovered but marked as incompatible
        assert "incompatible-plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["incompatible-plugin"]
        assert plugin_info.load_error == "Incompatible with current Fapilog version"

    @pytest.mark.asyncio
    async def test_discovery_local_plugin_import_error(self, tmp_path):
        """Test discovery of local plugin with import error."""
        discovery = AsyncPluginDiscovery()
        discovery.add_discovery_path(tmp_path)

        # Create a plugin with import error
        broken_plugin = tmp_path / "import_error_plugin.py"
        broken_content = """
import this_module_does_not_exist

PLUGIN_METADATA = {
    "name": "import-error-plugin",
    "version": "1.0.0",
    "plugin_type": "sink"
}
"""
        broken_plugin.write_text(broken_content)

        await discovery._discover_local_plugins()

        # Check that error plugin was created
        assert "import_error_plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["import_error_plugin"]
        assert plugin_info.load_error is not None

    @pytest.mark.asyncio
    async def test_discovery_local_plugin_no_metadata(self, tmp_path):
        """Test discovery of local plugin without metadata."""
        discovery = AsyncPluginDiscovery()
        discovery.add_discovery_path(tmp_path)

        # Create a plugin without PLUGIN_METADATA
        no_metadata_plugin = tmp_path / "no_metadata_plugin.py"
        no_metadata_content = """
# This plugin has no PLUGIN_METADATA
def some_function():
    pass
"""
        no_metadata_plugin.write_text(no_metadata_content)

        await discovery._discover_local_plugins()

        # Plugin should not be discovered (no metadata)
        assert "no_metadata_plugin" not in discovery._discovered_plugins

    @pytest.mark.asyncio
    async def test_discovery_directory_scan_error(self, tmp_path):
        """Test discovery error when scanning directory fails."""
        discovery = AsyncPluginDiscovery()

        # Add a non-existent directory
        nonexistent_dir = tmp_path / "nonexistent"
        discovery.add_discovery_path(nonexistent_dir)

        # This should not raise an error for non-existent directory (it just skips it)
        # The directory doesn't exist, so no plugins will be discovered
        await discovery._discover_local_plugins()
        # Verify no plugins were discovered
        assert len(discovery._discovered_plugins) == 0

    @pytest.mark.asyncio
    async def test_discovery_python_version_compatibility(self):
        """Test discovery with different Python versions for entry points."""
        discovery = AsyncPluginDiscovery()

        # Force 3.8/3.9 code path (no select attr) by returning a dict
        with patch(
            "importlib.metadata.entry_points", return_value={"fapilog.plugins": []}
        ):
            # Should handle gracefully and not raise
            await discovery._discover_entry_point_plugins()

    @pytest.mark.asyncio
    async def test_pypi_wrapper_catches_inner_error(self):
        """_discover_pypi_plugins prints and swallows inner errors (lines 113-115)."""
        discovery = AsyncPluginDiscovery()
        with patch.object(
            discovery,
            "_discover_installed_pypi_plugins",
            new=AsyncMock(side_effect=Exception("boom")),
        ):
            # Should not raise
            await discovery._discover_pypi_plugins()

    @pytest.mark.asyncio
    async def test_installed_pypi_processing_error(self):
        """Installed package processing error is printed (lines 126-130)."""
        discovery = AsyncPluginDiscovery()

        class Dist:
            def __init__(self, name: str) -> None:
                self.metadata = {"Name": name, "Keywords": ""}

        bad = Dist("fapilog-bad")
        with patch("importlib.metadata.distributions", return_value=[bad]):
            with patch.object(
                discovery,
                "_process_installed_package",
                new=AsyncMock(side_effect=RuntimeError("x")),
            ):
                # Should print and continue without raising
                await discovery._discover_installed_pypi_plugins()

    @pytest.mark.asyncio
    async def test_is_fapilog_entry_points_branch(self):
        """Cover entry_points.get path and ep.dist name match (lines 158, 162-166)."""
        discovery = AsyncPluginDiscovery()

        class Dist:
            def __init__(self, name: str) -> None:
                self.metadata = {"Name": name, "Keywords": ""}

        class EPDist:
            def __init__(self, name: str) -> None:
                self.name = name

        class EP:
            def __init__(self, dist_name: str) -> None:
                self.dist = EPDist(dist_name)
                self.name = "ep"

        dist = Dist("mypkg")
        with patch(
            "importlib.metadata.entry_points",
            return_value={"fapilog.plugins": [EP("mypkg")]},
        ):
            assert discovery._is_fapilog_plugin_package("mypkg", dist) is True

    @pytest.mark.asyncio
    async def test_process_installed_package_success_and_error(self):
        """Cover _process_installed_package select path and error print (182, 188-199)."""
        discovery = AsyncPluginDiscovery()

        class Dist:
            def __init__(self, name: str) -> None:
                self.metadata = {"Name": name}

        class EPDist:
            def __init__(self, name: str) -> None:
                self.name = name

        class EP:
            def __init__(self, dist_name: str, name: str) -> None:
                self.dist = EPDist(dist_name)
                self.name = name

        d = Dist("pkg1")
        eps = Mock()
        eps.select.return_value = [EP("pkg1", "ep1"), EP("pkg1", "ep2")]

        # First run: inner processing raises to hit print at 196
        with patch("importlib.metadata.entry_points", return_value=eps):
            with patch.object(
                discovery,
                "_process_entry_point",
                new=AsyncMock(side_effect=RuntimeError("fail")),
            ):
                await discovery._process_installed_package(d)

        # Second run: outer exception path (lines 198-199)
        with patch("importlib.metadata.entry_points", side_effect=Exception("outer")):
            await discovery._process_installed_package(d)

    @pytest.mark.asyncio
    async def test_missing_coverage_lines(self):
        """Test various edge cases to improve coverage."""

        # Test lifecycle manager error scenarios
        from fapilog.plugins.lifecycle import AsyncComponentLifecycleManager

        async with create_container() as container:
            lifecycle_manager = AsyncComponentLifecycleManager("test-container")

            # Test cleanup with no registered plugins
            await lifecycle_manager.cleanup_all()

            # Test initialize with no plugins
            await lifecycle_manager.initialize_all()

        # Test discovery edge cases
        discovery = AsyncPluginDiscovery()

        # Test entry point discovery with empty list
        # Force 3.8/3.9 code path (no select) by returning a dict
        with patch(
            "importlib.metadata.entry_points", return_value={"fapilog.plugins": []}
        ):
            await discovery._discover_entry_point_plugins()

        # Test registry with no plugins
        async with create_container() as container:
            registry = AsyncComponentRegistry(container)
            await registry.initialize()

            # Test unloading from empty registry
            await registry.unload_plugin("nonexistent")

            # Test getting plugin info for nonexistent plugin
            info = registry.get_plugin_info("nonexistent")
            assert info is None

            # Test creating instance factory error handling
            plugin_info = await registry._discovery.get_plugin_info("nonexistent")
            assert plugin_info is None

            # Test discovery API calls through the discovery object
            assert len(registry._discovery._discovered_plugins) == 0
            discovered = registry._discovery.get_plugins_by_type("sink")
            assert len(discovered) == 0


class TestDiscoveryDetailedCoverage:
    """Targeted tests to improve discovery.py coverage to 90%+."""

    @pytest.mark.asyncio
    async def test_entry_point_processing_error_print(self):
        """Test error printing in entry point processing."""
        discovery = AsyncPluginDiscovery()

        # Mock the process_entry_point method to raise an exception
        with patch.object(
            discovery,
            "_process_entry_point",
            new=AsyncMock(side_effect=RuntimeError("Plugin load failed")),
        ):
            # Prepare entry_points to return one failing entry point
            mock_entry_point = Mock()
            mock_entry_point.name = "failing-plugin"
            mock_eps = Mock()
            mock_eps.select.return_value = [mock_entry_point]
            with patch("importlib.metadata.entry_points", return_value=mock_eps):
                with patch("builtins.print") as mock_print:
                    await discovery._discover_entry_point_plugins()
                    # Verify error was printed
                    assert mock_print.called
                    printed = " ".join(str(a) for a in mock_print.call_args[0])
                    assert "Error processing entry point failing-plugin" in printed

    @pytest.mark.asyncio
    async def test_compatible_entry_point_plugin(self):
        """Test discovery of compatible entry point plugin (line 127)."""
        discovery = AsyncPluginDiscovery()

        # Mock compatible entry point plugin
        mock_module = Mock()
        mock_module.PLUGIN_METADATA = {
            "name": "compatible-plugin",
            "version": "1.0.0",
            "plugin_type": "sink",
            "entry_point": "compatible_plugin",
            "description": "Compatible plugin",
            "author": "Test",
            "compatibility": {"min_fapilog_version": "3.0.0a1"},  # Compatible
        }

        mock_entry_point = Mock()
        mock_entry_point.name = "compatible-plugin"
        mock_entry_point.load.return_value = mock_module

        await discovery._process_entry_point(mock_entry_point)

        # Verify plugin was discovered as compatible (covers line 127)
        assert "compatible-plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["compatible-plugin"]
        assert plugin_info.load_error is None
        assert plugin_info.source == "entry_point"

    @pytest.mark.asyncio
    async def test_per_group_entry_point_mapping(self):
        """Discovery maps entry point groups to plugin_type and loads both."""
        discovery = AsyncPluginDiscovery()

        # Modules without explicit plugin_type → should be derived from group
        class SinkModule:
            PLUGIN_METADATA = {
                "name": "sink-a",
                "version": "1.0.0",
                "entry_point": "sink_a",
                "description": "sink",
                "author": "t",
                "compatibility": {"min_fapilog_version": "3.0.0"},
            }

        class ProcessorModule:
            PLUGIN_METADATA = {
                "name": "proc-a",
                "version": "1.0.0",
                "entry_point": "proc_a",
                "description": "proc",
                "author": "t",
                "compatibility": {"min_fapilog_version": "3.0.0"},
            }

        class EP:
            def __init__(self, name: str, module) -> None:
                self.name = name
                self._module = module

            def load(self):
                return self._module

        class Eps:
            def __init__(self, mapping: dict[str, list]) -> None:
                self.mapping = mapping

            def select(self, *, group: str):
                return self.mapping.get(group, [])

        eps = Eps(
            {
                "fapilog.sinks": [EP("sink-a", SinkModule)],
                "fapilog.processors": [EP("proc-a", ProcessorModule)],
            }
        )

        with patch("importlib.metadata.entry_points", return_value=eps), patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=True,
        ):
            plugins = await discovery.discover_all_plugins()

        assert "sink-a" in plugins and plugins["sink-a"].metadata.plugin_type == "sink"
        assert (
            "proc-a" in plugins
            and plugins["proc-a"].metadata.plugin_type == "processor"
        )

    @pytest.mark.asyncio
    async def test_contradictory_plugin_type_error(self):
        """Contradictory plugin_type vs group produces actionable error."""
        discovery = AsyncPluginDiscovery()

        class BadSinkModule:
            PLUGIN_METADATA = {
                "name": "bad-sink",
                "version": "1.0.0",
                "plugin_type": "processor",  # contradicts sink group
                "entry_point": "bad",
                "description": "bad",
                "author": "t",
                "compatibility": {"min_fapilog_version": "3.0.0"},
            }

        class EP:
            def __init__(self, name: str, module) -> None:
                self.name = name
                self._module = module

            def load(self):
                return self._module

        class Eps:
            def __init__(self, mapping: dict[str, list]) -> None:
                self.mapping = mapping

            def select(self, *, group: str):
                return self.mapping.get(group, [])

        eps = Eps({"fapilog.sinks": [EP("bad-sink", BadSinkModule)]})

        with patch("importlib.metadata.entry_points", return_value=eps), patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=True,
        ):
            await discovery.discover_all_plugins()

        assert "bad-sink" in discovery._discovered_plugins
        info = discovery._discovered_plugins["bad-sink"]
        assert info.load_error and "Contradictory plugin_type" in info.load_error

    @pytest.mark.asyncio
    async def test_duplicate_name_collision_across_groups(self):
        """Duplicate plugin names across groups produce collision error."""
        discovery = AsyncPluginDiscovery()

        class M1:
            PLUGIN_METADATA = {
                "name": "dup",
                "version": "1.0.0",
                "entry_point": "dup1",
                "description": "",
                "author": "t",
                "compatibility": {"min_fapilog_version": "3.0.0"},
            }

        class M2:
            PLUGIN_METADATA = {
                "name": "dup",
                "version": "1.0.0",
                "entry_point": "dup2",
                "description": "",
                "author": "t",
                "compatibility": {"min_fapilog_version": "3.0.0"},
            }

        class EP:
            def __init__(self, name: str, module) -> None:
                self.name = name
                self._module = module

            def load(self):
                return self._module

        class Eps:
            def __init__(self, mapping: dict[str, list]) -> None:
                self.mapping = mapping

            def select(self, *, group: str):
                return self.mapping.get(group, [])

        eps = Eps(
            {
                "fapilog.sinks": [EP("dup", M1)],
                "fapilog.processors": [EP("dup", M2)],
            }
        )

        with patch("importlib.metadata.entry_points", return_value=eps), patch(
            "fapilog.plugins.discovery.validate_fapilog_compatibility",
            return_value=True,
        ):
            await discovery.discover_all_plugins()

        assert "dup" in discovery._discovered_plugins
        collision = discovery._discovered_plugins["dup"]
        assert collision.load_error and "Duplicate plugin name" in collision.load_error

    @pytest.mark.asyncio
    async def test_private_file_skipping(self, tmp_path):
        """Test skipping of private files during discovery (line 171)."""
        discovery = AsyncPluginDiscovery()
        discovery.add_discovery_path(tmp_path)

        # Create a private file (starts with underscore)
        private_plugin = tmp_path / "_private_plugin.py"
        private_content = """
PLUGIN_METADATA = {
    "name": "private-plugin",
    "version": "1.0.0",
    "plugin_type": "sink"
}
"""
        private_plugin.write_text(private_content)

        # Create a normal file
        normal_plugin = tmp_path / "normal_plugin.py"
        normal_content = """
PLUGIN_METADATA = {
    "name": "normal-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "normal_plugin.py",
    "description": "Normal plugin",
    "author": "Test",
    "compatibility": {"min_fapilog_version": "3.0.0a1"}
}
"""
        normal_plugin.write_text(normal_content)

        await discovery._discover_local_plugins()

        # Verify private file was skipped, normal file was processed
        # Plugins are indexed by metadata name, not filename
        assert "_private_plugin" not in discovery._discovered_plugins
        assert "normal-plugin" in discovery._discovered_plugins

    @pytest.mark.asyncio
    async def test_directory_scan_exception_handling(self, tmp_path):
        """Test directory scanning exception handling (lines 175-176)."""
        discovery = AsyncPluginDiscovery()

        # Mock the _process_local_plugin_file to raise an exception
        with patch.object(
            discovery,
            "_process_local_plugin_file",
            new=AsyncMock(side_effect=RuntimeError("Scan error")),
        ):
            # Create a plugin file to trigger the scanning
            plugin_file = tmp_path / "test_plugin.py"
            plugin_file.write_text("# test content")

            # This should trigger the exception handling in _scan_directory_for_plugins
            with pytest.raises(PluginDiscoveryError, match="Failed to scan directory"):
                await discovery._scan_directory_for_plugins(tmp_path)

    @pytest.mark.asyncio
    async def test_path_already_in_sys_path(self, tmp_path):
        """Test scenario where path is already in sys.path (line 192)."""
        discovery = AsyncPluginDiscovery()

        plugin_file = tmp_path / "test_plugin.py"
        plugin_content = """
PLUGIN_METADATA = {
    "name": "test-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "test_plugin.py",
    "description": "Test plugin",
    "author": "Test",
    "compatibility": {"min_fapilog_version": "3.0.0a1"}
}
"""
        plugin_file.write_text(plugin_content)

        # Add the path to sys.path first
        import sys

        parent_dir = str(tmp_path)
        sys.path.insert(0, parent_dir)

        try:
            await discovery._process_local_plugin_file(plugin_file)

            # Verify plugin was processed (covers line 192 path_added = False)
            # Plugins are indexed by metadata name, not filename
            assert "test-plugin" in discovery._discovered_plugins

        finally:
            # Clean up
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)

    @pytest.mark.asyncio
    async def test_incompatible_local_plugin(self, tmp_path):
        """Test discovery of incompatible local plugin (line 209)."""
        discovery = AsyncPluginDiscovery()

        plugin_file = tmp_path / "incompatible_plugin.py"
        plugin_content = """
PLUGIN_METADATA = {
    "name": "incompatible-plugin",
    "version": "1.0.0",
    "plugin_type": "sink",
    "entry_point": "incompatible_plugin.py",
    "description": "Incompatible plugin",
    "author": "Test",
    "compatibility": {"min_fapilog_version": "99.0.0"}  # Way too high
}
"""
        plugin_file.write_text(plugin_content)

        await discovery._process_local_plugin_file(plugin_file)

        # Verify plugin was discovered but marked as incompatible (covers line 209)
        # Plugins are indexed by metadata name, not filename
        assert "incompatible-plugin" in discovery._discovered_plugins
        plugin_info = discovery._discovered_plugins["incompatible-plugin"]
        assert plugin_info.load_error == "Incompatible with current Fapilog version"
        assert plugin_info.source == "local"

    @pytest.mark.asyncio
    async def test_global_discovery_instance_singleton(self):
        """Test global discovery instance and convenience functions (lines 311-325)."""
        # Clear the global instance first
        import fapilog.plugins.discovery as discovery_module
        from fapilog.plugins.discovery import (
            discover_plugins,
            discover_plugins_by_type,
            get_discovery_instance,
        )

        discovery_module._discovery_instance = None

        # Test singleton behavior (covers lines 311-313)
        instance1 = await get_discovery_instance()
        instance2 = await get_discovery_instance()
        assert instance1 is instance2

        # Test convenience functions (covers lines 318-319, 324-325)
        with patch.object(
            instance1, "discover_all_plugins", new=AsyncMock(return_value={})
        ) as _:
            await discover_plugins()

        with patch.object(
            instance1, "discover_plugins_by_type", new=AsyncMock(return_value={})
        ) as _:
            await discover_plugins_by_type("sink")


class TestMemoryAndPerformance:
    """Test memory management and performance characteristics."""

    async def test_memory_leak_prevention(self):
        """Test that the registry doesn't leak memory with repeated operations."""
        # This is a basic test - in practice you'd use memory profiling tools
        async with create_container() as container:
            for i in range(10):
                registry = await create_component_registry(container, f"container-{i}")
                await registry.cleanup()

        # If we get here without issues, basic memory management works

    async def test_concurrent_access(self):
        """Test thread-safe concurrent access to registry."""
        async with create_container() as container:
            registry = await create_component_registry(container)

            # Simulate concurrent operations
            async def concurrent_operation(operation_id: int):
                await registry.discover_plugins()
                return operation_id

            # Run multiple concurrent operations
            tasks = [concurrent_operation(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            await registry.cleanup()

    async def test_large_number_of_plugins(self):
        """Test performance with a larger number of mock plugins."""
        # Create a temporary directory with multiple plugins
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir)

            # Create multiple test plugins
            for i in range(10):
                plugin_file = plugin_dir / f"test_plugin_{i}.py"
                plugin_content = f"""
PLUGIN_METADATA = {{
    "name": "test-plugin-{i}",
    "version": "1.0.0",
    "description": "Test plugin {i}",
    "author": "Test Author",
    "plugin_type": "sink",
    "entry_point": "{plugin_file}",
    "compatibility": {{
        "min_fapilog_version": "3.0.0a1"
    }}
}}

class Plugin:
    def __init__(self):
        self.name = "test-plugin-{i}"
"""
                plugin_file.write_text(plugin_content)

            async with create_container() as container:
                registry = await create_component_registry(container)
                registry.add_discovery_path(plugin_dir)

                # Discover all plugins
                plugins = await registry.discover_plugins()
                assert len(plugins) == 10

                # Load all plugins
                for i in range(10):
                    await registry.load_plugin(f"test-plugin-{i}")

                assert registry.loaded_plugin_count == 10
                await registry.cleanup()


# Integration Tests


@pytest.mark.asyncio
class TestIntegration:
    """Test integration between all plugin system components."""

    @pytest.fixture
    def complex_plugin_dir(self):
        """Create a directory with multiple types of plugins."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_dir = Path(temp_dir)

            # Sink plugin
            sink_plugin = plugin_dir / "file_sink.py"
            sink_content = f"""
PLUGIN_METADATA = {{
    "name": "file-sink",
    "version": "1.0.0",
    "description": "File output sink",
    "author": "Test Author",
    "plugin_type": "sink",
    "entry_point": "{sink_plugin}",
    "compatibility": {{
        "min_fapilog_version": "3.0.0a1"
    }}
}}

class Plugin:
    def __init__(self):
        self.name = "file-sink"
        self.logs = []

    async def write_log(self, log_entry):
        self.logs.append(log_entry)
"""

            # Processor plugin
            processor_plugin = plugin_dir / "json_processor.py"
            processor_content = f"""
PLUGIN_METADATA = {{
    "name": "json-processor",
    "version": "1.0.0",
    "description": "JSON log processor",
    "author": "Test Author",
    "plugin_type": "processor",
    "entry_point": "{processor_plugin}",
    "compatibility": {{
        "min_fapilog_version": "3.0.0a1"
    }}
}}

class Plugin:
    def __init__(self):
        self.name = "json-processor"

    async def process_log(self, log_entry):
        return {{"processed": True, "original": log_entry}}
"""

            sink_plugin.write_text(sink_content)
            processor_plugin.write_text(processor_content)
            yield plugin_dir

    async def test_full_plugin_lifecycle(self, complex_plugin_dir):
        """Test the complete plugin lifecycle with multiple plugin types."""
        async with create_container() as container:
            registry = await create_component_registry(container)
            registry.add_discovery_path(complex_plugin_dir)

            # Discover all plugins
            plugins = await registry.discover_plugins()
            assert "file-sink" in plugins
            assert "json-processor" in plugins

            # Test discovery by type
            sinks = await registry.discover_plugins("sink")
            processors = await registry.discover_plugins("processor")

            assert "file-sink" in sinks
            assert "json-processor" in processors
            assert "file-sink" not in processors
            assert "json-processor" not in sinks

            # Load plugins
            sink_plugin = await registry.load_plugin("file-sink")
            processor_plugin = await registry.load_plugin("json-processor")

            assert sink_plugin.name == "file-sink"
            assert processor_plugin.name == "json-processor"

            # Test plugin functionality
            test_log = {"message": "test log", "level": "info"}
            processed_log = await processor_plugin.process_log(test_log)
            await sink_plugin.write_log(processed_log)

            assert len(sink_plugin.logs) == 1
            assert sink_plugin.logs[0]["processed"] is True

            # Test type-safe retrieval
            sink = await registry.get_plugin("file-sink", object)
            assert sink is sink_plugin

            # Cleanup
            await registry.cleanup()

    async def test_container_integration(self, complex_plugin_dir):
        """Test integration with the async container."""
        async with create_container() as container:
            registry = await create_component_registry(container)
            registry.add_discovery_path(complex_plugin_dir)

            # Load a plugin
            await registry.load_plugin("file-sink")

            # Plugin should be registered with container under isolated name
            assert registry.loaded_plugin_count == 1

            # Test cleanup through registry
            await registry.cleanup()
            assert registry.loaded_plugin_count == 0

    async def test_error_handling_and_recovery(self, complex_plugin_dir):
        """Test error handling and recovery scenarios."""
        async with create_container() as container:
            registry = await create_component_registry(container)
            registry.add_discovery_path(complex_plugin_dir)

            # Test loading non-existent plugin
            with pytest.raises(PluginRegistryError):
                await registry.load_plugin("non-existent-plugin")

            # Successful operations should still work after errors
            sink_plugin = await registry.load_plugin("file-sink")
            assert sink_plugin is not None

            await registry.cleanup()


if __name__ == "__main__":
    pytest.main([__file__])
