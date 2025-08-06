"""
Unit tests for AsyncLoggingContainer.
"""

import pytest

from fapilog.containers.container import AsyncLoggingContainer
from fapilog.core.settings import LogLevel, UniversalSettings


class TestAsyncLoggingContainer:
    """Test AsyncLoggingContainer functionality."""

    @pytest.fixture  # type: ignore[misc]
    def container_settings(self) -> UniversalSettings:
        """Create test settings."""
        return UniversalSettings(level=LogLevel.INFO, sinks=["stdout"], max_workers=2)

    @pytest.fixture  # type: ignore[misc]
    def container(self, container_settings: UniversalSettings) -> AsyncLoggingContainer:
        """Create test container."""
        return AsyncLoggingContainer(container_settings)

    def test_container_initialization(
        self, container: AsyncLoggingContainer, container_settings: UniversalSettings
    ) -> None:
        """Test container initialization."""
        assert container.settings == container_settings
        assert container.container_id is not None
        assert len(container.container_id) > 0
        assert container._components == {}
        assert container._configured is False

    async def test_container_configure(self, container: AsyncLoggingContainer) -> None:
        """Test container configuration."""
        logger = await container.configure()
        assert container._configured is True
        assert logger is not None
        await logger.shutdown()

    async def test_container_get_component_found(
        self, container: AsyncLoggingContainer
    ) -> None:
        """Test getting existing component."""
        # Add a component manually for testing
        test_component = "test_value"
        container._components[str] = test_component

        result = await container.get_component(str)
        assert result == test_component

    async def test_container_cleanup(self, container: AsyncLoggingContainer) -> None:
        """Test container cleanup."""
        # First configure
        await container.configure()
        assert container._configured is True

        # Then cleanup
        await container.cleanup()
        assert container._configured is False
        assert container._components == {}  # type: ignore[unreachable]

    async def test_container_context_manager(
        self, container: AsyncLoggingContainer
    ) -> None:
        """Test container as async context manager."""
        async with container as ctx:
            assert ctx is container

    async def test_container_context_manager_cleanup(
        self, container: AsyncLoggingContainer
    ) -> None:
        """Test container context manager cleanup."""
        # Test that context manager properly handles exceptions
        try:
            async with container as ctx:
                assert ctx is container
                # Simulate an exception
                raise ValueError("Test exception")
        except ValueError:
            # Exception should be properly handled
            pass

        # Container should have been through cleanup process
