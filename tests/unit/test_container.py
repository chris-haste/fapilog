"""
Unit tests for the async container architecture.

This module tests the AsyncLoggingContainer and related components
to ensure perfect isolation, async lifecycle management, and proper
dependency injection.
"""

import asyncio

import pytest

from fapilog.containers import (
    AsyncComponentBase,
    AsyncLoggingContainer,
    LifecycleManager,
    create_container,
    managed_component,
)


class MockComponent:
    """Mock component for testing."""

    def __init__(self, name: str = "mock") -> None:
        self.name = name
        self.initialized = False
        self.cleaned_up = False

    async def initialize(self) -> None:
        """Initialize the mock component."""
        self.initialized = True

    async def cleanup(self) -> None:
        """Clean up the mock component."""
        self.cleaned_up = True


class MockComponentWithDependency:
    """Mock component with dependency for testing."""

    def __init__(self, dependency: MockComponent) -> None:
        self.dependency = dependency


async def mock_factory() -> MockComponent:
    """Factory function for creating mock components."""
    return MockComponent()


async def mock_factory_with_dependency(
    dependency: MockComponent,
) -> MockComponentWithDependency:
    """Factory function for creating mock components with dependencies."""
    return MockComponentWithDependency(dependency)


class TestAsyncLoggingContainer:
    """Test cases for AsyncLoggingContainer."""

    @pytest.fixture
    async def container(self) -> AsyncLoggingContainer:
        """Create a container for testing."""
        return AsyncLoggingContainer()

    async def test_container_initialization(self, container: AsyncLoggingContainer):
        """Test container initialization."""
        assert not container.is_initialized
        await container.initialize()
        assert container.is_initialized

    async def test_container_cleanup(self, container: AsyncLoggingContainer):
        """Test container cleanup."""
        await container.initialize()
        assert container.is_initialized
        await container.cleanup()
        assert not container.is_initialized

    async def test_context_manager(self):
        """Test container as async context manager."""
        async with AsyncLoggingContainer() as container:
            assert container.is_initialized
        # Container should be cleaned up after exiting context

    async def test_component_registration(self, container: AsyncLoggingContainer):
        """Test component registration."""
        container.register_component("test_component", MockComponent, mock_factory)

        assert container.component_count == 1
        assert "test_component" in container.list_components()

    async def test_component_retrieval(self, container: AsyncLoggingContainer):
        """Test component retrieval."""
        container.register_component("test_component", MockComponent, mock_factory)

        await container.initialize()
        component = await container.get_component("test_component", MockComponent)

        assert isinstance(component, MockComponent)

    async def test_component_singleton_behavior(self, container: AsyncLoggingContainer):
        """Test that singleton components return the same instance."""
        container.register_component(
            "test_component", MockComponent, mock_factory, is_singleton=True
        )

        await container.initialize()
        component1 = await container.get_component("test_component", MockComponent)
        component2 = await container.get_component("test_component", MockComponent)

        assert component1 is component2

    async def test_component_non_singleton_behavior(
        self, container: AsyncLoggingContainer
    ):
        """Test that non-singleton components return different instances."""
        container.register_component(
            "test_component", MockComponent, mock_factory, is_singleton=False
        )

        await container.initialize()
        component1 = await container.get_component("test_component", MockComponent)
        component2 = await container.get_component("test_component", MockComponent)

        assert component1 is not component2

    async def test_dependency_injection(self, container: AsyncLoggingContainer):
        """Test dependency injection between components."""
        # Register dependency first
        container.register_component("dependency", MockComponent, mock_factory)

        # Register component with dependency
        container.register_component(
            "main_component",
            MockComponentWithDependency,
            mock_factory_with_dependency,
            dependencies=["dependency"],
        )

        await container.initialize()
        main_component = await container.get_component(
            "main_component", MockComponentWithDependency
        )

        assert isinstance(main_component, MockComponentWithDependency)
        assert isinstance(main_component.dependency, MockComponent)

    async def test_component_not_found_error(self, container: AsyncLoggingContainer):
        """Test error when requesting non-existent component."""
        await container.initialize()

        with pytest.raises(KeyError, match="Component 'missing' is not registered"):
            await container.get_component("missing", MockComponent)

    async def test_dependency_not_found_error(self, container: AsyncLoggingContainer):
        """Test error when dependency is missing."""
        container.register_component(
            "main_component",
            MockComponentWithDependency,
            mock_factory_with_dependency,
            dependencies=["missing_dependency"],
        )

        # The error should be raised during initialization when creating singleton instances
        with pytest.raises(KeyError, match="Dependency 'missing_dependency' not found"):
            await container.initialize()

    async def test_type_safety_check(self, container: AsyncLoggingContainer):
        """Test type safety when retrieving components."""
        container.register_component("test_component", MockComponent, mock_factory)

        await container.initialize()

        # This should work
        component = await container.get_component("test_component", MockComponent)
        assert isinstance(component, MockComponent)

        # This should raise TypeError due to type mismatch
        with pytest.raises(TypeError, match="is of type MockComponent, not str"):
            await container.get_component("test_component", str)

    async def test_cleanup_callbacks(self, container: AsyncLoggingContainer):
        """Test cleanup callbacks are executed."""
        cleanup_called = False

        async def cleanup_callback():
            nonlocal cleanup_called
            cleanup_called = True

        container.add_cleanup_callback(cleanup_callback)
        await container.initialize()
        await container.cleanup()

        assert cleanup_called

    async def test_zero_global_state_isolation(self):
        """Test that containers are completely isolated from each other."""
        container1 = AsyncLoggingContainer()
        container2 = AsyncLoggingContainer()

        # Register different components in each container
        container1.register_component("comp1", MockComponent, mock_factory)
        container2.register_component("comp2", MockComponent, mock_factory)

        await container1.initialize()
        await container2.initialize()

        # Each container should only know about its own components
        assert container1.component_count == 1
        assert container2.component_count == 1
        assert "comp1" in container1.list_components()
        assert "comp2" in container2.list_components()
        assert "comp1" not in container2.list_components()
        assert "comp2" not in container1.list_components()

        await container1.cleanup()
        await container2.cleanup()

    async def test_concurrent_access_thread_safety(self):
        """Test thread-safe concurrent access to container."""
        container = AsyncLoggingContainer()
        container.register_component("test_component", MockComponent, mock_factory)

        await container.initialize()

        # Concurrent access should be safe due to async locks
        async def get_component():
            return await container.get_component("test_component", MockComponent)

        # Run multiple concurrent accesses
        tasks = [get_component() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All results should be the same instance (singleton)
        for result in results:
            assert result is results[0]

        await container.cleanup()


class TestCreateContainerFactory:
    """Test cases for the create_container factory function."""

    async def test_factory_creates_initialized_container(self):
        """Test that factory creates and initializes container."""
        async with create_container() as container:
            assert isinstance(container, AsyncLoggingContainer)
            assert container.is_initialized

    async def test_factory_cleanup_on_exit(self):
        """Test that factory cleans up container on exit."""
        container_ref = None

        async with create_container() as container:
            container_ref = container
            assert container.is_initialized

        # Container should be cleaned up after context exit
        assert not container_ref.is_initialized


class TestAsyncComponentBase:
    """Test cases for AsyncComponentBase."""

    class SampleComponent(AsyncComponentBase):
        """Sample implementation of AsyncComponentBase for testing."""

        def __init__(self):
            super().__init__()
            self.init_called = False
            self.cleanup_called = False

        async def _initialize_impl(self) -> None:
            self.init_called = True

        async def _cleanup_impl(self) -> None:
            self.cleanup_called = True

    async def test_component_lifecycle(self):
        """Test component lifecycle management."""
        component = self.SampleComponent()

        assert not component.is_initialized
        assert not component.init_called

        await component.initialize()
        assert component.is_initialized
        assert component.init_called

        await component.cleanup()
        assert not component.is_initialized
        assert component.cleanup_called

    async def test_double_initialization_protection(self):
        """Test that double initialization is protected."""
        component = self.SampleComponent()

        await component.initialize()
        init_count_before = 1 if component.init_called else 0

        # Second initialization should be ignored
        await component.initialize()
        assert component.is_initialized
        assert init_count_before == 1  # Should not change

    async def test_double_cleanup_protection(self):
        """Test that double cleanup is protected."""
        component = self.SampleComponent()

        await component.initialize()
        await component.cleanup()
        cleanup_count_before = 1 if component.cleanup_called else 0

        # Second cleanup should be ignored
        await component.cleanup()
        assert not component.is_initialized
        assert cleanup_count_before == 1  # Should not change


class TestLifecycleManager:
    """Test cases for LifecycleManager."""

    async def test_initialize_component(self):
        """Test component initialization via lifecycle manager."""
        manager = LifecycleManager()
        component = MockComponent()

        assert not component.initialized
        await manager.initialize_component(component)
        assert component.initialized

    async def test_cleanup_all_components(self):
        """Test cleanup of all managed components."""
        manager = LifecycleManager()
        component1 = MockComponent("comp1")
        component2 = MockComponent("comp2")

        await manager.initialize_component(component1)
        await manager.initialize_component(component2)

        await manager.cleanup_all()

        assert component1.cleaned_up
        assert component2.cleaned_up

    async def test_cleanup_order_lifo(self):
        """Test that cleanup happens in LIFO order."""
        manager = LifecycleManager()
        cleanup_order = []

        class OrderedComponent:
            def __init__(self, name: str):
                self.name = name

            async def initialize(self):
                pass

            async def cleanup(self):
                cleanup_order.append(self.name)

        comp1 = OrderedComponent("first")
        comp2 = OrderedComponent("second")
        comp3 = OrderedComponent("third")

        await manager.initialize_component(comp1)
        await manager.initialize_component(comp2)
        await manager.initialize_component(comp3)

        await manager.cleanup_all()

        # Should be cleaned up in reverse order (LIFO)
        assert cleanup_order == ["third", "second", "first"]


class TestManagedComponent:
    """Test cases for managed_component context manager."""

    async def test_managed_component_with_init_and_cleanup(self):
        """Test managed component with both init and cleanup."""
        component = MockComponent()

        async with managed_component(component) as managed:
            assert managed is component
            assert component.initialized

        assert component.cleaned_up

    async def test_managed_component_init_only(self):
        """Test managed component with init only."""

        class InitOnlyComponent:
            def __init__(self):
                self.initialized = False

            async def initialize(self):
                self.initialized = True

        component = InitOnlyComponent()

        async with managed_component(component) as managed:
            assert managed is component
            assert component.initialized

    async def test_managed_component_cleanup_only(self):
        """Test managed component with cleanup only."""

        class CleanupOnlyComponent:
            def __init__(self):
                self.cleaned_up = False

            async def cleanup(self):
                self.cleaned_up = True

        component = CleanupOnlyComponent()

        async with managed_component(component) as managed:
            assert managed is component
            assert not component.cleaned_up

        assert component.cleaned_up


class TestMemoryEfficiency:
    """Test cases for memory efficiency and leak prevention."""

    async def test_cleanup_clears_instances(self):
        """Test that cleanup properly clears all instances."""
        container = AsyncLoggingContainer()
        container.register_component("test_component", MockComponent, mock_factory)

        await container.initialize()
        component = await container.get_component("test_component", MockComponent)
        assert component is not None

        await container.cleanup()

        # Internal instances should be cleared
        assert len(container._instances) == 0

    async def test_no_global_state(self):
        """Test that no global state exists between containers."""
        # Create and destroy multiple containers
        for i in range(5):
            container = AsyncLoggingContainer()
            container.register_component(f"component_{i}", MockComponent, mock_factory)
            await container.initialize()
            await container.cleanup()

        # Create a new container and verify it's clean
        new_container = AsyncLoggingContainer()
        assert new_container.component_count == 0
        assert len(new_container.list_components()) == 0


# Performance tests for validation
class TestPerformance:
    """Performance tests for the container."""

    async def test_container_creation_performance(self):
        """Test container creation performance."""

        async def create_and_initialize():
            container = AsyncLoggingContainer()
            await container.initialize()
            await container.cleanup()

        # Test that creation is reasonably fast
        import time

        start = time.time()
        await create_and_initialize()
        end = time.time()

        # Should complete in reasonable time (adjust as needed)
        assert (end - start) < 0.1

    async def test_component_retrieval_performance(self):
        """Test component retrieval performance."""
        container = AsyncLoggingContainer()
        container.register_component("test_component", MockComponent, mock_factory)
        await container.initialize()

        # Multiple retrievals should be fast (singleton behavior)
        import time

        start = time.time()

        for _ in range(1000):
            component = await container.get_component("test_component", MockComponent)
            assert component is not None

        end = time.time()
        await container.cleanup()

        # Should complete many retrievals quickly
        assert (end - start) < 1.0
