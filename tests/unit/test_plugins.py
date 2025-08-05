"""
Unit tests for plugin system.
"""

from unittest.mock import AsyncMock

import pytest

from fapilog.core.settings import UniversalSettings
from fapilog.plugins.marketplace import PluginInfo, PluginMarketplace
from fapilog.plugins.registry import PluginRegistry


class TestPluginInfo:
    """Test PluginInfo class."""

    def test_plugin_info_creation(self) -> None:
        """Test PluginInfo creation."""
        info = PluginInfo("test-plugin", "1.0.0", "A test plugin")

        assert info.name == "test-plugin"
        assert info.version == "1.0.0"
        assert info.description == "A test plugin"


class TestPluginMarketplace:
    """Test PluginMarketplace functionality."""

    @pytest.fixture  # type: ignore[misc]
    def marketplace_settings(self) -> UniversalSettings:
        """Create test settings."""
        return UniversalSettings(plugins_enabled=True, plugin_marketplace=True)

    @pytest.fixture  # type: ignore[misc]
    def marketplace(self, marketplace_settings: UniversalSettings) -> PluginMarketplace:
        """Create test marketplace."""
        return PluginMarketplace(marketplace_settings)

    def test_marketplace_initialization(
        self, marketplace: PluginMarketplace, marketplace_settings: UniversalSettings
    ) -> None:
        """Test marketplace initialization."""
        assert marketplace.settings == marketplace_settings
        assert marketplace._available_plugins == {}
        assert marketplace._installed_plugins == {}
        assert marketplace._lock is not None

    async def test_search_plugins(self, marketplace: PluginMarketplace) -> None:
        """Test plugin search functionality."""
        results = await marketplace.search_plugins("test")
        assert results == []  # Currently returns empty list

    async def test_install_plugin_success(self, marketplace: PluginMarketplace) -> None:
        """Test successful plugin installation."""
        result = await marketplace.install_plugin("test-plugin", "1.0.0")
        assert result is True

    async def test_install_plugin_without_version(
        self, marketplace: PluginMarketplace
    ) -> None:
        """Test plugin installation without specific version."""
        result = await marketplace.install_plugin("test-plugin")
        assert result is True

    async def test_update_plugin(self, marketplace: PluginMarketplace) -> None:
        """Test plugin update functionality."""
        result = await marketplace.update_plugin("test-plugin")
        assert result is True

    async def test_uninstall_plugin_success(
        self, marketplace: PluginMarketplace
    ) -> None:
        """Test successful plugin uninstallation."""
        # First install a plugin
        marketplace._installed_plugins["test-plugin"] = "1.0.0"

        result = await marketplace.uninstall_plugin("test-plugin")
        assert result is True
        assert "test-plugin" not in marketplace._installed_plugins

    async def test_uninstall_plugin_not_found(
        self, marketplace: PluginMarketplace
    ) -> None:
        """Test uninstalling non-existent plugin."""
        result = await marketplace.uninstall_plugin("nonexistent-plugin")
        assert result is False

    async def test_list_installed_plugins_empty(
        self, marketplace: PluginMarketplace
    ) -> None:
        """Test listing installed plugins when none are installed."""
        installed = await marketplace.list_installed_plugins()
        assert installed == {}

    async def test_list_installed_plugins_with_plugins(
        self, marketplace: PluginMarketplace
    ) -> None:
        """Test listing installed plugins."""
        # Add some plugins
        marketplace._installed_plugins["plugin1"] = "1.0.0"
        marketplace._installed_plugins["plugin2"] = "2.0.0"

        installed = await marketplace.list_installed_plugins()
        expected = {"plugin1": "1.0.0", "plugin2": "2.0.0"}
        assert installed == expected

    async def test_get_plugin_info_found(self, marketplace: PluginMarketplace) -> None:
        """Test getting plugin info when plugin exists."""
        # Add a plugin to available plugins
        plugin_info = PluginInfo("test-plugin", "1.0.0", "Test description")
        marketplace._available_plugins["test-plugin"] = plugin_info

        result = await marketplace.get_plugin_info("test-plugin")
        assert result == plugin_info

    async def test_get_plugin_info_not_found(
        self, marketplace: PluginMarketplace
    ) -> None:
        """Test getting plugin info when plugin doesn't exist."""
        result = await marketplace.get_plugin_info("nonexistent-plugin")
        assert result is None

    async def test_refresh_marketplace(self, marketplace: PluginMarketplace) -> None:
        """Test marketplace refresh functionality."""
        # Currently just passes, so we test it doesn't raise
        await marketplace.refresh_marketplace()


class MockSinkPlugin:
    """Mock sink plugin for testing."""

    async def write(self, events: list) -> None:
        """Mock write method."""
        pass

    async def initialize(self, config: dict) -> None:
        """Mock initialize method."""
        pass

    async def cleanup(self) -> None:
        """Mock cleanup method."""
        pass


class MockProcessorPlugin:
    """Mock processor plugin for testing."""

    async def process(self, events: list) -> list:
        """Mock process method."""
        return events

    async def initialize(self, config: dict) -> None:
        """Mock initialize method."""
        pass

    async def cleanup(self) -> None:
        """Mock cleanup method."""
        pass


class MockEnricherPlugin:
    """Mock enricher plugin for testing."""

    async def enrich(self, event: dict) -> dict:
        """Mock enrich method."""
        return event

    async def initialize(self, config: dict) -> None:
        """Mock initialize method."""
        pass

    async def cleanup(self) -> None:
        """Mock cleanup method."""
        pass


class TestPluginRegistry:
    """Test PluginRegistry functionality."""

    @pytest.fixture  # type: ignore[misc]
    def registry_settings(self) -> UniversalSettings:
        """Create test settings."""
        return UniversalSettings(plugins_enabled=True, plugin_auto_discovery=True)

    @pytest.fixture  # type: ignore[misc]
    def registry(self, registry_settings: UniversalSettings) -> PluginRegistry:
        """Create test registry."""
        return PluginRegistry(registry_settings)

    def test_registry_initialization(
        self, registry: PluginRegistry, registry_settings: UniversalSettings
    ) -> None:
        """Test registry initialization."""
        assert registry.settings == registry_settings
        assert registry._sink_plugins == {}
        assert registry._processor_plugins == {}
        assert registry._enricher_plugins == {}
        assert registry._lock is not None

    async def test_register_sink_plugin(self, registry: PluginRegistry) -> None:
        """Test registering a sink plugin."""
        plugin = MockSinkPlugin()
        await registry.register_sink_plugin("test-sink", plugin)

        assert "test-sink" in registry._sink_plugins
        assert registry._sink_plugins["test-sink"] == plugin

    async def test_register_processor_plugin(self, registry: PluginRegistry) -> None:
        """Test registering a processor plugin."""
        plugin = MockProcessorPlugin()
        await registry.register_processor_plugin("test-processor", plugin)

        assert "test-processor" in registry._processor_plugins
        assert registry._processor_plugins["test-processor"] == plugin

    async def test_register_enricher_plugin(self, registry: PluginRegistry) -> None:
        """Test registering an enricher plugin."""
        plugin = MockEnricherPlugin()
        await registry.register_enricher_plugin("test-enricher", plugin)

        assert "test-enricher" in registry._enricher_plugins
        assert registry._enricher_plugins["test-enricher"] == plugin

    async def test_get_sink_plugin_found(self, registry: PluginRegistry) -> None:
        """Test getting an existing sink plugin."""
        plugin = MockSinkPlugin()
        await registry.register_sink_plugin("test-sink", plugin)

        result = await registry.get_sink_plugin("test-sink")
        assert result == plugin

    async def test_get_sink_plugin_not_found(self, registry: PluginRegistry) -> None:
        """Test getting a non-existent sink plugin."""
        result = await registry.get_sink_plugin("nonexistent")
        assert result is None

    async def test_get_processor_plugin_found(self, registry: PluginRegistry) -> None:
        """Test getting an existing processor plugin."""
        plugin = MockProcessorPlugin()
        await registry.register_processor_plugin("test-processor", plugin)

        result = await registry.get_processor_plugin("test-processor")
        assert result == plugin

    async def test_get_processor_plugin_not_found(
        self, registry: PluginRegistry
    ) -> None:
        """Test getting a non-existent processor plugin."""
        result = await registry.get_processor_plugin("nonexistent")
        assert result is None

    async def test_get_enricher_plugin_found(self, registry: PluginRegistry) -> None:
        """Test getting an existing enricher plugin."""
        plugin = MockEnricherPlugin()
        await registry.register_enricher_plugin("test-enricher", plugin)

        result = await registry.get_enricher_plugin("test-enricher")
        assert result == plugin

    async def test_get_enricher_plugin_not_found(
        self, registry: PluginRegistry
    ) -> None:
        """Test getting a non-existent enricher plugin."""
        result = await registry.get_enricher_plugin("nonexistent")
        assert result is None

    async def test_list_sink_plugins_empty(self, registry: PluginRegistry) -> None:
        """Test listing sink plugins when none are registered."""
        plugins = await registry.list_sink_plugins()
        assert plugins == []

    async def test_list_sink_plugins_with_plugins(
        self, registry: PluginRegistry
    ) -> None:
        """Test listing sink plugins."""
        plugin1 = MockSinkPlugin()
        plugin2 = MockSinkPlugin()
        await registry.register_sink_plugin("sink1", plugin1)
        await registry.register_sink_plugin("sink2", plugin2)

        plugins = await registry.list_sink_plugins()
        assert set(plugins) == {"sink1", "sink2"}

    async def test_list_processor_plugins(self, registry: PluginRegistry) -> None:
        """Test listing processor plugins."""
        plugin = MockProcessorPlugin()
        await registry.register_processor_plugin("processor1", plugin)

        plugins = await registry.list_processor_plugins()
        assert plugins == ["processor1"]

    async def test_list_enricher_plugins(self, registry: PluginRegistry) -> None:
        """Test listing enricher plugins."""
        plugin = MockEnricherPlugin()
        await registry.register_enricher_plugin("enricher1", plugin)

        plugins = await registry.list_enricher_plugins()
        assert plugins == ["enricher1"]

    async def test_cleanup_plugins(self, registry: PluginRegistry) -> None:
        """Test cleaning up all plugins."""
        from unittest.mock import patch

        # Register plugins
        sink_plugin = MockSinkPlugin()
        processor_plugin = MockProcessorPlugin()
        enricher_plugin = MockEnricherPlugin()

        await registry.register_sink_plugin("sink1", sink_plugin)
        await registry.register_processor_plugin("processor1", processor_plugin)
        await registry.register_enricher_plugin("enricher1", enricher_plugin)

        # Mock the cleanup methods using patch
        with patch.object(
            sink_plugin, "cleanup", new_callable=AsyncMock
        ) as mock_sink_cleanup, patch.object(
            processor_plugin, "cleanup", new_callable=AsyncMock
        ) as mock_processor_cleanup, patch.object(
            enricher_plugin, "cleanup", new_callable=AsyncMock
        ) as mock_enricher_cleanup:
            # Cleanup
            await registry.cleanup()

            # Verify cleanup was called on all plugins
            mock_sink_cleanup.assert_called_once()
            mock_processor_cleanup.assert_called_once()
            mock_enricher_cleanup.assert_called_once()

        # Verify all plugins were cleared
        assert registry._sink_plugins == {}
        assert registry._processor_plugins == {}
        assert registry._enricher_plugins == {}
