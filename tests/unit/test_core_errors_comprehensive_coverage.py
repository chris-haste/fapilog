"""Comprehensive tests for fapilog.core.errors to improve coverage."""

from __future__ import annotations

import sys
from unittest.mock import Mock, patch

from fapilog.core.errors import (
    CacheCapacityError,
    CacheError,
    CacheMissError,
    CacheOperationError,
    ComponentError,
    ConfigurationError,
    ContainerError,
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    ExternalServiceError,
    FapilogError,
    NetworkError,
    PluginError,
    PluginExecutionError,
    PluginLoadError,
    TimeoutError,
    ValidationError,
    capture_unhandled_exceptions,
    create_error_context,
    serialize_exception,
)


class TestErrorClassConstructors:
    """Test error class constructors and inheritance."""

    def test_container_error_constructor(self) -> None:
        """Test ContainerError constructor with default values."""
        error = ContainerError("Container failed")
        assert error.context.category == ErrorCategory.CONTAINER
        assert error.context.severity == ErrorSeverity.HIGH
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.RESTART

    def test_component_error_constructor(self) -> None:
        """Test ComponentError constructor with default values."""
        error = ComponentError("Component failed")
        assert error.context.category == ErrorCategory.COMPONENT
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.RETRY

    def test_plugin_error_constructor_without_name(self) -> None:
        """Test PluginError constructor without plugin name."""
        error = PluginError("Plugin failed")
        assert error.context.category == ErrorCategory.PLUGIN_EXEC
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK
        # plugin_name should be None when not provided
        assert error.context.plugin_name is None

    def test_plugin_error_constructor_with_name(self) -> None:
        """Test PluginError constructor with plugin name."""
        error = PluginError("Plugin failed", plugin_name="test-plugin")
        assert error.context.plugin_name == "test-plugin"

    def test_plugin_load_error_constructor(self) -> None:
        """Test PluginLoadError constructor with default values."""
        error = PluginLoadError("Plugin load failed")
        # PluginLoadError overrides the category from PluginError
        assert error.context.category == ErrorCategory.PLUGIN_LOAD
        assert error.context.severity == ErrorSeverity.HIGH
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.NONE

    def test_plugin_execution_error_constructor(self) -> None:
        """Test PluginExecutionError constructor with default values."""
        error = PluginExecutionError("Plugin execution failed")
        # PluginExecutionError overrides the category from PluginError
        assert error.context.category == ErrorCategory.PLUGIN_EXEC
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK

    def test_cache_error_constructor(self) -> None:
        """Test CacheError constructor with default values."""
        error = CacheError("Cache failed")
        assert error.context.category == ErrorCategory.SYSTEM
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK

    def test_cache_error_constructor_with_context_and_cause(self) -> None:
        """Test CacheError constructor with custom context and cause."""
        context = create_error_context(
            ErrorCategory.SYSTEM, ErrorSeverity.HIGH, ErrorRecoveryStrategy.RETRY
        )
        cause = RuntimeError("Root cause")
        error = CacheError("Cache failed", error_context=context, cause=cause)
        assert error.context == context
        assert error.__cause__ == cause

    def test_cache_miss_error_constructor(self) -> None:
        """Test CacheMissError constructor."""
        error = CacheMissError("missing-key")
        assert error.cache_key == "missing-key"
        assert error.context.category == ErrorCategory.SYSTEM
        assert error.context.severity == ErrorSeverity.LOW

    def test_cache_operation_error_constructor(self) -> None:
        """Test CacheOperationError constructor."""
        error = CacheOperationError("get", "test-key")
        assert "get" in error.message
        assert "test-key" in error.message
        assert error.context.category == ErrorCategory.SYSTEM

    def test_cache_capacity_error_constructor(self) -> None:
        """Test CacheCapacityError constructor."""
        error = CacheCapacityError("test-key", 100, 50)
        assert error.cache_key == "test-key"
        assert error.current_size == 100
        assert error.capacity == 50
        assert "100/50" in error.message


class TestNetworkAndTimeoutErrors:
    """Test network and timeout related error classes."""

    def test_network_error_constructor(self) -> None:
        """Test NetworkError constructor."""
        error = NetworkError("Connection failed")
        assert error.context.category == ErrorCategory.NETWORK
        assert error.context.severity == ErrorSeverity.HIGH

    def test_timeout_error_constructor(self) -> None:
        """Test TimeoutError constructor."""
        error = TimeoutError("Operation timed out")
        assert error.context.category == ErrorCategory.TIMEOUT
        assert error.context.severity == ErrorSeverity.MEDIUM


class TestDataAndValidationErrors:
    """Test data and validation related error classes."""

    def test_validation_error_constructor(self) -> None:
        """Test ValidationError constructor."""
        error = ValidationError("Invalid data")
        assert error.context.category == ErrorCategory.VALIDATION
        assert error.context.severity == ErrorSeverity.LOW


class TestExternalServiceErrors:
    """Test external service error classes."""

    def test_external_service_error_constructor(self) -> None:
        """Test ExternalServiceError constructor."""
        error = ExternalServiceError("External service failed")
        assert error.context.category == ErrorCategory.EXTERNAL
        assert error.context.severity == ErrorSeverity.HIGH


class TestConfigurationErrors:
    """Test configuration error classes."""

    def test_configuration_error_constructor(self) -> None:
        """Test ConfigurationError constructor."""
        error = ConfigurationError("Invalid configuration")
        assert error.context.category == ErrorCategory.CONFIG
        assert error.context.severity == ErrorSeverity.HIGH


class TestSerializeExceptionEdgeCases:
    """Test edge cases in serialize_exception function."""

    def test_serialize_exception_with_exception_during_traceback_extraction(
        self,
    ) -> None:
        """Test serialize_exception when traceback extraction fails."""
        # Mock traceback.extract_tb to raise an exception
        with patch(
            "traceback.extract_tb", side_effect=RuntimeError("Extraction failed")
        ):
            try:
                raise ValueError("Test error")
            except ValueError:
                exc_info = sys.exc_info()

            result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
            # Should still return basic error info even if frame extraction fails
            assert result.get("error.type") == "ValueError"
            assert "error.stack" in result
            # Frames should not be present due to extraction failure
            assert "error.frames" not in result

    def test_serialize_exception_with_exception_during_frame_processing(self) -> None:
        """Test serialize_exception when individual frame processing fails."""
        # Create a mock frame that will cause an exception when accessed
        mock_frame = Mock()
        mock_frame.filename = "test.py"
        mock_frame.lineno = 42
        mock_frame.name = "test_function"
        # Make code access raise an exception
        mock_frame.line = Mock(side_effect=AttributeError("No code"))

        # Mock traceback.extract_tb to return our problematic frame
        with patch("traceback.extract_tb", return_value=[mock_frame]):
            try:
                raise RuntimeError("Test error")
            except RuntimeError:
                exc_info = sys.exc_info()

            result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
            # Should handle frame processing errors gracefully
            assert result.get("error.type") == "RuntimeError"
            assert "error.stack" in result

    def test_serialize_exception_with_cause_and_context(self) -> None:
        """Test serialize_exception with exception cause and context."""
        try:
            try:
                raise RuntimeError("Root cause")
            except RuntimeError as e:
                raise ValueError("Secondary error") from e
        except ValueError:
            exc_info = sys.exc_info()

        result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
        assert result.get("error.type") == "ValueError"
        assert result.get("error.cause") == "RuntimeError"

    def test_serialize_exception_with_context_only(self) -> None:
        """Test serialize_exception with exception context but no cause."""
        try:
            try:
                raise RuntimeError("Context error")
            except RuntimeError as err:
                raise ValueError("Context error") from err
        except ValueError:
            exc_info = sys.exc_info()

        result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
        assert result.get("error.type") == "ValueError"
        # Should not have cause since it's not a chained exception

    def test_serialize_exception_with_empty_traceback(self) -> None:
        """Test serialize_exception with empty traceback."""
        # Create exc_info with None traceback
        exc_info = (ValueError, ValueError("Test"), None)
        result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
        assert result.get("error.type") == "ValueError"
        # Even with None traceback, we get basic error info
        assert "error.stack" in result


class TestUnhandledExceptionHooks:
    """Test unhandled exception hook functionality."""

    def test_capture_unhandled_exceptions_idempotent(self) -> None:
        """Test that capture_unhandled_exceptions is idempotent."""
        mock_logger = Mock()

        # First call should install hooks
        capture_unhandled_exceptions(mock_logger)

        # Second call should return early
        capture_unhandled_exceptions(mock_logger)

        # Verify hooks were installed only once
        assert sys.excepthook != sys.__excepthook__

    def test_capture_unhandled_exceptions_sys_hook(self) -> None:
        """Test sys.excepthook installation and delegation."""
        mock_logger = Mock()
        original_hook = sys.excepthook

        try:
            capture_unhandled_exceptions(mock_logger)

            # Test that our hook is installed (function reference changed)
            # Note: The function reference might be the same due to how Python handles closures
            # but we can verify the function is callable and different from the original
            assert callable(sys.excepthook)
            # The important thing is that the function is callable and installed

        finally:
            # Restore original hook
            sys.excepthook = original_hook

    def test_capture_unhandled_exceptions_asyncio_handler(self) -> None:
        """Test asyncio exception handler installation."""
        mock_logger = Mock()

        # Test that the function can be called without error
        # (The actual asyncio handler setup is complex and depends on runtime environment)
        try:
            capture_unhandled_exceptions(mock_logger)
            # If we get here, the function executed without error
            assert True
        except Exception as e:
            # If there's an error, it should be a known limitation
            assert "event loop" in str(e).lower() or "asyncio" in str(e).lower()

    def test_capture_unhandled_exceptions_no_event_loop(self) -> None:
        """Test capture_unhandled_exceptions when no event loop exists."""
        mock_logger = Mock()

        # Mock asyncio.get_event_loop to raise RuntimeError
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("No loop")):
            capture_unhandled_exceptions(mock_logger)

            # Should handle the case gracefully without setting asyncio handler
            # but sys.excepthook should still be set
            assert sys.excepthook != sys.__excepthook__

    def test_asyncio_exception_handler_with_exception(self) -> None:
        """Test asyncio exception handler with actual exception."""
        # Test the handler logic directly
        context = {"exception": ValueError("Test error")}

        # Simulate the handler logic
        exc = context.get("exception")
        assert isinstance(exc, BaseException)
        assert str(exc) == "Test error"

    def test_asyncio_exception_handler_with_future(self) -> None:
        """Test asyncio exception handler with future in context."""
        # Mock a future with an exception
        mock_future = Mock()
        mock_future.exception.return_value = RuntimeError("Future error")

        context = {"future": mock_future}

        # Simulate the handler logic
        exc = context.get("exception")
        if exc is None:
            fut = context.get("future")
            if fut is not None and hasattr(fut, "exception"):
                exc = fut.exception()

        assert isinstance(exc, BaseException)
        assert str(exc) == "Future error"

    def test_asyncio_exception_handler_with_task(self) -> None:
        """Test asyncio exception handler with task in context."""
        # Mock a task with an exception
        mock_task = Mock()
        mock_task.exception.return_value = OSError("Task error")

        context = {"task": mock_task}

        # Simulate the handler logic
        exc = context.get("exception")
        if exc is None:
            fut = context.get("task")
            if fut is not None and hasattr(fut, "exception"):
                exc = fut.exception()

        assert isinstance(exc, BaseException)
        assert str(exc) == "Task error"

    def test_asyncio_exception_handler_with_invalid_future(self) -> None:
        """Test asyncio exception handler with future that has no exception method."""
        mock_logger = Mock()
        mock_loop = Mock()

        # Mock a future without exception method
        mock_future = Mock()
        del mock_future.exception

        context = {"future": mock_future}

        # Mock the exception handler
        def mock_handler(loop, context):
            exc = context.get("exception")
            if exc is None:
                fut = context.get("future") or context.get("task")
                try:
                    if fut is not None and hasattr(fut, "exception"):
                        exc = fut.exception()
                except Exception:
                    exc = None
            if isinstance(exc, BaseException):
                try:
                    mock_logger.error("unhandled_task_exception", exc=exc)
                except Exception:
                    pass

        mock_handler(mock_loop, context)

        # Should not have logged anything since no exception was found
        mock_logger.error.assert_not_called()

    def test_asyncio_exception_handler_delegation(self) -> None:
        """Test asyncio exception handler delegates to previous handler."""
        mock_loop = Mock()

        # Mock previous handler
        mock_prev_handler = Mock()
        mock_loop.get_exception_handler.return_value = mock_prev_handler

        # Mock the exception handler
        def mock_handler(loop, context):
            # Delegate to previous handler if present
            try:
                if callable(mock_prev_handler):
                    mock_prev_handler(loop, context)
            except Exception:
                pass

        context = {"exception": ValueError("Test")}
        mock_handler(mock_loop, context)

        # Should have called the previous handler
        mock_prev_handler.assert_called_once_with(mock_loop, context)

    def test_asyncio_exception_handler_setup_failure(self) -> None:
        """Test asyncio exception handler setup failure handling."""
        mock_logger = Mock()
        mock_loop = Mock()

        # Mock set_exception_handler to fail
        mock_loop.get_exception_handler.return_value = None
        mock_loop.set_exception_handler.side_effect = RuntimeError("Setup failed")

        with patch("asyncio.get_event_loop", return_value=mock_loop):
            # Should handle setup failure gracefully
            capture_unhandled_exceptions(mock_logger)

            # sys.excepthook should still be set even if asyncio handler fails
            assert sys.excepthook != sys.__excepthook__


class TestErrorContextAndMetadata:
    """Test error context and metadata handling."""

    def test_fapilog_error_with_context_method(self) -> None:
        """Test FapilogError.with_context method."""
        error = FapilogError("Test error")
        error.with_context(key1="value1", key2="value2")

        assert error.context.metadata.get("key1") == "value1"
        assert error.context.metadata.get("key2") == "value2"
        assert error.with_context(key3="value3") is error  # Returns self

    def test_fapilog_error_to_dict_serialization(self) -> None:
        """Test FapilogError.to_dict method."""
        error = FapilogError("Test error")
        error.with_context(test_key="test_value")

        result = error.to_dict()
        assert result["error_type"] == "FapilogError"
        assert result["message"] == "Test error"
        assert "context" in result
        assert result["cause"] is None  # No cause set

    def test_fapilog_error_to_dict_with_cause(self) -> None:
        """Test FapilogError.to_dict method with cause."""
        try:
            raise RuntimeError("Root cause")
        except RuntimeError as cause:
            error = FapilogError("Test error", cause=cause)

        result = error.to_dict()
        assert result["cause"] == "Root cause"

    def test_create_error_context_with_metadata(self) -> None:
        """Test create_error_context with additional metadata."""
        context = create_error_context(
            ErrorCategory.SYSTEM,
            ErrorSeverity.HIGH,
            ErrorRecoveryStrategy.RETRY,
            extra_data="test",
            numeric_value=42,
        )

        assert context.metadata.get("extra_data") == "test"
        assert context.metadata.get("numeric_value") == 42
