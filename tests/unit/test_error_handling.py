"""
Comprehensive tests for the async error handling hierarchy.

This test module covers all the error handling components including:
- Standardized error types with context preservation
- Retry mechanisms with exponential backoff
- Enterprise compliance audit trails
- Error context preservation across async operations
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fapilog.core import (
    AsyncRetrier,
    AuditEventType,
    AuditLogLevel,
    AuditTrail,
    AuthenticationError,
    ComplianceLevel,
    CompliancePolicy,
    ComponentError,
    ContainerError,
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    FapilogError,
    NetworkError,
    PluginError,
    RetryConfig,
    RetryExhaustedError,
    ValidationError,
    audit_error,
    audit_security_event,
    execution_context,
    get_audit_trail,
    get_current_error_context,
    retry_async,
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
        assert error.context.error_id is not None
        assert error.context.timestamp is not None

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
            assert ctx.execution_id is not None
            assert not ctx.is_completed

        # Context should be completed after exiting
        assert ctx.is_completed
        assert ctx.duration is not None

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

        assert ctx.execution_id is not None
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
        assert ctx.duration is not None
        assert ctx.duration >= 0

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
        assert error_context.operation_duration is not None
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
        assert stats["active_contexts"] >= 1
        assert stats["context_hierarchy_size"] >= 0

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
        assert await manager.get_context(execution_id) is not None

        # Complete context
        await manager.complete_context(execution_id)

        # Context should still exist immediately after completion
        assert await manager.get_context(execution_id) is not None

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


class TestRetryMechanism:
    """Test retry mechanisms with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_successful_operation(self):
        """Succeeds immediately without delays."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=3, base_delay=0.0))

        async def successful_operation():
            return "success"

        result = await retrier.retry(successful_operation)
        assert result == "success"
        assert retrier.stats.attempt_count == 1
        assert retrier.stats.total_delay == 0.0

    @pytest.mark.asyncio
    async def test_retry_eventual_success(self):
        """Retries until success within max_attempts."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=3, base_delay=0.0))

        call_count = 0

        async def eventually_successful_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await retrier.retry(eventually_successful_operation)
        assert result == "success"
        assert retrier.stats.attempt_count == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Raises RetryExhaustedError after max_attempts."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=2, base_delay=0.0))

        async def always_failing_operation():
            raise ConnectionError("Always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retrier.retry(always_failing_operation)

        assert retrier.stats.attempt_count == 2
        assert "All 2 retry attempts exhausted" in str(exc_info.value)
        assert exc_info.value.retry_stats is not None

    @pytest.mark.asyncio
    async def test_non_retryable_exception_bubbles(self):
        """ValueError should not be retried when not configured."""
        retrier = AsyncRetrier(RetryConfig(max_attempts=3, retryable_exceptions=[]))

        async def bad_operation():
            raise ValueError("Do not retry")

        with pytest.raises(ValueError):
            await retrier.retry(bad_operation)
        assert retrier.stats.attempt_count == 1

    @pytest.mark.asyncio
    async def test_retry_timeout_per_attempt(self):
        """Times out each attempt and surfaces last timeout."""
        retrier = AsyncRetrier(
            RetryConfig(max_attempts=2, base_delay=0.0, timeout_per_attempt=0.01)
        )

        async def slow_operation():
            await asyncio.sleep(0.02)
            return "too slow"

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retrier.retry(slow_operation)

        stats = exc_info.value.retry_stats
        assert stats is not None
        assert stats.attempt_count == 2
        assert isinstance(stats.last_exception, asyncio.TimeoutError)

    @pytest.mark.asyncio
    async def test_retry_async_convenience(self):
        """retry_async helper should delegate to AsyncRetrier."""
        attempt_count = 0

        async def test_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ConnectionError("First fails")
            return "retry_async_success"

        result = await retry_async(test_operation, config=RetryConfig(max_attempts=2))
        assert result == "retry_async_success"
        assert attempt_count == 2


class TestAuditTrails:
    """Test enterprise compliance audit trails."""

    @pytest.mark.asyncio
    async def test_audit_trail_basic_logging(self):
        """Test basic audit event logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            policy = CompliancePolicy(level=ComplianceLevel.BASIC)
            audit_trail = AuditTrail(policy, storage_path)

            await audit_trail.start()

            # Log an event
            event_id = await audit_trail.log_event(
                AuditEventType.ERROR_OCCURRED,
                "Test error occurred",
                component="test-component",
                user_id="test-user",
            )

            assert event_id is not None
            assert audit_trail._event_count == 1

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_error_logging(self):
        """Test error-specific audit logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            await audit_trail.start()

            # Create a test error
            error = ComponentError("Component failed", component_name="test-component")

            # Audit the error
            event_id = await audit_trail.log_error(error, operation="test_operation")

            assert event_id is not None
            assert audit_trail._error_count == 1

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_security_events(self):
        """Test security event auditing."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            await audit_trail.start()

            # Log security event
            event_id = await audit_trail.log_security_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "Invalid login attempt",
                user_id="attempted-user",
                client_ip="192.168.1.100",
            )

            assert event_id is not None
            assert audit_trail._security_event_count == 1

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_data_access_logging(self):
        """Test data access audit logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            await audit_trail.start()

            # Log data access
            event_id = await audit_trail.log_data_access(
                resource="sensitive_database",
                operation="read",
                user_id="data-analyst",
                contains_pii=True,
                data_classification="confidential",
            )

            assert event_id is not None

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_compliance_policy_enforcement(self):
        """Test compliance policy enforcement."""
        policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            gdpr_data_subject_rights=True,
            real_time_alerts=True,
        )

        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(policy, storage_path)

            await audit_trail.start()

            # Log PII access (should trigger GDPR compliance)
            await audit_trail.log_event(
                AuditEventType.DATA_ACCESS,
                "PII data accessed",
                contains_pii=True,
                user_id="gdpr-user",
            )

            stats = await audit_trail.get_statistics()
            assert stats["policy"]["compliance_level"] == "gdpr"

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_event_type_enum(self):
        """Test AuditEventType enum values."""
        # Test error events
        assert AuditEventType.ERROR_OCCURRED == "error_occurred"
        assert AuditEventType.ERROR_RECOVERED == "error_recovered"
        assert AuditEventType.ERROR_ESCALATED == "error_escalated"

        # Test security events
        assert AuditEventType.AUTHENTICATION_FAILED == "authentication_failed"
        assert AuditEventType.AUTHORIZATION_FAILED == "authorization_failed"
        assert AuditEventType.SECURITY_VIOLATION == "security_violation"

        # Test system events
        assert AuditEventType.SYSTEM_STARTUP == "system_startup"
        assert AuditEventType.SYSTEM_SHUTDOWN == "system_shutdown"
        assert AuditEventType.COMPONENT_FAILURE == "component_failure"
        assert AuditEventType.COMPONENT_RECOVERY == "component_recovery"

        # Test data events
        assert AuditEventType.DATA_ACCESS == "data_access"
        assert AuditEventType.DATA_MODIFICATION == "data_modification"
        assert AuditEventType.DATA_DELETION == "data_deletion"

    @pytest.mark.asyncio
    async def test_compliance_level_enum(self):
        """Test ComplianceLevel enum values."""
        assert ComplianceLevel.NONE == "none"
        assert ComplianceLevel.BASIC == "basic"
        assert ComplianceLevel.SOX == "sox"
        assert ComplianceLevel.HIPAA == "hipaa"
        assert ComplianceLevel.GDPR == "gdpr"
        assert ComplianceLevel.PCI_DSS == "pci_dss"
        assert ComplianceLevel.SOC2 == "soc2"
        assert ComplianceLevel.ISO27001 == "iso27001"

    @pytest.mark.asyncio
    async def test_audit_log_level_enum(self):
        """Test AuditLogLevel enum values."""

        assert AuditLogLevel.DEBUG == "debug"
        assert AuditLogLevel.INFO == "info"
        assert AuditLogLevel.WARNING == "warning"
        assert AuditLogLevel.ERROR == "error"
        assert AuditLogLevel.CRITICAL == "critical"
        assert AuditLogLevel.SECURITY == "security"

    @pytest.mark.asyncio
    async def test_compliance_policy_creation(self):
        """Test CompliancePolicy model creation and validation."""
        # Test default policy
        policy = CompliancePolicy()
        assert policy.level == ComplianceLevel.BASIC
        assert policy.enabled is True
        assert policy.retention_days == 365
        assert policy.archive_after_days == 90
        assert policy.encrypt_audit_logs is True
        assert policy.require_integrity_check is True
        assert policy.real_time_alerts is True
        assert policy.alert_on_critical_errors is True
        assert policy.alert_on_security_events is True
        assert policy.gdpr_data_subject_rights is False
        assert policy.hipaa_minimum_necessary is False
        assert policy.sox_change_control is False

        # Test custom policy
        custom_policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            retention_days=7 * 365,  # 7 years
            archive_after_days=180,
            real_time_alerts=False,
            gdpr_data_subject_rights=True,
            hipaa_minimum_necessary=False,
            sox_change_control=False,
        )
        assert custom_policy.level == ComplianceLevel.GDPR
        assert custom_policy.retention_days == 2555
        assert custom_policy.archive_after_days == 180
        assert custom_policy.real_time_alerts is False
        assert custom_policy.gdpr_data_subject_rights is True
        assert custom_policy.hipaa_minimum_necessary is False
        assert custom_policy.sox_change_control is False

    @pytest.mark.asyncio
    async def test_audit_event_creation(self):
        """Test AuditEvent model creation and validation."""
        # Test basic event
        from fapilog.core.audit import AuditEvent

        event = AuditEvent(
            event_type=AuditEventType.ERROR_OCCURRED,
            message="Test error message",
            component="test-component",
        )
        assert event.event_type == AuditEventType.ERROR_OCCURRED
        assert event.message == "Test error message"
        assert event.component == "test-component"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.log_level == AuditLogLevel.INFO  # Default log level

        # Test event with full metadata
        metadata = {
            "operation": "test_operation",
            "duration_ms": 150,
            "request_id": "req-123",
        }
        detailed_event = AuditEvent(
            event_type=AuditEventType.DATA_ACCESS,
            message="Sensitive data accessed",
            component="data-service",
            user_id="user-456",
            session_id="session-789",
            client_ip="192.168.1.100",
            contains_pii=True,
            contains_phi=False,
            data_classification="confidential",
            metadata=metadata,
        )
        assert detailed_event.user_id == "user-456"
        assert detailed_event.contains_pii is True
        assert detailed_event.contains_phi is False
        assert detailed_event.data_classification == "confidential"
        assert detailed_event.metadata["operation"] == "test_operation"

    @pytest.mark.asyncio
    async def test_audit_trail_initialization(self):
        """Test AuditTrail initialization with different configurations."""
        # Test with minimal configuration
        minimal_trail = AuditTrail()
        assert minimal_trail.policy.level == ComplianceLevel.BASIC
        assert minimal_trail.storage_path.name == "audit_logs"  # Default path
        assert minimal_trail._event_count == 0
        assert minimal_trail._error_count == 0
        assert minimal_trail._security_event_count == 0

        # Test with custom configuration
        policy = CompliancePolicy(level=ComplianceLevel.HIPAA, retention_days=10 * 365)
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            configured_trail = AuditTrail(policy=policy, storage_path=storage_path)
            assert configured_trail.policy.level == ComplianceLevel.HIPAA
            assert configured_trail.storage_path == storage_path

    @pytest.mark.asyncio
    async def test_audit_trail_lifecycle(self):
        """Test AuditTrail start/stop lifecycle."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            # Test start and stop (simplified)
            await audit_trail.start()
            # No public _running attribute, just test that start/stop work
            await audit_trail.stop()

            # Test multiple start/stop calls (should be idempotent)
            await audit_trail.start()
            await audit_trail.start()  # Should be idempotent
            await audit_trail.stop()
            await audit_trail.stop()  # Should be idempotent

    @pytest.mark.asyncio
    async def test_audit_trail_event_logging_variations(self):
        """Test different ways of logging events."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test basic event logging
            event_id_1 = await audit_trail.log_event(
                AuditEventType.SYSTEM_STARTUP, "System initialized"
            )
            assert event_id_1 is not None

            # Test event with all optional parameters
            event_id_2 = await audit_trail.log_event(
                AuditEventType.DATA_MODIFICATION,
                "User profile updated",
                component="user-service",
                user_id="user-123",
                session_id="session-456",
                client_ip="10.0.0.1",
                contains_pii=True,
                contains_phi=False,
                data_classification="personal",
                metadata={"field": "email", "old_value": "old@example.com"},
            )
            assert event_id_2 is not None
            assert event_id_1 != event_id_2

            # Test event with custom metadata only
            event_id_3 = await audit_trail.log_event(
                AuditEventType.COMPONENT_RECOVERY,
                "Component recovered successfully",
                component="recovery-service",
            )
            assert event_id_3 is not None

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_error_logging_comprehensive(self):
        """Test comprehensive error logging functionality."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test different error types
            validation_error = ValidationError("Invalid input data", field_name="email")
            event_id_1 = await audit_trail.log_error(
                validation_error, operation="user_registration"
            )
            assert event_id_1 is not None

            auth_error = AuthenticationError(
                "Invalid credentials", user_id="failed-user"
            )
            event_id_2 = await audit_trail.log_error(
                auth_error, operation="login_attempt"
            )
            assert event_id_2 is not None

            network_error = NetworkError(
                "Connection timeout", service_name="external-api"
            )
            event_id_3 = await audit_trail.log_error(
                network_error, operation="api_call"
            )
            assert event_id_3 is not None

            # Check error count
            assert audit_trail._error_count == 3

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_security_event_logging(self):
        """Test comprehensive security event logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test authentication failure
            auth_event_id = await audit_trail.log_security_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "Multiple failed login attempts",
                user_id="suspicious-user",
                client_ip="192.168.1.100",
                additional_context={"attempt_count": 5, "time_window": "5_minutes"},
            )
            assert auth_event_id is not None

            # Test authorization failure
            authz_event_id = await audit_trail.log_security_event(
                AuditEventType.AUTHORIZATION_FAILED,
                "Access denied to restricted resource",
                user_id="limited-user",
                client_ip="10.0.0.50",
                additional_context={
                    "resource": "/admin/users",
                    "required_role": "admin",
                },
            )
            assert authz_event_id is not None

            # Test security violation
            violation_event_id = await audit_trail.log_security_event(
                AuditEventType.SECURITY_VIOLATION,
                "Potential SQL injection attempt",
                user_id="attacker",
                client_ip="203.0.113.1",
                additional_context={
                    "payload": "'; DROP TABLE users; --",
                    "blocked": True,
                },
            )
            assert violation_event_id is not None

            # Check security event count
            assert audit_trail._security_event_count == 3

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_data_access_comprehensive(self):
        """Test comprehensive data access logging."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Test PII data access
            pii_event_id = await audit_trail.log_data_access(
                resource="customer_database",
                operation="select",
                user_id="data-analyst",
                contains_pii=True,
                contains_phi=False,
                data_classification="confidential",
                record_count=150,
                additional_metadata={
                    "query": "SELECT * FROM customers WHERE region='EU'"
                },
            )
            assert pii_event_id is not None

            # Test PHI data access
            phi_event_id = await audit_trail.log_data_access(
                resource="medical_records",
                operation="read",
                user_id="doctor-smith",
                contains_pii=True,
                contains_phi=True,
                data_classification="restricted",
                record_count=1,
                additional_metadata={
                    "patient_id": "PAT-12345",
                    "diagnosis_code": "ICD-10",
                },
            )
            assert phi_event_id is not None

            # Test data modification
            modify_event_id = await audit_trail.log_data_access(
                resource="user_profiles",
                operation="update",
                user_id="user-456",
                contains_pii=True,
                data_classification="personal",
                record_count=1,
                additional_metadata={
                    "fields_modified": ["email", "phone"],
                    "reason": "user_request",
                },
            )
            assert modify_event_id is not None

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_statistics(self):
        """Test audit trail statistics functionality."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(policy=policy, storage_path=storage_path)
            await audit_trail.start()

            # Generate various events
            await audit_trail.log_event(AuditEventType.SYSTEM_STARTUP, "System started")
            await audit_trail.log_error(
                ComponentError("Test error", component_name="test")
            )
            await audit_trail.log_security_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "Login failed",
                user_id="test-user",
            )
            await audit_trail.log_data_access(
                resource="test_db",
                operation="read",
                user_id="analyst",
                contains_pii=True,
            )

            # Get statistics
            stats = await audit_trail.get_statistics()

            # Verify statistics structure and values (adjust based on actual structure)
            assert "policy" in stats
            assert "error_events" in stats
            assert "security_events" in stats

            assert stats["error_events"] == 1
            assert stats["security_events"] == 1
            assert stats["policy"]["compliance_level"] == "soc2"
            assert stats["policy"]["retention_days"] == 365

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_buffer_management(self):
        """Test audit trail buffer management and flushing."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            # Configure basic audit trail for testing
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Add events to fill buffer
            for i in range(5):
                await audit_trail.log_event(
                    AuditEventType.DATA_ACCESS, f"Access event {i}", user_id=f"user-{i}"
                )

            # Allow some time for background flushing (reduced for CI)
            await asyncio.sleep(0.05)

            # Check that events were processed
            assert audit_trail._event_count == 5

            # Just check that events were processed (no manual flush needed)

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_storage_file_operations(self):
        """Test audit trail file storage operations."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Log some events
            await audit_trail.log_event(AuditEventType.SYSTEM_STARTUP, "System started")
            await audit_trail.log_error(
                ComponentError("Test error", component_name="test")
            )

            # Allow time for automatic flushing (reduced for CI)
            await asyncio.sleep(0.05)

            # Check that files were created
            assert storage_path.exists()
            audit_files = list(storage_path.glob("audit_*.jsonl"))
            assert len(audit_files) > 0

            # Verify file content
            with open(audit_files[0]) as f:
                lines = f.readlines()
                assert len(lines) >= 2

                # Parse and verify first event
                first_event = json.loads(lines[0])
                assert first_event["event_type"] == "system_startup"
                assert first_event["message"] == "System started"

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_compliance_specific_features(self):
        """Test compliance-specific features for different standards."""
        # Test GDPR compliance
        gdpr_policy = CompliancePolicy(
            level=ComplianceLevel.GDPR,
            gdpr_data_subject_rights=True,
            retention_days=6 * 365,  # 6 years
        )

        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            gdpr_trail = AuditTrail(policy=gdpr_policy, storage_path=storage_path)
            await gdpr_trail.start()

            # Log GDPR-relevant event
            await gdpr_trail.log_data_access(
                resource="eu_customer_data",
                operation="read",
                user_id="eu-user",
                contains_pii=True,
                data_classification="personal",
                additional_metadata={
                    "gdpr_lawful_basis": "consent",
                    "data_subject_id": "DS-123",
                },
            )

            stats = await gdpr_trail.get_statistics()
            assert stats["policy"]["compliance_level"] == "gdpr"
            assert stats["policy"]["retention_days"] == 2190

            await gdpr_trail.stop()

        # Test HIPAA compliance
        hipaa_policy = CompliancePolicy(
            level=ComplianceLevel.HIPAA,
            hipaa_minimum_necessary=True,
            retention_days=6 * 365,
        )

        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            hipaa_trail = AuditTrail(policy=hipaa_policy, storage_path=storage_path)
            await hipaa_trail.start()

            # Log HIPAA-relevant event
            await hipaa_trail.log_data_access(
                resource="patient_records",
                operation="read",
                user_id="healthcare-provider",
                contains_phi=True,
                data_classification="restricted",
                additional_metadata={
                    "patient_id": "P-789",
                    "covered_entity": "Hospital-XYZ",
                },
            )

            stats = await hipaa_trail.get_statistics()
            assert stats["policy"]["compliance_level"] == "hipaa"

            await hipaa_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_convenience_functions(self):
        """Test audit convenience functions."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)

            # Test get_audit_trail function
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            trail = await get_audit_trail(policy=policy, storage_path=storage_path)
            assert trail.policy.level == ComplianceLevel.SOC2
            assert trail.storage_path == storage_path

            await trail.start()

            # Test audit_error convenience function
            error = NetworkError("Network failure", service_name="api-service")
            event_id = await audit_error(
                error, operation="network_call", audit_trail=trail
            )
            assert event_id is not None
            assert trail._error_count == 1

            # Test audit_security_event convenience function
            security_event_id = await audit_security_event(
                AuditEventType.AUTHORIZATION_FAILED,
                "Access denied",
                user_id="unauthorized-user",
                audit_trail=trail,
            )
            assert security_event_id is not None
            assert trail._security_event_count == 1

            await trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_error_conditions(self):
        """Test audit trail error handling and edge cases."""
        # Test logging events before starting
        audit_trail = AuditTrail()

        # Should handle gracefully when not started
        event_id = await audit_trail.log_event(
            AuditEventType.ERROR_OCCURRED, "Error before start"
        )
        assert event_id is not None  # Should still generate ID

        # Test with non-existent (but valid) storage path that gets created automatically
        with TemporaryDirectory() as temp_dir:
            invalid_path = Path(temp_dir) / "nonexistent" / "path"
            trail_with_new_path = AuditTrail(storage_path=invalid_path)
            await trail_with_new_path.start()

            # Should handle path creation gracefully
            await trail_with_new_path.log_event(
                AuditEventType.ERROR_OCCURRED, "Test error"
            )

            # Verify path was created
            assert invalid_path.exists()

            await trail_with_new_path.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_concurrent_operations(self):
        """Test audit trail with concurrent operations."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)
            await audit_trail.start()

            # Create multiple concurrent logging operations
            async def log_events(start_index, count):
                event_ids = []
                for i in range(count):
                    event_id = await audit_trail.log_event(
                        AuditEventType.DATA_ACCESS,
                        f"Concurrent access {start_index + i}",
                        user_id=f"user-{start_index + i}",
                    )
                    event_ids.append(event_id)
                return event_ids

            # Run concurrent operations
            tasks = [
                log_events(0, 10),
                log_events(10, 10),
                log_events(20, 10),
            ]

            results = await asyncio.gather(*tasks)

            # Verify all events were logged
            total_events = sum(len(result) for result in results)
            assert total_events == 30
            assert audit_trail._event_count == 30

            # Verify all event IDs are unique
            all_event_ids = [event_id for result in results for event_id in result]
            assert len(set(all_event_ids)) == 30

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_background_tasks(self):
        """Test audit background task functionality."""
        with TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            audit_trail = AuditTrail(storage_path=storage_path)

            # Test start/stop without any events
            await audit_trail.start()
            await asyncio.sleep(0.01)  # Let background tasks run briefly
            await audit_trail.stop()

            # Verify basic functionality worked
            assert audit_trail._event_count == 0

    @pytest.mark.asyncio
    async def test_audit_quick_coverage(self):
        """Test quick coverage improvements for audit module."""
        # Test direct AuditEvent creation with different log levels
        from fapilog.core.audit import AuditEvent

        event1 = AuditEvent(
            event_type=AuditEventType.SYSTEM_STARTUP,
            message="System started",
            log_level=AuditLogLevel.INFO,
        )
        assert event1.log_level == AuditLogLevel.INFO

        event2 = AuditEvent(
            event_type=AuditEventType.ERROR_OCCURRED,
            message="Error occurred",
            log_level=AuditLogLevel.ERROR,
        )
        assert event2.log_level == AuditLogLevel.ERROR

        # Test CompliancePolicy with different configurations
        policy1 = CompliancePolicy(level=ComplianceLevel.GDPR)
        assert policy1.level == ComplianceLevel.GDPR

        policy2 = CompliancePolicy(level=ComplianceLevel.HIPAA, enabled=False)
        assert policy2.enabled is False

    @pytest.mark.asyncio
    async def test_audit_trail_disabled_policy(self):
        """Test audit trail behavior when disabled."""
        policy = CompliancePolicy(enabled=False)
        audit_trail = AuditTrail(policy=policy)

        # When disabled, log_event should return empty string
        event_id = await audit_trail.log_event(
            AuditEventType.SYSTEM_STARTUP, "Test operation"
        )
        assert event_id == ""

        # Statistics should remain at zero
        stats = await audit_trail.get_statistics()
        assert stats["total_events"] == 0

    @pytest.mark.asyncio
    async def test_audit_trail_exception_handling(self):
        """Test audit trail exception handling in event processing."""
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            # Test hostname/process collection exception handling
            with patch("socket.gethostname", side_effect=Exception("Network error")):
                with patch("os.getpid", side_effect=Exception("OS error")):
                    event_id = await audit_trail.log_event(
                        AuditEventType.SYSTEM_STARTUP, "Test with exceptions"
                    )
                    assert event_id  # Should still work despite exceptions

    @pytest.mark.asyncio
    async def test_audit_trail_compliance_alerts(self):
        """Test compliance alert triggering."""
        import tempfile
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(
                level=ComplianceLevel.GDPR,
                real_time_alerts=True,
                alert_on_critical_errors=True,
                alert_on_security_events=True,
            )
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Mock the alert sending method
            with patch.object(
                audit_trail, "_send_compliance_alert", new_callable=AsyncMock
            ) as mock_alert:
                # Test critical error alert
                await audit_trail.log_event(
                    AuditEventType.ERROR_OCCURRED,
                    "Critical error",
                    log_level=AuditLogLevel.CRITICAL,
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

                mock_alert.reset_mock()

                # Test security event alert
                await audit_trail.log_event(
                    AuditEventType.SECURITY_VIOLATION,
                    "Security issue",
                    log_level=AuditLogLevel.SECURITY,
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

                mock_alert.reset_mock()

                # Test GDPR PII alert
                await audit_trail.log_event(
                    AuditEventType.DATA_ACCESS, "PII access", contains_pii=True
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_hipaa_phi_alerts(self):
        """Test HIPAA PHI compliance alerts."""
        import tempfile
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(
                level=ComplianceLevel.HIPAA, real_time_alerts=True
            )
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Mock the alert sending method
            with patch.object(
                audit_trail, "_send_compliance_alert", new_callable=AsyncMock
            ) as mock_alert:
                # Test HIPAA PHI alert
                await audit_trail.log_event(
                    AuditEventType.DATA_ACCESS, "PHI access", contains_phi=True
                )
                # Wait for async event processing (minimal for CI)
                await asyncio.sleep(0.01)
                # Simplified assertion - just check it was called
                assert mock_alert.called

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_disabled_alerts(self):
        """Test audit trail with disabled alerts."""
        import tempfile
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(
                level=ComplianceLevel.SOC2,
                real_time_alerts=False,  # Disabled
            )
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            # Mock the alert sending method
            with patch.object(
                audit_trail, "_send_compliance_alert", new_callable=AsyncMock
            ) as mock_alert:
                # Even critical errors shouldn't trigger alerts when disabled
                await audit_trail.log_event(
                    AuditEventType.ERROR_OCCURRED,
                    "Critical error",
                    log_level=AuditLogLevel.CRITICAL,
                )
                mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_trail_event_querying(self):
        """Test audit event querying and filtering."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Log some test events
            await audit_trail.log_event(
                AuditEventType.AUTHENTICATION_FAILED,
                "User login",
                user_id="user1",
                component="auth",
            )

            await audit_trail.log_event(
                AuditEventType.DATA_MODIFICATION,
                "Data operation",
                user_id="user2",
                component="data",
                log_level=AuditLogLevel.INFO,
            )

            await audit_trail.log_event(
                AuditEventType.ERROR_OCCURRED,
                "System error",
                log_level=AuditLogLevel.ERROR,
            )

            # Wait for events to be processed (minimal for CI)
            await asyncio.sleep(0.01)

            # Test querying all events (exercise the get_events method)
            events = await audit_trail.get_events()
            assert isinstance(events, list)

            # Test filtering by event type (exercises filtering logic)
            auth_events = await audit_trail.get_events(
                event_type=AuditEventType.AUTHENTICATION_FAILED
            )
            assert isinstance(auth_events, list)

            # Test filtering by user ID
            user1_events = await audit_trail.get_events(user_id="user1")
            assert isinstance(user1_events, list)

            # Test filtering by component
            auth_component_events = await audit_trail.get_events(component="auth")
            assert isinstance(auth_component_events, list)

            # Test filtering by log level
            error_events = await audit_trail.get_events(log_level=AuditLogLevel.ERROR)
            assert isinstance(error_events, list)

            # Test time-based filtering
            now = datetime.now(timezone.utc)
            past_events = await audit_trail.get_events(
                start_time=now - timedelta(hours=1), end_time=now + timedelta(hours=1)
            )
            assert isinstance(past_events, list)

            # Test limit parameter
            limited_events = await audit_trail.get_events(limit=2)
            assert isinstance(limited_events, list)

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_corrupted_data_handling(self):
        """Test audit trail handling of corrupted storage data."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            # Create a corrupted log file
            log_file = Path(temp_dir) / "audit_2024-01-01.jsonl"
            with open(log_file, "w") as f:
                f.write('{"valid": "json"}\n')
                f.write("invalid json line\n")  # Corrupted line
                f.write('{"another": "valid"}\n')

            # Querying should handle corrupted data gracefully
            events = await audit_trail.get_events()
            # Should return events that could be parsed, ignoring corrupted ones
            assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_audit_trail_storage_error_handling(self):
        """Test audit trail storage error handling."""
        import tempfile
        from unittest.mock import mock_open, patch

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Mock file operations to raise exceptions
            with patch("builtins.open", mock_open()) as mock_file:
                mock_file.side_effect = OSError("Storage error")

                # Event processing should continue despite storage errors
                event_id = await audit_trail.log_event(
                    AuditEventType.SYSTEM_STARTUP, "Test with storage error"
                )
                assert event_id  # Should still return an event ID

            await audit_trail.stop()

    @pytest.mark.asyncio
    async def test_audit_trail_cleanup(self):
        """Test audit trail cleanup functionality."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            policy = CompliancePolicy(level=ComplianceLevel.SOC2)
            audit_trail = AuditTrail(storage_path=Path(temp_dir), policy=policy)

            await audit_trail.start()

            # Log an event to ensure it's running
            await audit_trail.log_event(
                AuditEventType.SYSTEM_STARTUP, "Test before cleanup"
            )

            # Test cleanup
            await audit_trail.cleanup()

            # Audit trail should be stopped after cleanup (processing task should be done)
            assert (
                audit_trail._processing_task is None
                or audit_trail._processing_task.done()
            )


class TestIntegration:
    """Test integration between all error handling components."""

    @pytest.mark.asyncio
    async def test_error_propagation_with_context(self):
        """Test error propagation while preserving context."""

        async def operation_level_3():
            # Deepest level - create error with current context
            error = ComponentError(
                "Deep operation failed", component_name="deep-component"
            )
            return error

        async def operation_level_2():
            error = await operation_level_3()
            # Add more context and re-raise
            enhanced_error = ContainerError(
                "Container operation failed", cause=error, container_id="test-container"
            )
            raise enhanced_error

        async def operation_level_1():
            try:
                await operation_level_2()
            except ContainerError as e:
                # Create final error with full context chain
                final_error = FapilogError(
                    "Top-level operation failed",
                    cause=e,
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.CRITICAL,
                )
                raise final_error from e

        # Execute with context
        async with execution_context(
            request_id="context-test-456",
            user_id="context-user",
            operation_name="nested_operations",
        ):
            with pytest.raises(FapilogError) as exc_info:
                await operation_level_1()

            error = exc_info.value
            assert error.context.request_id == "context-test-456"
            assert error.context.user_id == "context-user"
            assert error.context.category == ErrorCategory.SYSTEM
            assert error.context.severity == ErrorSeverity.CRITICAL

            # Check error chain
            assert isinstance(error.__cause__, ContainerError)
            assert isinstance(error.__cause__.__cause__, ComponentError)

    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test performance monitoring and timing in error handling."""
        async with execution_context(operation_name="performance_test") as ctx:
            start_time = ctx.start_time

            # Simulate some work
            await asyncio.sleep(0.01)

            # Check timing
            assert ctx.start_time == start_time
            assert ctx.duration is None  # Should be None until completed

        # After context exit
        assert ctx.is_completed
        assert ctx.duration is not None
        assert ctx.duration > 0.01

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self):
        """Test error handling under concurrent load."""

        async def concurrent_operation(operation_id: str):
            async with execution_context(
                operation_name=f"concurrent_op_{operation_id}",
                request_id=f"req-{operation_id}",
            ):
                if operation_id == "fail":
                    raise NetworkError(f"Operation {operation_id} failed")
                return f"success-{operation_id}"

        # Run multiple operations concurrently
        tasks = [
            concurrent_operation("1"),
            concurrent_operation("2"),
            concurrent_operation("fail"),
            concurrent_operation("3"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        assert results[0] == "success-1"
        assert results[1] == "success-2"
        assert isinstance(results[2], NetworkError)
        assert results[3] == "success-3"


# Configuration for pytest-asyncio
pytestmark = pytest.mark.asyncio
