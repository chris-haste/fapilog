"""
Standardized Error Types with Async Context Preservation for Fapilog v3.

This module provides comprehensive error handling with context preservation,
categorization, and enterprise compliance support for async operations.
"""

import asyncio
import contextvars
import time
import traceback
from datetime import datetime, timezone
from enum import Enum
from types import TracebackType
from typing import Any, Dict, List, Optional, Tuple, Type
from uuid import uuid4

from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Error severity levels for categorization and handling."""

    CRITICAL = "critical"  # System failure, immediate attention required
    HIGH = "high"  # Significant impact, requires urgent attention
    MEDIUM = "medium"  # Moderate impact, should be addressed soon
    LOW = "low"  # Minor impact, can be addressed in normal cycle
    INFO = "info"  # Informational, no action required


class ErrorCategory(str, Enum):
    """Error categories for systematic error handling."""

    # System errors
    SYSTEM = "system"  # Core system errors
    CONTAINER = "container"  # Container lifecycle errors
    COMPONENT = "component"  # Component management errors

    # Plugin errors
    PLUGIN_LOAD = "plugin_load"  # Plugin loading failures
    PLUGIN_EXEC = "plugin_exec"  # Plugin execution failures
    PLUGIN_CONFIG = "plugin_config"  # Plugin configuration errors

    # Network and I/O errors
    NETWORK = "network"  # Network connectivity issues
    IO = "io"  # File system and I/O errors
    TIMEOUT = "timeout"  # Operation timeout errors

    # Authentication and authorization
    AUTH = "auth"  # Authentication failures
    AUTHZ = "authz"  # Authorization failures

    # Data and validation errors
    VALIDATION = "validation"  # Data validation errors
    SERIALIZATION = "serialization"  # Data serialization errors

    # External dependencies
    EXTERNAL = "external"  # External service errors
    DATABASE = "database"  # Database operation errors

    # Configuration and setup
    CONFIG = "config"  # Configuration errors
    SETUP = "setup"  # Setup and initialization errors


class ErrorRecoveryStrategy(str, Enum):
    """Recovery strategies for different error types."""

    NONE = "none"  # No automatic recovery
    RETRY = "retry"  # Retry with backoff
    FALLBACK = "fallback"  # Use fallback mechanism
    CIRCUIT_BREAKER = "circuit_breaker"  # Apply circuit breaker
    RESTART = "restart"  # Restart component/service
    ESCALATE = "escalate"  # Escalate to higher level


class AsyncErrorContext(BaseModel):
    """Context information for async errors with full traceability."""

    # Error identification
    error_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Error details
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.NONE

    # Context preservation
    task_name: Optional[str] = None
    coroutine_name: Optional[str] = None
    call_stack: List[str] = Field(default_factory=list)

    # User and session context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None

    # System context
    container_id: Optional[str] = None
    component_name: Optional[str] = None
    plugin_name: Optional[str] = None

    # Performance context
    operation_start_time: Optional[float] = None
    operation_duration: Optional[float] = None

    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class FapilogError(Exception):
    """
    Base error class for all Fapilog errors with async context preservation.

    This base class provides:
    - Automatic context capture in async environments
    - Error categorization and severity levels
    - Recovery strategy hints
    - Enterprise compliance support
    - Context preservation across async operations
    """

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.NONE,
        error_context: Optional[AsyncErrorContext] = None,
        cause: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Fapilog error with comprehensive context.

        Args:
            message: Human-readable error message
            category: Error category for systematic handling
            severity: Error severity level
            recovery_strategy: Suggested recovery strategy
            error_context: Pre-built error context (optional)
            cause: Original exception that caused this error
            **kwargs: Additional context metadata
        """
        super().__init__(message)

        # Create or update error context
        if error_context is None:
            error_context = AsyncErrorContext(
                category=category,
                severity=severity,
                recovery_strategy=recovery_strategy,
            )

        # Capture async context
        self._capture_async_context(error_context)

        # Add metadata from kwargs
        error_context.metadata.update(kwargs)

        # Store cause and context
        self.__cause__ = cause
        self.context = error_context
        self.message = message

    def _capture_async_context(self, context: AsyncErrorContext) -> None:
        """Capture current async context for error traceability."""
        try:
            # Get current task information
            try:
                current_task = asyncio.current_task()
                if current_task:
                    context.task_name = current_task.get_name()
                    # Extract coroutine name if available
                    if hasattr(current_task, "_coro"):
                        context.coroutine_name = getattr(
                            current_task._coro, "__name__", None
                        )
            except RuntimeError:
                # No event loop running
                pass

            # Capture call stack
            context.call_stack = traceback.format_stack()

            # Capture timing information
            context.operation_start_time = time.time()

            # Try to get context variables if available
            try:
                context_vars = [
                    ("request_id", request_id_var),
                    ("user_id", user_id_var),
                    ("session_id", session_id_var),
                    ("container_id", container_id_var),
                ]

                for var_name, var in context_vars:
                    try:
                        value = var.get(None)
                        if value:
                            setattr(context, var_name, value)
                    except LookupError:
                        continue
            except Exception:
                # Context variable access failed, continue without
                pass

        except Exception:
            # Context capture should never fail the main error
            pass

    def with_context(self, **kwargs: Any) -> "FapilogError":
        """Add additional context to the error."""
        self.context.metadata.update(kwargs)
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging and serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "context": self.context.model_dump(),
            "cause": str(self.__cause__) if self.__cause__ else None,
        }


class ContainerError(FapilogError):
    """Errors related to container lifecycle and management."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.CONTAINER,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.RESTART,
            **kwargs,
        )


class ComponentError(FapilogError):
    """Errors related to component management and lifecycle."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.COMPONENT,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=ErrorRecoveryStrategy.RETRY,
            **kwargs,
        )


class PluginError(FapilogError):
    """Base class for plugin-related errors."""

    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        recovery_strategy: Optional[ErrorRecoveryStrategy] = None,
        **kwargs: Any,
    ) -> None:
        # Use provided values or defaults
        if category is None:
            category = ErrorCategory.PLUGIN_EXEC
        if severity is None:
            severity = ErrorSeverity.MEDIUM
        if recovery_strategy is None:
            recovery_strategy = ErrorRecoveryStrategy.FALLBACK

        super().__init__(
            message,
            category=category,
            severity=severity,
            recovery_strategy=recovery_strategy,
            **kwargs,
        )
        if plugin_name:
            self.context.plugin_name = plugin_name


class PluginLoadError(PluginError):
    """Errors during plugin loading and initialization."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.PLUGIN_LOAD,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            **kwargs,
        )


class PluginExecutionError(PluginError):
    """Errors during plugin execution."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.PLUGIN_EXEC,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=ErrorRecoveryStrategy.FALLBACK,
            **kwargs,
        )


class NetworkError(FapilogError):
    """Network connectivity and communication errors."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.RETRY,
            **kwargs,
        )


class TimeoutError(FapilogError):
    """Operation timeout errors."""

    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message,
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=ErrorRecoveryStrategy.RETRY,
            **kwargs,
        )
        if timeout_duration:
            self.context.metadata["timeout_duration"] = timeout_duration


class ValidationError(FapilogError):
    """Data validation and schema errors."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            **kwargs,
        )


class BackpressureError(FapilogError):
    """Backpressure condition encountered (queue/full or timeout)."""

    def __init__(self, message: str, **kwargs: Any) -> None:  # noqa: D401
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.RETRY,
            **kwargs,
        )


class AuthenticationError(FapilogError):
    """Authentication failures."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.AUTH,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            **kwargs,
        )


class AuthorizationError(FapilogError):
    """Authorization failures."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.AUTHZ,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            **kwargs,
        )


class ExternalServiceError(FapilogError):
    """Errors from external service dependencies."""

    def __init__(
        self, message: str, service_name: Optional[str] = None, **kwargs: Any
    ) -> None:
        super().__init__(
            message,
            category=ErrorCategory.EXTERNAL,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.CIRCUIT_BREAKER,
            **kwargs,
        )
        if service_name:
            self.context.metadata["service_name"] = service_name


class ConfigurationError(FapilogError):
    """Configuration and setup errors."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            category=ErrorCategory.CONFIG,
            severity=ErrorSeverity.HIGH,
            recovery_strategy=ErrorRecoveryStrategy.NONE,
            **kwargs,
        )


# Context variables for tracking error context across async operations
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
session_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("session_id")
container_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("container_id")
tenant_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("tenant_id")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id")
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("span_id")


def set_error_context(
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    container_id: Optional[str] = None,
) -> None:
    """Set error context variables for automatic context preservation."""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if session_id:
        session_id_var.set(session_id)
    if container_id:
        container_id_var.set(container_id)


def get_error_context() -> Dict[str, Optional[str]]:
    """Get current error context variables."""
    return {
        "request_id": request_id_var.get(None),
        "user_id": user_id_var.get(None),
        "session_id": session_id_var.get(None),
        "container_id": container_id_var.get(None),
    }


def create_error_context(
    category: ErrorCategory,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.NONE,
    **kwargs: Any,
) -> AsyncErrorContext:
    """Create error context with current async environment information."""
    context = AsyncErrorContext(
        category=category,
        severity=severity,
        recovery_strategy=recovery_strategy,
    )

    # Add current context variables
    current_context = get_error_context()
    for key, value in current_context.items():
        if value:
            setattr(context, key, value)

    # Add additional metadata
    context.metadata.update(kwargs)

    return context


def serialize_exception(
    exc_info: Optional[
        Tuple[
            Optional[Type[BaseException]],
            Optional[BaseException],
            Optional[TracebackType],
        ]
    ],
    *,
    max_frames: int,
    max_stack_chars: int,
) -> Dict[str, Any]:
    """Serialize an exception tuple into a structured mapping.

    Returns an empty dict if exc_info is None. Defensive against errors.
    """
    if not exc_info:
        return {}
    try:
        etype, evalue, etb = exc_info
        # Best-effort type extraction
        type_name = getattr(etype, "__name__", None) if etype is not None else None
        data: Dict[str, Any] = {
            "error.type": type_name or str(etype),
            "error.message": str(evalue),
        }
        stack_str = "".join(traceback.format_exception(etype, evalue, etb))
        if len(stack_str) > max_stack_chars:
            stack_str = stack_str[: max_stack_chars - 3] + "..."
        data["error.stack"] = stack_str
        frames: List[Dict[str, Any]] = []
        try:
            tb_frames = traceback.extract_tb(etb)
            for fr in tb_frames[:max_frames]:
                frames.append(
                    {
                        "file": fr.filename,
                        "line": fr.lineno,
                        "function": fr.name,
                        "code": fr.line,
                    }
                )
        except Exception:
            pass
        if frames:
            data["error.frames"] = frames
        cause = getattr(evalue, "__cause__", None) or getattr(
            evalue,
            "__context__",
            None,
        )
        if cause is not None:
            data["error.cause"] = type(cause).__name__
        return data
    except Exception:
        return {}


# Cache-specific error classes
class CacheError(FapilogError):
    """Base class for cache-related errors."""

    def __init__(
        self,
        message: str,
        error_context: Optional[AsyncErrorContext] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            recovery_strategy=ErrorRecoveryStrategy.FALLBACK,
            error_context=error_context
            or create_error_context(
                ErrorCategory.SYSTEM,
                ErrorSeverity.MEDIUM,
                ErrorRecoveryStrategy.FALLBACK,
            ),
            cause=cause,
        )


class CacheMissError(CacheError):
    """Raised when a cache key is not found."""

    def __init__(
        self,
        key: str,
        error_context: Optional[AsyncErrorContext] = None,
    ) -> None:
        super().__init__(
            f"Cache key not found: {key}",
            error_context=error_context
            or create_error_context(
                ErrorCategory.SYSTEM,
                ErrorSeverity.LOW,
                ErrorRecoveryStrategy.FALLBACK,
            ),
        )
        self.cache_key = key


class CacheOperationError(CacheError):
    """Raised when a cache operation fails."""

    def __init__(
        self,
        operation: str,
        key: str,
        error_context: Optional[AsyncErrorContext] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            f"Cache operation '{operation}' failed for key '{key}'",
            error_context=error_context
            or create_error_context(
                ErrorCategory.SYSTEM,
                ErrorSeverity.MEDIUM,
                ErrorRecoveryStrategy.FALLBACK,
            ),
            cause=cause,
        )
        self.operation = operation
        self.cache_key = key


class CacheCapacityError(CacheError):
    """Raised when cache capacity is exceeded."""

    def __init__(
        self,
        key: str,
        current_size: int,
        capacity: int,
        error_context: Optional[AsyncErrorContext] = None,
    ) -> None:
        super().__init__(
            f"Cache capacity exceeded: {current_size}/{capacity}",
            error_context=error_context
            or create_error_context(
                ErrorCategory.SYSTEM,
                ErrorSeverity.MEDIUM,
                ErrorRecoveryStrategy.FALLBACK,
            ),
        )
        self.cache_key = key
        self.current_size = current_size
        self.capacity = capacity


# Unhandled exception hooks (optional)
_unhandled_installed: bool = False
_prev_sys_excepthook = None
_prev_asyncio_handler = None


def capture_unhandled_exceptions(logger: Any) -> None:
    """Install unhandled exception hooks for sync and asyncio contexts.

    Idempotent: safe to call multiple times. Non-blocking in asyncio handler.
    """
    global _unhandled_installed, _prev_sys_excepthook, _prev_asyncio_handler
    if _unhandled_installed:
        return
    _unhandled_installed = True

    import asyncio as _asyncio
    import sys as _sys

    # Sync: sys.excepthook
    _prev_sys_excepthook = getattr(_sys, "excepthook", None)

    def _sys_hook(
        etype: Type[BaseException], value: BaseException, tb: TracebackType
    ) -> None:
        try:
            logger.error(
                "unhandled_exception",
                exc_info=(etype, value, tb),
                origin="sys.excepthook",
            )
        except Exception:
            pass
        # Delegate to previous hook if present
        try:
            if callable(_prev_sys_excepthook):
                _prev = _prev_sys_excepthook
                _prev(etype, value, tb)
        except Exception:
            pass

    _sys.excepthook = _sys_hook  # type: ignore[assignment]

    # Async: event loop exception handler
    try:
        loop = _asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        _prev_asyncio_handler = loop.get_exception_handler()

        def _async_handler(
            _loop: _asyncio.AbstractEventLoop, context: Dict[str, Any]
        ) -> None:
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
                    # Log synchronously; logger enqueues to background worker
                    logger.error("unhandled_task_exception", exc=exc)
                except Exception:
                    pass
            # Delegate to previous handler if present
            try:
                if callable(_prev_asyncio_handler):
                    _prev_asyncio_handler(_loop, context)
            except Exception:
                pass

        try:
            loop.set_exception_handler(_async_handler)
        except Exception:
            pass
