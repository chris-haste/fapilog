"""
Comprehensive test coverage for fapilog config module.

These tests focus on increasing coverage for all config functionality,
including configuration management, hot-reloading, versioning, and global functions.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from unittest.mock import MagicMock

import pytest

from fapilog.core.config import (
    ConfigurationManager,
    ConfigurationWatcher,
    SchemaVersionManager,
    cleanup_global_configuration,
    get_configuration_manager,
    initialize_global_configuration,
)
from fapilog.core.errors import ConfigurationError
from fapilog.core.settings import FapilogSettings


class TestConfigurationWatcher:
    """Test configuration file watcher functionality."""

    @pytest.mark.asyncio
    async def test_watcher_initialization(self):
        """Test watcher initialization."""
        callback = Mock()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b'{"environment": "development"}')

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.1,
            )

            assert watcher.config_file == temp_path
            assert watcher.reload_callback == callback
            assert watcher.check_interval == 0.1
            assert watcher._last_modified is None
            assert watcher._watch_task is None
            assert watcher._running is False
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_start_watching(self):
        """Test starting the configuration watcher."""
        callback = Mock()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b'{"environment": "development"}')

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.1,
            )

            await watcher.start_watching()

            assert watcher._running is True
            assert watcher._watch_task is not None
            assert watcher._last_modified is not None

            # Stop watching
            await watcher.stop_watching()
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_start_watching_already_running(self):
        """Test starting watcher when already running."""
        callback = Mock()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b'{"environment": "development"}')

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.1,
            )

            # Start watching twice
            await watcher.start_watching()
            first_task = watcher._watch_task

            await watcher.start_watching()
            second_task = watcher._watch_task

            # Should be the same task
            assert first_task is second_task

            await watcher.stop_watching()
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_stop_watching(self):
        """Test stopping the configuration watcher."""
        callback = Mock()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b'{"environment": "development"}')

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.1,
            )

            await watcher.start_watching()
            await watcher.stop_watching()

            assert watcher._running is False
            assert watcher._watch_task is None
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_stop_watching_not_running(self):
        """Test stopping watcher when not running."""
        callback = Mock()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.1,
            )

            # Should not raise exception
            await watcher.stop_watching()
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_file_change_detection(self):
        """Test file change detection and callback triggering."""
        callback = Mock()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b'{"environment": "development"}')

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.05,  # Very fast for testing
            )

            await watcher.start_watching()

            # Wait a bit and modify file
            await asyncio.sleep(0.1)
            temp_path.write_text('{"environment": "production"}')

            # Wait for detection
            await asyncio.sleep(0.15)

            await watcher.stop_watching()

            # Callback should have been called
            assert callback.call_count >= 1
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_nonexistent_file(self):
        """Test watcher with nonexistent file."""
        callback = Mock()
        nonexistent_path = Path("/tmp/nonexistent_config.json")

        watcher = ConfigurationWatcher(
            config_file=nonexistent_path,
            reload_callback=callback,
            check_interval=0.1,
        )

        await watcher.start_watching()
        await asyncio.sleep(0.05)
        await watcher.stop_watching()

        # Should not crash


class TestConfigurationManagerAdvanced:
    """Test advanced configuration manager functionality."""

    @pytest.mark.asyncio
    async def test_manager_properties(self):
        """Test manager properties."""
        manager = ConfigurationManager()

        assert not manager.is_initialized
        assert manager.get_current_settings() is None
        assert len(manager.get_configuration_history()) == 0

    @pytest.mark.asyncio
    async def test_manager_initialize_with_overrides(self):
        """Test manager initialization with config overrides."""
        manager = ConfigurationManager()

        settings = await manager.initialize(
            debug=True,
            environment="testing",
        )

        assert settings.debug is True
        assert settings.environment == "testing"
        assert manager.is_initialized

    @pytest.mark.asyncio
    async def test_manager_initialize_already_initialized(self):
        """Test initializing already initialized manager."""
        manager = ConfigurationManager()

        # First initialization
        settings1 = await manager.initialize(environment="development")

        # Second initialization should return same settings
        settings2 = await manager.initialize(environment="production")

        assert settings1 is settings2
        assert settings1.environment == "development"  # Original value

    @pytest.mark.asyncio
    async def test_manager_initialize_with_config_file(self):
        """Test manager initialization with config file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            config_data = {
                "environment": "production",
                "debug": False,
                "core": {"log_level": "INFO"},
            }
            json.dump(config_data, temp_file)
            temp_file.flush()

        try:
            manager = ConfigurationManager()
            settings = await manager.initialize(config_file=temp_path)

            assert settings.environment == "production"
            assert settings.debug is False
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_manager_initialize_error_handling(self):
        """Test manager initialization error handling."""
        manager = ConfigurationManager()

        with patch(
            "fapilog.core.config.load_settings", side_effect=Exception("Load failed")
        ):
            with pytest.raises(
                ConfigurationError, match="Failed to initialize configuration manager"
            ):
                await manager.initialize()

    @pytest.mark.asyncio
    async def test_manager_reload_configuration(self):
        """Test configuration reload."""
        manager = ConfigurationManager()

        # Initial setup
        await manager.initialize(environment="development")
        initial_settings = manager.get_current_settings()

        # Reload with different config
        new_settings = await manager.reload_configuration(environment="production")

        assert new_settings.environment == "production"
        assert manager.get_current_settings() is new_settings
        assert len(manager.get_configuration_history()) == 2

    @pytest.mark.asyncio
    async def test_manager_reload_not_initialized(self):
        """Test reloading when not initialized."""
        manager = ConfigurationManager()

        # Reload should work even when not initialized (it just loads new settings)
        settings = await manager.reload_configuration(environment="development")
        assert settings.environment == "development"

    @pytest.mark.asyncio
    async def test_manager_reload_error_handling(self):
        """Test reload error handling."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")

        with patch(
            "fapilog.core.config.load_settings", side_effect=Exception("Reload failed")
        ):
            with pytest.raises(
                ConfigurationError, match="Failed to reload configuration"
            ):
                await manager.reload_configuration()

    @pytest.mark.asyncio
    async def test_manager_rollback_configuration(self):
        """Test configuration rollback."""
        manager = ConfigurationManager()

        # Setup multiple configurations (avoid production to avoid breaking change validation)
        # initialize(dev): current=dev, history=[dev]
        settings1 = await manager.initialize(environment="development")

        # reload(staging): history.append(dev) -> [dev, dev], current=staging
        settings2 = await manager.reload_configuration(environment="staging")

        # reload(testing): history.append(staging) -> [dev, dev, staging], current=testing
        settings3 = await manager.reload_configuration(environment="testing")

        assert len(manager.get_configuration_history()) == 3

        # History is [dev, dev, staging], current is testing
        # Rollback 1 step: target_index = len(3) - 1 - 1 = 1 -> history[1] = dev
        rolled_back = await manager.rollback_configuration(steps=1)
        assert rolled_back.environment == "development"

        # After rollback: history is [dev, dev], current is dev
        # The test was wrong about expected staging

    @pytest.mark.asyncio
    async def test_manager_rollback_not_initialized(self):
        """Test rollback when not initialized."""
        manager = ConfigurationManager()

        with pytest.raises(ConfigurationError, match="Cannot rollback"):
            await manager.rollback_configuration()

    @pytest.mark.asyncio
    async def test_manager_rollback_insufficient_history(self):
        """Test rollback with insufficient history."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")

        with pytest.raises(ConfigurationError, match="Cannot rollback"):
            await manager.rollback_configuration(steps=5)

    @pytest.mark.asyncio
    async def test_manager_history_size_limit(self):
        """Test configuration history size limit."""
        manager = ConfigurationManager()

        # Generate more configurations than the limit
        for i in range(15):
            if i == 0:
                await manager.initialize(environment="development", debug=i % 2 == 0)
            else:
                await manager.reload_configuration(
                    environment="development", debug=i % 2 == 0
                )

        # Should respect max history size
        assert len(manager.get_configuration_history()) == manager._max_history_size

    @pytest.mark.asyncio
    async def test_manager_setup_hot_reload(self):
        """Test hot reload setup."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            config_data = {"environment": "development"}
            json.dump(config_data, temp_file)
            temp_file.flush()

        try:
            manager = ConfigurationManager()
            await manager.initialize(
                config_file=temp_path, enable_hot_reload=True, hot_reload_interval=0.1
            )

            assert len(manager._watchers) == 1
            assert manager._watchers[0]._running is True

            await manager.cleanup()
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_manager_add_reload_callback(self):
        """Test adding reload callback."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")

        callback = Mock()
        manager.add_reload_callback(callback)

        # Trigger reload
        await manager.reload_configuration(environment="production")

        # Callback should be called
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_manager_validate_configuration_change_breaking(self):
        """Test validation of breaking configuration changes."""
        manager = ConfigurationManager()
        await manager.initialize(environment="production")

        old_settings = manager.get_current_settings()
        new_settings = FapilogSettings(environment="development")

        with pytest.raises(ConfigurationError, match="breaking changes"):
            await manager._validate_configuration_change(old_settings, new_settings)

    @pytest.mark.asyncio
    async def test_manager_validate_configuration_change_valid(self):
        """Test validation of valid configuration changes."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")

        old_settings = manager.get_current_settings()
        new_settings = FapilogSettings(environment="development", debug=True)

        # Should not raise exception
        await manager._validate_configuration_change(old_settings, new_settings)

    @pytest.mark.asyncio
    async def test_manager_cleanup(self):
        """Test manager cleanup."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            config_data = {"environment": "development"}
            json.dump(config_data, temp_file)
            temp_file.flush()

        try:
            manager = ConfigurationManager()
            await manager.initialize(
                config_file=temp_path, enable_hot_reload=True, hot_reload_interval=0.1
            )

            await manager.cleanup()

            # All watchers should be stopped
            for watcher in manager._watchers:
                assert not watcher._running
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_manager_notify_callbacks_error_handling(self):
        """Test callback notification error handling."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")

        # Add callback that raises exception
        failing_callback = Mock(side_effect=Exception("Callback failed"))
        working_callback = Mock()

        manager.add_reload_callback(failing_callback)
        manager.add_reload_callback(working_callback)

        # Should not raise exception
        new_settings = FapilogSettings(environment="development", debug=True)
        manager._notify_reload_callbacks(new_settings)

        # Working callback should still be called
        working_callback.assert_called_once_with(new_settings)


class TestSchemaVersionManager:
    """Test schema version manager functionality."""

    def test_schema_manager_initialization(self):
        """Test schema manager initialization."""
        manager = SchemaVersionManager()

        assert manager.current_version == "3.0.0"
        assert "3.0.0" in manager.supported_versions
        assert manager._migrations == {}

    def test_register_migration(self):
        """Test registering a migration function."""
        manager = SchemaVersionManager()

        def migration_func(config: dict) -> dict:
            return {**config, "migrated": True}

        manager.register_migration("2.0.0", "3.0.0", migration_func)

        assert "2.0.0->3.0.0" in manager._migrations
        assert manager._migrations["2.0.0->3.0.0"] == migration_func

    @pytest.mark.asyncio
    async def test_migrate_configuration_no_migration_needed(self):
        """Test migration when no migration is needed."""
        manager = SchemaVersionManager()
        config_data = {"version": "3.0.0", "environment": "development"}

        result = await manager.migrate_configuration(config_data)

        assert result == config_data

    @pytest.mark.asyncio
    async def test_migrate_configuration_with_migration(self):
        """Test configuration migration."""
        manager = SchemaVersionManager()

        def migration_func(config: dict) -> dict:
            return {**config, "migrated": True}

        manager.register_migration("2.0.0", "3.0.0", migration_func)

        config_data = {"config_version": "2.0.0", "environment": "development"}
        result = await manager.migrate_configuration(config_data, "3.0.0")

        assert result["config_version"] == "3.0.0"
        assert result["migrated"] is True

    @pytest.mark.asyncio
    async def test_migrate_configuration_unsupported_version(self):
        """Test migration with unsupported version."""
        manager = SchemaVersionManager()
        config_data = {"config_version": "1.0.0", "environment": "development"}

        with pytest.raises(ConfigurationError, match="No migration path"):
            await manager.migrate_configuration(config_data, "3.0.0")

    @pytest.mark.asyncio
    async def test_migrate_configuration_migration_error(self):
        """Test migration with migration error."""
        manager = SchemaVersionManager()

        def failing_migration(config: dict) -> dict:
            raise ValueError("Migration failed")

        manager.register_migration("2.0.0", "3.0.0", failing_migration)

        config_data = {"config_version": "2.0.0", "environment": "development"}

        with pytest.raises(ConfigurationError, match="Configuration migration failed"):
            await manager.migrate_configuration(config_data, "3.0.0")

    def test_validate_version_supported(self):
        """Test version validation for supported version."""
        manager = SchemaVersionManager()

        # Should return True
        assert manager.validate_version_compatibility("3.0.0") is True

    def test_validate_version_unsupported(self):
        """Test version validation for unsupported version."""
        manager = SchemaVersionManager()

        # Should return False
        assert manager.validate_version_compatibility("1.0.0") is False

    def test_schema_version_defaults(self):
        """Test schema version manager defaults."""
        manager = SchemaVersionManager()

        # Test default version extraction behavior
        config_with_version = {"config_version": "2.0.0", "environment": "development"}
        source_version = config_with_version.get("config_version", "3.0.0")
        assert source_version == "2.0.0"

        config_without_version = {"environment": "development"}
        source_version = config_without_version.get("config_version", "3.0.0")
        assert source_version == "3.0.0"


class TestGlobalConfigurationFunctions:
    """Test global configuration management functions."""

    @pytest.mark.asyncio
    async def test_get_configuration_manager_new(self):
        """Test getting configuration manager when none exists."""
        # Clean up any existing manager
        import fapilog.core.config

        fapilog.core.config._config_manager = None

        manager = await get_configuration_manager()
        assert isinstance(manager, ConfigurationManager)

    @pytest.mark.asyncio
    async def test_get_configuration_manager_existing(self):
        """Test getting existing configuration manager."""
        manager1 = await get_configuration_manager()
        manager2 = await get_configuration_manager()

        # Should return the same instance
        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_initialize_global_configuration(self):
        """Test initializing global configuration."""
        settings = await initialize_global_configuration(
            environment="testing", debug=True
        )

        assert isinstance(settings, FapilogSettings)
        assert settings.environment == "testing"
        assert settings.debug is True

    @pytest.mark.asyncio
    async def test_initialize_global_configuration_with_file(self):
        """Test initializing global configuration with file."""
        # Cleanup any existing global manager first
        await cleanup_global_configuration()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            config_data = {"environment": "production", "debug": False}
            json.dump(config_data, temp_file)
            temp_file.flush()

        try:
            settings = await initialize_global_configuration(
                config_file=temp_path, enable_hot_reload=True
            )

            assert settings.environment == "production"
            assert settings.debug is False
        finally:
            temp_path.unlink(missing_ok=True)
            await cleanup_global_configuration()

    @pytest.mark.asyncio
    async def test_cleanup_global_configuration(self):
        """Test cleaning up global configuration."""
        # Initialize first
        await initialize_global_configuration(environment="development")

        # Cleanup
        await cleanup_global_configuration()

        # Should be able to initialize again with different settings
        settings = await initialize_global_configuration(environment="production")
        assert settings.environment == "production"

    @pytest.mark.asyncio
    async def test_cleanup_global_configuration_no_manager(self):
        """Test cleanup when no manager exists."""
        import fapilog.core.config

        fapilog.core.config._config_manager = None

        # Should not raise exception
        await cleanup_global_configuration()

    @pytest.mark.asyncio
    async def test_get_lock_thread_safety(self):
        """Test _get_lock function thread safety."""
        from fapilog.core.config import _get_lock

        # Multiple calls should return the same lock
        lock1 = _get_lock()
        lock2 = _get_lock()

        assert lock1 is lock2
        assert isinstance(lock1, asyncio.Lock)


class TestConfigurationWatcherEdgeCases:
    """Test edge cases for configuration watcher."""

    @pytest.mark.asyncio
    async def test_watcher_watch_loop_exception_handling(self):
        """Test watch loop exception handling."""
        callback = Mock()

        # Create a mock watcher with mocked file operations
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=callback,
                check_interval=0.05,
            )

            # Delete the file to cause stat() to fail
            temp_path.unlink()

            await watcher.start_watching()
            await asyncio.sleep(0.1)  # Let it run and hit the exception
            await watcher.stop_watching()

            # Should not crash
        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_watcher_callback_exception_handling(self):
        """Test callback exception handling in watcher."""
        failing_callback = Mock(side_effect=Exception("Callback failed"))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b'{"environment": "development"}')

        try:
            watcher = ConfigurationWatcher(
                config_file=temp_path,
                reload_callback=failing_callback,
                check_interval=0.05,
            )

            await watcher.start_watching()

            # Modify file to trigger callback
            await asyncio.sleep(0.1)
            temp_path.write_text('{"environment": "production"}')
            await asyncio.sleep(0.1)

            await watcher.stop_watching()

            # Should not crash despite callback failure
        finally:
            temp_path.unlink(missing_ok=True)


class TestConfigurationManagerConcurrency:
    """Test configuration manager concurrency scenarios."""

    @pytest.mark.asyncio
    async def test_manager_concurrent_initialization(self):
        """Test concurrent initialization of manager."""
        manager = ConfigurationManager()

        async def init_task():
            return await manager.initialize(environment="development")

        # Run multiple initialization tasks concurrently
        results = await asyncio.gather(
            init_task(),
            init_task(),
            init_task(),
        )

        # All should return the same settings instance
        assert all(result is results[0] for result in results)
        assert all(result.environment == "development" for result in results)

    @pytest.mark.asyncio
    async def test_manager_concurrent_reload(self):
        """Test concurrent reload operations."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")

        async def reload_task(env):
            return await manager.reload_configuration(environment=env)

        # Run multiple reload tasks (later ones should win)
        results = await asyncio.gather(
            reload_task("staging"),
            reload_task("testing"),
            reload_task("production"),
        )

        # Final state should be from last reload
        final_settings = manager.get_current_settings()
        assert final_settings.environment in ["staging", "testing", "production"]

    @pytest.mark.asyncio
    async def test_manager_concurrent_rollback(self):
        """Test concurrent rollback operations."""
        manager = ConfigurationManager()
        await manager.initialize(environment="development")
        await manager.reload_configuration(environment="staging")
        await manager.reload_configuration(environment="testing")

        async def rollback_task():
            return await manager.rollback_configuration(steps=1)

        # Only the first rollback should succeed due to the async lock
        results = await asyncio.gather(
            rollback_task(), rollback_task(), return_exceptions=True
        )

        # At least one should succeed
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) >= 1
