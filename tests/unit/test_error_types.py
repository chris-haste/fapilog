"""
Tests for error types and context management.

Scope:
- Standardized error types with context preservation
- Error context management across async operations
- ExecutionContext properties and methods
- Context variable lookup and management
"""

import pytest

from fapilog.core import (
    ComponentError,
    ContainerError,
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    FapilogError,
    NetworkError,
    PluginError,
    execution_context,
    get_current_error_context,
)


class TestErrorTypes:
    """Test standardized error types with context preservation."""

    @pytest.mark.asyncio
    async def test_fapilog_error_basic_creation(self):
        """Test basic FapilogError creation with context."""
        error = FapilogError(
            "Test error message",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
        )

        assert error.message == "Test error message"
        assert error.context.category == ErrorCategory.SYSTEM
        assert error.context.severity == ErrorSeverity.HIGH
        assert (
            isinstance(error.context.error_id, str)
            and len(error.context.error_id) == 36
        )
        assert error.context.timestamp is not None and hasattr(
            error.context.timestamp, "isoformat"
        )

    @pytest.mark.asyncio
    async def test_error_context_preservation(self):
        """Test error context preservation in async operations."""
        async with execution_context(
            request_id="test-req-123",
            user_id="test-user",
            operation_name="test_operation",
        ):
            # Create error within context
            error = FapilogError("Test error")

            # Check that context was captured
            assert error.context.request_id == "test-req-123"
            assert error.context.user_id == "test-user"

    @pytest.mark.asyncio
    async def test_specific_error_types(self):
        """Test specific error type creation and categorization."""
        # Container error
        container_error = ContainerError("Container failed")
        assert container_error.context.category == ErrorCategory.CONTAINER
        assert container_error.context.severity == ErrorSeverity.HIGH

        # Plugin error
        plugin_error = PluginError("Plugin failed", plugin_name="test-plugin")
        assert plugin_error.context.category == ErrorCategory.PLUGIN_EXEC
        assert plugin_error.context.plugin_name == "test-plugin"

        # Network error
        network_error = NetworkError("Network connection failed")
        assert network_error.context.category == ErrorCategory.NETWORK
        assert network_error.context.recovery_strategy == ErrorRecoveryStrategy.RETRY

    @pytest.mark.asyncio
    async def test_error_chaining(self):
        """Test error chaining and cause preservation."""
        original_error = ValueError("Original error")

        fapilog_error = FapilogError(
            "Wrapped error", cause=original_error, category=ErrorCategory.VALIDATION
        )

        assert fapilog_error.__cause__ == original_error
        assert fapilog_error.context.category == ErrorCategory.VALIDATION

    async def test_error_serialization(self):
        """Test error serialization for logging and persistence."""
        error = FapilogError(
            "Test error",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            component_name="test-component",
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "FapilogError"
        assert error_dict["message"] == "Test error"
        assert "context" in error_dict
        assert error_dict["context"]["category"] == "system"
        assert error_dict["context"]["severity"] == "critical"


class TestContextManagement:
    """Test error context preservation across async operations."""

    @pytest.mark.asyncio
    async def test_execution_context_creation(self):
        """Test creation and management of execution contexts."""
        async with execution_context(
            request_id="test-123",
            user_id="user-456",
            operation_name="test_operation",
            custom_field="custom_value",
        ) as ctx:
            assert ctx.request_id == "test-123"
            assert ctx.user_id == "user-456"
            assert ctx.operation_name == "test_operation"
            assert ctx.metadata["custom_field"] == "custom_value"
            assert isinstance(ctx.execution_id, str) and len(ctx.execution_id) == 36
            assert not ctx.is_completed

        # Context should be completed after exiting
        assert ctx.is_completed
        assert isinstance(ctx.duration, float) and ctx.duration >= 0

    @pytest.mark.asyncio
    async def test_nested_context_hierarchy(self):
        """Test nested execution contexts and hierarchy tracking."""
        async with execution_context(operation_name="parent_operation") as parent_ctx:
            parent_id = parent_ctx.execution_id

            async with execution_context(operation_name="child_operation") as child_ctx:
                assert child_ctx.parent_execution_id == parent_id

    @pytest.mark.asyncio
    async def test_error_context_integration(self):
        """Test integration between execution context and error context."""
        async with execution_context(
            request_id="req-123", component_name="test-component"
        ):
            error_context = await get_current_error_context(
                ErrorCategory.SYSTEM, ErrorSeverity.HIGH
            )

            assert error_context.request_id == "req-123"
            assert error_context.component_name == "test-component"
            assert error_context.category == ErrorCategory.SYSTEM
            assert error_context.severity == ErrorSeverity.HIGH

    @pytest.mark.asyncio
    async def test_context_error_tracking(self):
        """Test error tracking within execution contexts."""
        async with execution_context(operation_name="error_test") as ctx:
            # Simulate adding errors to context
            error1 = ValueError("First error")
            error2 = RuntimeError("Second error")

            ctx.add_error(error1)
            ctx.add_error(error2)

            assert len(ctx.error_chain) == 2
            assert ctx.error_chain[0]["error_type"] == "ValueError"
            assert ctx.error_chain[1]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_execution_context_properties(self):
        """Test ExecutionContext properties and methods."""
        from fapilog.core.context import ExecutionContext

        # Test basic properties
        ctx = ExecutionContext(
            request_id="test-req",
            user_id="test-user",
            session_id="test-session",
            container_id="test-container",
            component_name="test-component",
            operation_name="test-operation",
        )

        assert isinstance(ctx.execution_id, str) and len(ctx.execution_id) == 36
        assert ctx.request_id == "test-req"
        assert ctx.user_id == "test-user"
        assert ctx.session_id == "test-session"
        assert ctx.container_id == "test-container"
        assert ctx.component_name == "test-component"
        assert ctx.operation_name == "test-operation"
        assert not ctx.is_completed
        assert ctx.duration is None

        # Test completion
        ctx.complete()
        assert ctx.is_completed
        assert isinstance(ctx.duration, float) and ctx.duration >= 0

    @pytest.mark.asyncio
    async def test_execution_context_error_handling(self):
        """Test ExecutionContext error handling methods."""
        from fapilog.core.context import ExecutionContext

        ctx = ExecutionContext()

        # Test adding regular exception
        error = ValueError("Test error")
        ctx.add_error(error)

        assert len(ctx.error_chain) == 1
        error_info = ctx.error_chain[0]
        assert error_info["error_type"] == "ValueError"
        assert error_info["error_message"] == "Test error"
        assert error_info["execution_id"] == ctx.execution_id

        # Test adding FapilogError
        fapilog_error = ComponentError("Component failed", component_name="test-comp")
        ctx.add_error(fapilog_error)

        assert len(ctx.error_chain) == 2
        error_info = ctx.error_chain[1]
        assert error_info["error_type"] == "ComponentError"
        assert "error_id" in error_info
        assert "category" in error_info
        assert "severity" in error_info

    @pytest.mark.asyncio
    async def test_execution_context_to_error_context(self):
        """Test conversion from ExecutionContext to AsyncErrorContext."""
        from fapilog.core.context import ExecutionContext

        ctx = ExecutionContext(
            request_id="test-req",
            user_id="test-user",
            session_id="test-session",
            container_id="test-container",
            component_name="test-component",
            operation_name="test-operation",
        )
        ctx.retry_count = 2
        ctx.circuit_breaker_state = "OPEN"
        ctx.metadata["custom"] = "value"
        ctx.complete()

        error_context = ctx.to_error_context(ErrorCategory.NETWORK, ErrorSeverity.HIGH)

        assert error_context.category == ErrorCategory.NETWORK
        assert error_context.severity == ErrorSeverity.HIGH
        assert error_context.request_id == "test-req"
        assert error_context.user_id == "test-user"
        assert error_context.session_id == "test-session"
        assert error_context.container_id == "test-container"
        assert error_context.component_name == "test-component"
        assert isinstance(error_context.operation_duration, float)
        assert error_context.metadata["custom"] == "value"
        assert error_context.metadata["execution_id"] == ctx.execution_id
        assert error_context.metadata["retry_count"] == 2
        assert error_context.metadata["circuit_breaker_state"] == "OPEN"
        assert error_context.metadata["error_chain_length"] == 0

    @pytest.mark.asyncio
    async def test_context_manager_functionality(self):
        """Test ContextManager class functionality."""
        from fapilog.core.context import get_context_manager

        # Test singleton behavior
        manager1 = await get_context_manager()
        manager2 = await get_context_manager()
        assert manager1 is manager2

        # Test context creation
        context = await manager1.create_context(
            request_id="test-req", operation_name="test-op", custom_field="custom_value"
        )

        assert context.request_id == "test-req"
        assert context.operation_name == "test-op"
        assert context.metadata["custom_field"] == "custom_value"

        # Test context retrieval
        retrieved = await manager1.get_context(context.execution_id)
        assert retrieved is context

        # Test statistics
        stats = await manager1.get_statistics()
        assert (
            isinstance(stats["active_contexts"], int) and stats["active_contexts"] >= 1
        )
        assert isinstance(stats["context_hierarchy_size"], int)

        # Test context completion
        await manager1.complete_context(context.execution_id)
        assert context.is_completed

    @pytest.mark.asyncio
    async def test_context_manager_hierarchy(self):
        """Test context hierarchy tracking in ContextManager."""
        from fapilog.core.context import get_context_manager

        manager = await get_context_manager()

        # Create parent context
        parent = await manager.create_context(operation_name="parent")

        # Create child context
        child = await manager.create_context(
            operation_name="child", parent_execution_id=parent.execution_id
        )

        # Test hierarchy
        chain = await manager.get_context_chain(child.execution_id)
        assert len(chain) == 2
        assert chain[0] is parent  # Root
        assert chain[1] is child  # Current

    @pytest.mark.asyncio
    async def test_context_manager_error_handling(self):
        """Test error handling in ContextManager."""
        from fapilog.core.context import get_context_manager

        manager = await get_context_manager()

        async with execution_context(operation_name="test_error") as ctx:
            error = RuntimeError("Test error")
            await manager.add_error_to_current_context(error)

            # Check error was added to context
            assert len(ctx.error_chain) == 1
            assert ctx.error_chain[0]["error_type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_preserve_context_decorator(self):
        """Test preserve_context decorator."""
        from fapilog.core.context import get_context_values, preserve_context

        @preserve_context
        async def decorated_function():
            return get_context_values()

        async with execution_context(request_id="test-123", operation_name="test-op"):
            # Get context inside the execution context
            values = await decorated_function()
            assert values["request_id"] == "test-123"
            assert values["operation_name"] == "test-op"

    @pytest.mark.asyncio
    async def test_with_context_decorator(self):
        """Test with_context decorator."""
        from fapilog.core.context import get_context_values, with_context

        @with_context(component_name="test-component", operation_name="test-operation")
        async def decorated_function():
            return get_context_values()

        values = await decorated_function()
        assert values["component_name"] == "test-component"
        assert values["operation_name"] == "test-operation"

    @pytest.mark.asyncio
    async def test_context_variables_direct_access(self):
        """Test direct access to context variables."""
        from fapilog.core.context import (
            add_context_metadata,
            get_context_values,
            increment_retry_count,
            set_circuit_breaker_state,
        )

        async with execution_context(
            request_id="test-123", user_id="user-456", operation_name="test-op"
        ) as ctx:
            # Test get_context_values
            values = get_context_values()
            assert values["request_id"] == "test-123"
            assert values["user_id"] == "user-456"
            assert values["operation_name"] == "test-op"

            # Test add_context_metadata
            await add_context_metadata(custom_key="custom_value")
            assert ctx.metadata["custom_key"] == "custom_value"

            # Test increment_retry_count
            count1 = await increment_retry_count()
            assert count1 == 1
            count2 = await increment_retry_count()
            assert count2 == 2
            assert ctx.retry_count == 2

            # Test set_circuit_breaker_state
            await set_circuit_breaker_state("OPEN")
            assert ctx.circuit_breaker_state == "OPEN"

    @pytest.mark.asyncio
    async def test_create_child_context(self):
        """Test create_child_context functionality."""
        from fapilog.core.context import create_child_context

        async with execution_context(
            request_id="parent-req",
            user_id="parent-user",
            component_name="parent-component",
        ):
            async with create_child_context(
                "child_operation", custom_field="child_value"
            ) as child_ctx:
                assert child_ctx.operation_name == "child_operation"
                assert child_ctx.request_id == "parent-req"
                assert child_ctx.user_id == "parent-user"
                assert child_ctx.component_name == "parent-component"
                assert child_ctx.metadata["custom_field"] == "child_value"

    @pytest.mark.asyncio
    async def test_convenience_context_functions(self):
        """Test convenience context functions."""
        from fapilog.core.context import with_component_context, with_request_context

        # Test with_request_context
        async with with_request_context(
            "req-123", user_id="user-456", session_id="session-789"
        ) as req_ctx:
            assert req_ctx.request_id == "req-123"
            assert req_ctx.user_id == "user-456"
            assert req_ctx.session_id == "session-789"
            assert req_ctx.operation_name == "request_handling"

        # Test with_component_context
        async with with_component_context(
            "test-component",
            container_id="container-123",
            operation_name="custom-operation",
        ) as comp_ctx:
            assert comp_ctx.component_name == "test-component"
            assert comp_ctx.container_id == "container-123"
            assert comp_ctx.operation_name == "custom-operation"

        # Test with_component_context default operation name
        async with with_component_context("another-component") as comp_ctx2:
            assert comp_ctx2.component_name == "another-component"
            assert comp_ctx2.operation_name == "another-component_operation"

    @pytest.mark.asyncio
    async def test_context_without_current_execution(self):
        """Test error context creation without current execution context."""
        from fapilog.core.context import (
            get_current_error_context,
            get_current_execution_context,
        )

        # Outside any execution context
        current_ctx = await get_current_execution_context()
        assert current_ctx is None

        # Should still create error context with fallback
        error_context = await get_current_error_context(
            ErrorCategory.VALIDATION, ErrorSeverity.LOW
        )
        assert error_context.category == ErrorCategory.VALIDATION
        assert error_context.severity == ErrorSeverity.LOW

    @pytest.mark.asyncio
    async def test_context_variable_lookup_errors(self):
        """Test handling of context variable lookup errors."""
        from fapilog.core.context import increment_retry_count

        # Test increment_retry_count without existing context
        count = await increment_retry_count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """Test context manager cleanup functionality."""

        from fapilog.core.context import ContextManager

        manager = ContextManager()

        # Create a context
        context = await manager.create_context(operation_name="test")
        execution_id = context.execution_id

        # Verify context exists
        retrieved = await manager.get_context(execution_id)
        assert retrieved is context

        # Complete context
        await manager.complete_context(execution_id)

        # Context should still exist immediately after completion
        retrieved_after = await manager.get_context(execution_id)
        assert retrieved_after is context

        # Test that cleanup would eventually happen (we can't wait 300s in tests)
        # So we'll test the cleanup method directly with a short delay
        await manager._cleanup_context_later(execution_id, delay=0.01)

        # After cleanup, context should be removed
        assert await manager.get_context(execution_id) is None

    @pytest.mark.asyncio
    async def test_execution_context_exception_handling(self):
        """Test that execution context properly handles exceptions."""
        from fapilog.core.context import execution_context

        with pytest.raises(ValueError):
            async with execution_context(operation_name="exception_test") as ctx:
                raise ValueError("Test exception")

        # Context should still be completed even after exception
        assert ctx.is_completed
        assert len(ctx.error_chain) == 1
        assert ctx.error_chain[0]["error_type"] == "ValueError"


# Configuration for pytest-asyncio
pytestmark = pytest.mark.asyncio
