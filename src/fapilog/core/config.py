"""
Configuration Loading and Management for Fapilog v3.

This module provides advanced configuration loading, hot-reloading,
and integration with the async container system.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union
from weakref import WeakSet

from .errors import ConfigurationError
from .settings import FapilogSettings, load_settings


class ConfigurationWatcher:
    """
    Configuration file watcher for hot-reloading capabilities.

    Monitors configuration files for changes and triggers reloads
    when modifications are detected.
    """

    def __init__(
        self,
        config_file: Union[str, Path],
        reload_callback: Callable[[FapilogSettings], None],
        check_interval: float = 1.0,
    ) -> None:
        """
        Initialize configuration watcher.

        Args:
            config_file: Configuration file to watch
            reload_callback: Callback to execute on configuration reload
            check_interval: How often to check for changes (seconds)
        """
        self.config_file = Path(config_file)
        self.reload_callback = reload_callback
        self.check_interval = check_interval
        self._last_modified: Optional[float] = None
        self._watch_task: Optional[asyncio.Task[None]] = None
        self._running = False

    async def start_watching(self) -> None:
        """Start watching the configuration file for changes."""
        if self._running:
            return

        self._running = True

        # Get initial modification time
        if self.config_file.exists():
            self._last_modified = self.config_file.stat().st_mtime

        # Start watching task
        self._watch_task = asyncio.create_task(self._watch_loop())

    async def stop_watching(self) -> None:
        """Stop watching the configuration file."""
        self._running = False

        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None

    async def _watch_loop(self) -> None:
        """Main watching loop."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                if not self.config_file.exists():
                    continue

                current_modified = self.config_file.stat().st_mtime

                if (
                    self._last_modified is not None
                    and current_modified > self._last_modified
                ):
                    # File was modified, trigger reload
                    try:
                        new_settings = await load_settings(self.config_file)
                        self.reload_callback(new_settings)
                        self._last_modified = current_modified
                    except Exception:
                        # Log error but continue watching
                        pass

                self._last_modified = current_modified

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue watching
                pass


class ConfigurationManager:
    """
    Advanced configuration manager with hot-reloading and validation.

    Provides:
    - Configuration loading with validation
    - Hot-reloading capabilities
    - Configuration versioning and rollback
    - Integration with container lifecycle
    """

    def __init__(self) -> None:
        """Initialize configuration manager."""
        self._current_settings: Optional[FapilogSettings] = None
        self._config_history: list[FapilogSettings] = []
        self._max_history_size = 10
        self._watchers: list[ConfigurationWatcher] = []
        self._reload_callbacks: WeakSet[Callable[[FapilogSettings], None]] = WeakSet()
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(
        self,
        config_file: Optional[Union[str, Path]] = None,
        enable_hot_reload: bool = False,
        hot_reload_interval: float = 1.0,
        **config_overrides: Any,
    ) -> FapilogSettings:
        """
        Initialize configuration manager with settings.

        Args:
            config_file: Optional configuration file path
            enable_hot_reload: Enable hot-reloading of configuration
            hot_reload_interval: Hot-reload check interval (seconds)
            **config_overrides: Configuration overrides

        Returns:
            Loaded FapilogSettings instance

        Raises:
            ConfigurationError: If initialization fails
        """
        async with self._lock:
            if self._initialized:
                # _current_settings is set when _initialized is True
                assert self._current_settings is not None
                return self._current_settings

            try:
                # Load initial configuration
                settings = await load_settings(config_file, **config_overrides)

                # Store configuration
                self._current_settings = settings
                self._config_history.append(settings)

                # Setup hot-reloading if requested
                if enable_hot_reload and config_file:
                    await self._setup_hot_reload(config_file, hot_reload_interval)

                self._initialized = True
                return settings

            except Exception as e:
                raise ConfigurationError(
                    f"Failed to initialize configuration manager: {e}",
                    cause=e,
                ) from e

    async def reload_configuration(
        self,
        config_file: Optional[Union[str, Path]] = None,
        **config_overrides: Any,
    ) -> FapilogSettings:
        """
        Reload configuration with new settings.

        Args:
            config_file: Optional configuration file path
            **config_overrides: Configuration overrides

        Returns:
            New FapilogSettings instance

        Raises:
            ConfigurationError: If reload fails
        """
        async with self._lock:
            try:
                # Load new configuration
                new_settings = await load_settings(config_file, **config_overrides)

                # Validate new configuration
                await self._validate_configuration_change(
                    self._current_settings, new_settings
                )

                # Store old configuration in history
                if self._current_settings:
                    self._config_history.append(self._current_settings)

                    # Limit history size
                    if len(self._config_history) > self._max_history_size:
                        self._config_history.pop(0)

                # Update current configuration
                self._current_settings = new_settings

                # Notify callbacks
                self._notify_reload_callbacks(new_settings)

                return new_settings

            except Exception as e:
                raise ConfigurationError(
                    f"Failed to reload configuration: {e}",
                    cause=e,
                ) from e

    async def rollback_configuration(self, steps: int = 1) -> Optional[FapilogSettings]:
        """
        Rollback configuration to a previous version.

        Args:
            steps: Number of steps to rollback

        Returns:
            Rolled back FapilogSettings instance or None if no history

        Raises:
            ConfigurationError: If rollback fails
        """
        async with self._lock:
            if len(self._config_history) < steps + 1:
                raise ConfigurationError(
                    f"Cannot rollback {steps} steps, only {len(self._config_history) - 1} versions available"
                )

            try:
                # Get target configuration
                target_index = len(self._config_history) - steps - 1
                target_settings = self._config_history[target_index]

                # Validate rollback
                await self._validate_configuration_change(
                    self._current_settings, target_settings
                )

                # Perform rollback
                self._current_settings = target_settings

                # Remove rolled back configurations from history
                self._config_history = self._config_history[: target_index + 1]

                # Notify callbacks
                self._notify_reload_callbacks(target_settings)

                return target_settings

            except Exception as e:
                raise ConfigurationError(
                    f"Failed to rollback configuration: {e}",
                    cause=e,
                ) from e

    def add_reload_callback(self, callback: Callable[[FapilogSettings], None]) -> None:
        """
        Add a callback to be notified on configuration reload.

        Args:
            callback: Function to call with new settings
        """
        self._reload_callbacks.add(callback)

    def get_current_settings(self) -> Optional[FapilogSettings]:
        """Get current configuration settings."""
        return self._current_settings

    def get_configuration_history(self) -> list[FapilogSettings]:
        """Get configuration history."""
        return self._config_history.copy()

    async def cleanup(self) -> None:
        """Clean up configuration manager resources."""
        async with self._lock:
            # Stop all watchers
            for watcher in self._watchers:
                await watcher.stop_watching()

            self._watchers.clear()
            self._reload_callbacks.clear()
            self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if configuration manager is initialized."""
        return self._initialized

    async def _setup_hot_reload(
        self, config_file: Union[str, Path], interval: float
    ) -> None:
        """Setup hot-reloading for configuration file."""
        watcher = ConfigurationWatcher(
            config_file=config_file,
            reload_callback=self._handle_hot_reload,
            check_interval=interval,
        )

        self._watchers.append(watcher)
        await watcher.start_watching()

    def _handle_hot_reload(self, new_settings: FapilogSettings) -> None:
        """Handle hot-reload callback."""
        asyncio.create_task(self._process_hot_reload(new_settings))

    async def _process_hot_reload(self, new_settings: FapilogSettings) -> None:
        """Process hot-reload asynchronously."""
        try:
            async with self._lock:
                # Validate configuration change
                await self._validate_configuration_change(
                    self._current_settings, new_settings
                )

                # Store old configuration
                if self._current_settings:
                    self._config_history.append(self._current_settings)

                    if len(self._config_history) > self._max_history_size:
                        self._config_history.pop(0)

                # Update current configuration
                self._current_settings = new_settings

                # Notify callbacks
                self._notify_reload_callbacks(new_settings)

        except Exception:
            # Log error but don't crash
            pass

    async def _validate_configuration_change(
        self,
        old_settings: Optional[FapilogSettings],
        new_settings: FapilogSettings,
    ) -> None:
        """Validate that configuration change is safe."""
        if old_settings is None:
            return

        # Check for breaking changes
        breaking_changes = []

        # Environment changes in production
        if (
            old_settings.environment == "production"
            and new_settings.environment != "production"
        ):
            breaking_changes.append(
                "Cannot change environment from production to non-production"
            )

        # Security downgrades
        if (
            old_settings.security.encryption_enabled
            and not new_settings.security.encryption_enabled
        ):
            breaking_changes.append("Cannot disable encryption after it was enabled")

        # Compliance downgrades
        if (
            old_settings.compliance.compliance_enabled
            and not new_settings.compliance.compliance_enabled
        ):
            breaking_changes.append("Cannot disable compliance after it was enabled")

        if breaking_changes:
            raise ConfigurationError(
                f"Configuration change contains breaking changes: {'; '.join(breaking_changes)}"
            )

    def _notify_reload_callbacks(self, new_settings: FapilogSettings) -> None:
        """Notify all reload callbacks."""
        for callback in self._reload_callbacks:
            try:
                callback(new_settings)
            except Exception:
                # Log error but continue with other callbacks
                pass


class SchemaVersionManager:
    """
    Configuration schema versioning and migration manager.

    Handles schema versioning, migration between versions,
    and backward compatibility validation.
    """

    def __init__(self) -> None:
        """Initialize schema version manager."""
        self.current_version = "3.0.0"
        self.supported_versions = ["3.0.0"]
        self._migrations: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register_migration(
        self,
        from_version: str,
        to_version: str,
        migration_func: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        """
        Register a configuration migration function.

        Args:
            from_version: Source version
            to_version: Target version
            migration_func: Migration function
        """
        key = f"{from_version}->{to_version}"
        self._migrations[key] = migration_func

    async def migrate_configuration(
        self, config_data: Dict[str, Any], target_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Migrate configuration data to target version.

        Args:
            config_data: Configuration data to migrate
            target_version: Target version (current if not specified)

        Returns:
            Migrated configuration data

        Raises:
            ConfigurationError: If migration fails
        """
        if target_version is None:
            target_version = self.current_version

        source_version = config_data.get("config_version", "3.0.0")

        if source_version == target_version:
            return config_data

        # Find migration path
        migration_key = f"{source_version}->{target_version}"

        if migration_key not in self._migrations:
            raise ConfigurationError(
                f"No migration path from {source_version} to {target_version}"
            )

        try:
            migration_func = self._migrations[migration_key]
            migrated_data = migration_func(config_data.copy())
            migrated_data["config_version"] = target_version
            return migrated_data

        except Exception as e:
            raise ConfigurationError(
                f"Configuration migration failed: {e}",
                cause=e,
            ) from e

    def validate_version_compatibility(self, version: str) -> bool:
        """
        Validate if a configuration version is supported.

        Args:
            version: Configuration version to validate

        Returns:
            True if version is supported
        """
        return version in self.supported_versions


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None
_config_manager_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    """Get or create the configuration manager lock."""
    global _config_manager_lock
    if _config_manager_lock is None:
        _config_manager_lock = asyncio.Lock()
    return _config_manager_lock


async def get_configuration_manager() -> ConfigurationManager:
    """
    Get global configuration manager instance.

    Returns:
        ConfigurationManager instance
    """
    global _config_manager

    if _config_manager is None:
        lock = _get_lock()
        async with lock:
            if _config_manager is None:
                _config_manager = ConfigurationManager()

    return _config_manager


async def initialize_global_configuration(
    config_file: Optional[Union[str, Path]] = None,
    enable_hot_reload: bool = False,
    **config_overrides: Any,
) -> FapilogSettings:
    """
    Initialize global configuration manager.

    Args:
        config_file: Optional configuration file path
        enable_hot_reload: Enable hot-reloading
        **config_overrides: Configuration overrides

    Returns:
        Loaded FapilogSettings instance
    """
    manager = await get_configuration_manager()
    return await manager.initialize(
        config_file=config_file,
        enable_hot_reload=enable_hot_reload,
        **config_overrides,
    )


async def cleanup_global_configuration() -> None:
    """Clean up global configuration manager."""
    global _config_manager

    if _config_manager:
        lock = _get_lock()
        async with lock:
            if _config_manager:
                await _config_manager.cleanup()
                _config_manager = None
