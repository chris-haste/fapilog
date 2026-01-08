"""
Error Classes Tests for fapilog.core.errors

Tests for error class behavior including:
- Error class constructors and inheritance
- Error context and metadata handling
- Exception serialization
- Unhandled exception hooks

These tests verify behavioral correctness with strong assertions.
"""

from __future__ import annotations

import sys
from unittest.mock import Mock, patch

import pytest

from fapilog.core.errors import (
    AsyncErrorContext,
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
    get_error_context,
    serialize_exception,
    set_error_context,
)


class TestErrorContextVariables:
    """Test error context variable handling."""

    def test_set_and_get_error_context_variables(self) -> None:
        """Setting context variables makes them retrievable."""
        set_error_context(
            request_id="r-1",
            user_id="u-2",
            session_id="s-3",
            container_id="c-4",
        )
        ctx = get_error_context()
        assert ctx["request_id"] == "r-1"
        assert ctx["user_id"] == "u-2"
        assert ctx["session_id"] == "s-3"
        assert ctx["container_id"] == "c-4"

    def test_create_error_context_includes_vars_and_metadata(self) -> None:
        """create_error_context includes context vars and extra metadata."""
        set_error_context(request_id="r-x", user_id="u-y")
        ctx = create_error_context(
            ErrorCategory.SYSTEM,
            ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            extra="v",
        )
        assert isinstance(ctx, AsyncErrorContext)
        assert ctx.request_id == "r-x" and ctx.user_id == "u-y"
        assert ctx.metadata.get("extra") == "v"

    def test_create_error_context_populates_fields(self) -> None:
        """create_error_context sets all required fields."""
        ctx = create_error_context(
            ErrorCategory.DATABASE,
            ErrorSeverity.HIGH,
            ErrorRecoveryStrategy.RETRY,
            note="x",
        )
        assert ctx.category == ErrorCategory.DATABASE
        assert ctx.severity == ErrorSeverity.HIGH
        assert ctx.recovery_strategy == ErrorRecoveryStrategy.RETRY
        assert ctx.metadata.get("note") == "x"

    def test_create_error_context_with_metadata(self) -> None:
        """create_error_context accepts additional metadata kwargs."""
        context = create_error_context(
            ErrorCategory.SYSTEM,
            ErrorSeverity.HIGH,
            ErrorRecoveryStrategy.RETRY,
            extra_data="test",
            numeric_value=42,
        )
        assert context.metadata.get("extra_data") == "test"
        assert context.metadata.get("numeric_value") == 42


class TestFapilogErrorBehavior:
    """Test FapilogError class behavior."""

    def test_fapilog_error_to_dict_contains_context_and_cause(self) -> None:
        """to_dict includes error type, message, context and cause."""
        try:
            raise ValueError("inner")
        except ValueError as inner:
            err = FapilogError(
                "outer",
                category=ErrorCategory.CONFIG,
                severity=ErrorSeverity.HIGH,
                cause=inner,
            )
        d = err.to_dict()
        assert d["error_type"] == "FapilogError"
        assert d["message"] == "outer"
        assert "context" in d and isinstance(d["context"], dict)
        assert d.get("cause") == "inner"

    def test_fapilog_error_with_context_method(self) -> None:
        """with_context adds metadata and returns self for chaining."""
        error = FapilogError("Test error")
        result = error.with_context(key1="value1", key2="value2")

        assert error.context.metadata.get("key1") == "value1"
        assert error.context.metadata.get("key2") == "value2"
        assert result is error  # Returns self for chaining

    def test_fapilog_error_to_dict_serialization(self) -> None:
        """to_dict produces expected serialization structure."""
        error = FapilogError("Test error")
        error.with_context(test_key="test_value")

        result = error.to_dict()
        assert result["error_type"] == "FapilogError"
        assert result["message"] == "Test error"
        assert "context" in result
        assert result["cause"] is None

    def test_fapilog_error_to_dict_with_cause(self) -> None:
        """to_dict includes cause message when present."""
        try:
            raise RuntimeError("Root cause")
        except RuntimeError as cause:
            error = FapilogError("Test error", cause=cause)

        result = error.to_dict()
        assert result["cause"] == "Root cause"

    @pytest.mark.asyncio
    async def test_fapilog_error_captures_async_and_contextvars(self) -> None:
        """FapilogError captures context vars in async context."""
        set_error_context(
            request_id="r1", user_id="u1", session_id="s1", container_id="c1"
        )
        err = FapilogError(
            "msg",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            extra_key=True,
        )
        assert err.context.category == ErrorCategory.VALIDATION
        assert err.context.severity == ErrorSeverity.LOW
        assert err.context.recovery_strategy == ErrorRecoveryStrategy.NONE
        assert err.context.request_id == "r1"
        assert err.context.user_id == "u1"
        assert err.context.metadata.get("extra_key") is True

        as_dict = err.to_dict()
        assert as_dict["error_type"] == "FapilogError"
        assert as_dict["message"] == "msg"
        assert isinstance(as_dict["context"], dict)

    def test_with_context_updates_metadata(self) -> None:
        """with_context adds multiple metadata entries."""
        err = FapilogError("m")
        err.with_context(alpha=1, beta=2)
        assert err.context.metadata.get("alpha") == 1
        assert err.context.metadata.get("beta") == 2


class TestErrorClassConstructors:
    """Test error class constructors and inheritance."""

    def test_container_error_constructor(self) -> None:
        """ContainerError has correct default category and severity."""
        error = ContainerError("Container failed")
        assert error.context.category == ErrorCategory.CONTAINER
        assert error.context.severity == ErrorSeverity.HIGH
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.RESTART

    def test_component_error_constructor(self) -> None:
        """ComponentError has correct default category and severity."""
        error = ComponentError("Component failed")
        assert error.context.category == ErrorCategory.COMPONENT
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.RETRY

    def test_plugin_error_constructor_without_name(self) -> None:
        """PluginError works without plugin name."""
        error = PluginError("Plugin failed")
        assert error.context.category == ErrorCategory.PLUGIN_EXEC
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK
        assert error.context.plugin_name is None

    def test_plugin_error_constructor_with_name(self) -> None:
        """PluginError captures plugin name."""
        error = PluginError("Plugin failed", plugin_name="test-plugin")
        assert error.context.plugin_name == "test-plugin"

    def test_plugin_load_error_constructor(self) -> None:
        """PluginLoadError has correct category override."""
        error = PluginLoadError("Plugin load failed")
        assert error.context.category == ErrorCategory.PLUGIN_LOAD
        assert error.context.severity == ErrorSeverity.HIGH
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.NONE

    def test_plugin_execution_error_constructor(self) -> None:
        """PluginExecutionError has correct category override."""
        error = PluginExecutionError("Plugin execution failed")
        assert error.context.category == ErrorCategory.PLUGIN_EXEC
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK

    def test_cache_error_constructor(self) -> None:
        """CacheError has correct default values."""
        error = CacheError("Cache failed")
        assert error.context.category == ErrorCategory.SYSTEM
        assert error.context.severity == ErrorSeverity.MEDIUM
        assert error.context.recovery_strategy == ErrorRecoveryStrategy.FALLBACK

    def test_cache_error_constructor_with_context_and_cause(self) -> None:
        """CacheError accepts custom context and cause."""
        context = create_error_context(
            ErrorCategory.SYSTEM, ErrorSeverity.HIGH, ErrorRecoveryStrategy.RETRY
        )
        cause = RuntimeError("Root cause")
        error = CacheError("Cache failed", error_context=context, cause=cause)
        assert error.context == context
        assert error.__cause__ == cause

    def test_cache_miss_error_constructor(self) -> None:
        """CacheMissError captures cache key."""
        error = CacheMissError("missing-key")
        assert error.cache_key == "missing-key"
        assert error.context.category == ErrorCategory.SYSTEM
        assert error.context.severity == ErrorSeverity.LOW

    def test_cache_operation_error_constructor(self) -> None:
        """CacheOperationError includes operation and key in message."""
        error = CacheOperationError("get", "test-key")
        assert "get" in error.message
        assert "test-key" in error.message
        assert error.context.category == ErrorCategory.SYSTEM

    def test_cache_capacity_error_constructor(self) -> None:
        """CacheCapacityError captures size info."""
        error = CacheCapacityError("test-key", 100, 50)
        assert error.cache_key == "test-key"
        assert error.current_size == 100
        assert error.capacity == 50
        assert "100/50" in error.message

    def test_network_error_constructor(self) -> None:
        """NetworkError has correct category."""
        error = NetworkError("Connection failed")
        assert error.context.category == ErrorCategory.NETWORK
        assert error.context.severity == ErrorSeverity.HIGH

    def test_timeout_error_constructor(self) -> None:
        """TimeoutError has correct category."""
        error = TimeoutError("Operation timed out")
        assert error.context.category == ErrorCategory.TIMEOUT
        assert error.context.severity == ErrorSeverity.MEDIUM

    def test_validation_error_constructor(self) -> None:
        """ValidationError has correct category."""
        error = ValidationError("Invalid data")
        assert error.context.category == ErrorCategory.VALIDATION
        assert error.context.severity == ErrorSeverity.LOW

    def test_external_service_error_constructor(self) -> None:
        """ExternalServiceError has correct category."""
        error = ExternalServiceError("External service failed")
        assert error.context.category == ErrorCategory.EXTERNAL
        assert error.context.severity == ErrorSeverity.HIGH

    def test_configuration_error_constructor(self) -> None:
        """ConfigurationError has correct category."""
        error = ConfigurationError("Invalid configuration")
        assert error.context.category == ErrorCategory.CONFIG
        assert error.context.severity == ErrorSeverity.HIGH


class TestExceptionSerialization:
    """Test serialize_exception function."""

    def test_serialize_exception_includes_cause(self) -> None:
        """serialize_exception captures exception cause chain."""
        try:
            try:
                raise RuntimeError("root")
            except RuntimeError as e:
                raise ValueError("leaf") from e
        except ValueError:
            info = sys.exc_info()
        data = serialize_exception(info, max_frames=10, max_stack_chars=2000)
        assert data.get("error.type") == "ValueError"
        assert data.get("error.cause") == "RuntimeError"
        assert "error.stack" in data

    def test_serialize_exception_empty_returns_empty_mapping(self) -> None:
        """serialize_exception returns empty dict for None input."""
        data = serialize_exception(None, max_frames=1, max_stack_chars=100)
        assert data == {}

    def test_serialize_exception_none_returns_empty(self) -> None:
        """serialize_exception returns empty dict for None."""
        out = serialize_exception(None, max_frames=5, max_stack_chars=1000)
        assert out == {}

    def test_serialize_exception_basic_fields_and_frame_limit(self) -> None:
        """serialize_exception captures basic fields with frame limit."""
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        out = serialize_exception(exc_info, max_frames=1, max_stack_chars=10_000)
        assert out.get("error.type") in {"ValueError", str(ValueError)}
        assert "error.message" in out
        frames = out.get("error.frames", [])
        assert isinstance(frames, list)
        assert len(frames) <= 1

    def test_serialize_exception_truncates_stack_string(self) -> None:
        """serialize_exception truncates stack to max_stack_chars."""
        try:

            def _a():
                def _b():
                    raise RuntimeError("deep")

                _b()

            _a()
        except RuntimeError:
            exc_info = sys.exc_info()
        out = serialize_exception(exc_info, max_frames=10, max_stack_chars=16)
        stack = out.get("error.stack", "")
        assert isinstance(stack, str)
        assert len(stack) <= 16
        assert stack.endswith("...")

    def test_serialize_exception_with_cause_and_context(self) -> None:
        """serialize_exception captures chained exception cause."""
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

    def test_serialize_exception_with_empty_traceback(self) -> None:
        """serialize_exception handles None traceback."""
        exc_info = (ValueError, ValueError("Test"), None)
        result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
        assert result.get("error.type") == "ValueError"
        assert "error.stack" in result

    def test_serialize_exception_with_exception_during_traceback_extraction(
        self,
    ) -> None:
        """serialize_exception handles traceback extraction failure."""
        with patch(
            "traceback.extract_tb", side_effect=RuntimeError("Extraction failed")
        ):
            try:
                raise ValueError("Test error")
            except ValueError:
                exc_info = sys.exc_info()

            result = serialize_exception(exc_info, max_frames=5, max_stack_chars=1000)
            assert result.get("error.type") == "ValueError"
            assert "error.stack" in result
            assert "error.frames" not in result


class TestUnhandledExceptionHooks:
    """Test unhandled exception hook functionality."""

    def test_capture_unhandled_exceptions_idempotent(self) -> None:
        """capture_unhandled_exceptions is idempotent."""
        mock_logger = Mock()
        capture_unhandled_exceptions(mock_logger)
        capture_unhandled_exceptions(mock_logger)
        assert sys.excepthook != sys.__excepthook__

    def test_capture_unhandled_exceptions_sys_hook(self) -> None:
        """capture_unhandled_exceptions installs sys.excepthook."""
        mock_logger = Mock()
        original_hook = sys.excepthook

        try:
            capture_unhandled_exceptions(mock_logger)
            assert callable(sys.excepthook)
        finally:
            sys.excepthook = original_hook

    def test_capture_unhandled_exceptions_no_event_loop(self) -> None:
        """capture_unhandled_exceptions handles missing event loop."""
        mock_logger = Mock()

        with patch("asyncio.get_event_loop", side_effect=RuntimeError("No loop")):
            capture_unhandled_exceptions(mock_logger)
            assert sys.excepthook != sys.__excepthook__
