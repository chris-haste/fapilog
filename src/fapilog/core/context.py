"""
Error Context Preservation in Async Operations for Fapilog v3.

This module provides comprehensive context preservation across async operations
including execution context, user context, system context, and error propagation.
"""

import asyncio
import contextvars
import functools
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Tuple,
    TypeVar,
)
from uuid import uuid4

from .errors import (
    AsyncErrorContext,
    ErrorCategory,
    ErrorSeverity,
    FapilogError,
    container_id_var,
    create_error_context,
    request_id_var,
    session_id_var,
    user_id_var,
)

T = TypeVar("T")


# Context variables are now imported above

# Additional context variables specific to execution context
execution_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("execution_id")
component_name_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "component_name"
)
operation_name_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "operation_name"
)

# Performance and timing context
operation_start_time_var: contextvars.ContextVar[float] = contextvars.ContextVar(
    "operation_start_time"
)
parent_execution_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "parent_execution_id"
)

# Error propagation context
error_chain_var: contextvars.ContextVar[list] = contextvars.ContextVar("error_chain")
retry_count_var: contextvars.ContextVar[int] = contextvars.ContextVar("retry_count")
circuit_breaker_state_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "circuit_breaker_state"
)


@dataclass
class ExecutionContext:
    """Complete execution context for async operations."""

    # Execution identification
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    parent_execution_id: Optional[str] = None

    # Request context
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # System context
    container_id: Optional[str] = None
    component_name: Optional[str] = None
    operation_name: Optional[str] = None

    # Timing context
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    # Error context
    error_chain: list = field(default_factory=list)
    retry_count: int = 0
    circuit_breaker_state: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> Optional[float]:
        """Get execution duration if completed."""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def is_completed(self) -> bool:
        """Check if execution is completed."""
        return self.end_time is not None

    def complete(self) -> None:
        """Mark execution as completed."""
        if not self.end_time:
            self.end_time = time.time()

    def add_error(self, error: Exception) -> None:
        """Add error to the error chain."""
        error_info = {
            "timestamp": time.time(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "execution_id": self.execution_id,
        }

        if isinstance(error, FapilogError):
            error_info.update(
                {
                    "error_id": error.context.error_id,
                    "category": error.context.category.value,
                    "severity": error.context.severity.value,
                }
            )

        self.error_chain.append(error_info)

    def to_error_context(
        self,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> AsyncErrorContext:
        """Convert to AsyncErrorContext."""
        context = AsyncErrorContext(
            category=category,
            severity=severity,
            user_id=self.user_id,
            session_id=self.session_id,
            request_id=self.request_id,
            container_id=self.container_id,
            component_name=self.component_name,
            operation_start_time=self.start_time,
        )

        if self.duration:
            context.operation_duration = self.duration

        # Add metadata
        context.metadata.update(self.metadata)
        context.metadata.update(
            {
                "execution_id": self.execution_id,
                "parent_execution_id": self.parent_execution_id,
                "retry_count": self.retry_count,
                "circuit_breaker_state": self.circuit_breaker_state,
                "error_chain_length": len(self.error_chain),
            }
        )

        return context


class ContextManager:
    """
    Manager for execution context preservation across async operations.

    This manager provides:
    - Automatic context propagation across async calls
    - Context isolation between different execution paths
    - Error context preservation and propagation
    - Performance monitoring and timing
    - Integration with container and component systems
    """

    def __init__(self) -> None:
        """Initialize context manager."""
        self._active_contexts: Dict[str, ExecutionContext] = {}
        self._context_hierarchy: Dict[str, str] = {}  # child -> parent mapping
        self._lock = asyncio.Lock()

    async def create_context(
        self,
        *,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        container_id: Optional[str] = None,
        component_name: Optional[str] = None,
        operation_name: Optional[str] = None,
        parent_execution_id: Optional[str] = None,
        **metadata: Any,
    ) -> ExecutionContext:
        """
        Create new execution context.

        Args:
            request_id: Request identifier
            user_id: User identifier
            session_id: Session identifier
            container_id: Container identifier
            component_name: Component name
            operation_name: Operation name
            parent_execution_id: Parent execution identifier
            **metadata: Additional metadata

        Returns:
            New execution context
        """
        # Get parent context if not provided
        if parent_execution_id is None:
            try:
                parent_execution_id = execution_id_var.get(None)
            except LookupError:
                pass

        # Create context
        context = ExecutionContext(
            parent_execution_id=parent_execution_id,
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            container_id=container_id,
            component_name=component_name,
            operation_name=operation_name,
            metadata=metadata,
        )

        # Register context
        async with self._lock:
            self._active_contexts[context.execution_id] = context
            if parent_execution_id:
                self._context_hierarchy[context.execution_id] = parent_execution_id

        return context

    async def get_context(self, execution_id: str) -> Optional[ExecutionContext]:
        """Get execution context by ID."""
        return self._active_contexts.get(execution_id)

    async def get_current_context(self) -> Optional[ExecutionContext]:
        """Get current execution context."""
        try:
            execution_id = execution_id_var.get()
            return await self.get_context(execution_id)
        except LookupError:
            return None

    async def complete_context(self, execution_id: str) -> None:
        """Mark context as completed and clean up."""
        context = self._active_contexts.get(execution_id)
        if context:
            context.complete()

            # Clean up after some time (keep for debugging)
            asyncio.create_task(self._cleanup_context_later(execution_id))

    async def _cleanup_context_later(
        self, execution_id: str, delay: float = 300.0
    ) -> None:
        """Clean up context after delay."""
        await asyncio.sleep(delay)
        async with self._lock:
            self._active_contexts.pop(execution_id, None)
            self._context_hierarchy.pop(execution_id, None)

    async def add_error_to_current_context(self, error: Exception) -> None:
        """Add error to current execution context."""
        context = await self.get_current_context()
        if context:
            context.add_error(error)

    async def get_context_chain(self, execution_id: str) -> list[ExecutionContext]:
        """Get full context chain from root to current."""
        chain = []
        current_id: Optional[str] = execution_id

        while current_id:
            context = await self.get_context(current_id)
            if context:
                chain.append(context)
            current_id = self._context_hierarchy.get(current_id)

        return list(reversed(chain))  # Root to current

    async def get_statistics(self) -> Dict[str, Any]:
        """Get context manager statistics."""
        async with self._lock:
            return {
                "active_contexts": len(self._active_contexts),
                "context_hierarchy_size": len(self._context_hierarchy),
                "total_contexts_created": len(self._active_contexts),  # Simplified
            }


# Global context manager
_context_manager: Optional[ContextManager] = None


async def get_context_manager() -> ContextManager:
    """Get global context manager."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


@asynccontextmanager
async def execution_context(
    *,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    container_id: Optional[str] = None,
    component_name: Optional[str] = None,
    operation_name: Optional[str] = None,
    **metadata: Any,
) -> AsyncIterator[ExecutionContext]:
    """
    Async context manager for execution context.

    Usage:
        async with execution_context(operation_name="my_operation") as ctx:
            # Your async operation here
            pass
    """
    manager = await get_context_manager()

    # Create context
    context = await manager.create_context(
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        container_id=container_id,
        component_name=component_name,
        operation_name=operation_name,
        **metadata,
    )

    # Set context variables
    token_execution_id = execution_id_var.set(context.execution_id)
    token_request_id = None
    token_user_id = None
    token_session_id = None
    token_container_id = None
    token_component_name = None
    token_operation_name = None
    token_start_time = operation_start_time_var.set(context.start_time)

    try:
        if context.request_id:
            token_request_id = request_id_var.set(context.request_id)
        if context.user_id:
            token_user_id = user_id_var.set(context.user_id)
        if context.session_id:
            token_session_id = session_id_var.set(context.session_id)
        if context.container_id:
            token_container_id = container_id_var.set(context.container_id)
        if context.component_name:
            token_component_name = component_name_var.set(context.component_name)
        if context.operation_name:
            token_operation_name = operation_name_var.set(context.operation_name)

        yield context

    except Exception as e:
        # Add error to context
        context.add_error(e)
        raise
    finally:
        # Complete context
        await manager.complete_context(context.execution_id)

        # Reset context variables
        execution_id_var.reset(token_execution_id)
        operation_start_time_var.reset(token_start_time)

        if token_request_id:
            request_id_var.reset(token_request_id)
        if token_user_id:
            user_id_var.reset(token_user_id)
        if token_session_id:
            session_id_var.reset(token_session_id)
        if token_container_id:
            container_id_var.reset(token_container_id)
        if token_component_name:
            component_name_var.reset(token_component_name)
        if token_operation_name:
            operation_name_var.reset(token_operation_name)


def preserve_context(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """
    Decorator to preserve execution context across async function calls.

    Usage:
        @preserve_context
        async def my_function():
            # Context variables are automatically preserved
            pass
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        # Copy current context
        current_context = contextvars.copy_context()

        # Run function in copied context
        async def _run_in_context() -> Any:
            return await func(*args, **kwargs)

        return await current_context.run(lambda: asyncio.create_task(_run_in_context()))

    return wrapper


async def get_current_execution_context() -> Optional[ExecutionContext]:
    """Get current execution context."""
    manager = await get_context_manager()
    return await manager.get_current_context()


async def get_current_error_context(
    category: ErrorCategory = ErrorCategory.SYSTEM,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
) -> AsyncErrorContext:
    """
    Get current error context for creating FapilogError.

    Args:
        category: Error category
        severity: Error severity

    Returns:
        AsyncErrorContext with current context information
    """
    execution_context = await get_current_execution_context()

    if execution_context:
        return execution_context.to_error_context(category, severity)
    else:
        # Fallback to basic context creation
        return create_error_context(category, severity)


def with_context(**context_vars: Any) -> Callable:
    """
    Decorator to set context variables for a function.

    Usage:
        @with_context(component_name="my_component", operation_name="my_operation")
        async def my_function():
            pass
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with execution_context(**context_vars):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


async def add_context_metadata(**metadata: Any) -> None:
    """Add metadata to current execution context."""
    context = await get_current_execution_context()
    if context:
        context.metadata.update(metadata)


async def increment_retry_count() -> int:
    """Increment retry count in current context."""
    try:
        current_count = retry_count_var.get()
        new_count = current_count + 1
        retry_count_var.set(new_count)

        # Also update execution context
        context = await get_current_execution_context()
        if context:
            context.retry_count = new_count

        return new_count
    except LookupError:
        retry_count_var.set(1)
        return 1


async def set_circuit_breaker_state(state: str) -> None:
    """Set circuit breaker state in current context."""
    circuit_breaker_state_var.set(state)

    # Also update execution context
    context = await get_current_execution_context()
    if context:
        context.circuit_breaker_state = state


def get_context_values() -> Dict[str, Any]:
    """Get all current context variable values."""
    values = {}

    context_vars: list[Tuple[str, contextvars.ContextVar[Any]]] = [
        ("execution_id", execution_id_var),
        ("request_id", request_id_var),
        ("user_id", user_id_var),
        ("session_id", session_id_var),
        ("container_id", container_id_var),
        ("component_name", component_name_var),
        ("operation_name", operation_name_var),
        ("operation_start_time", operation_start_time_var),
        ("parent_execution_id", parent_execution_id_var),
        ("retry_count", retry_count_var),
        ("circuit_breaker_state", circuit_breaker_state_var),
    ]

    for name, var in context_vars:
        try:
            values[name] = var.get()
        except LookupError:
            values[name] = None

    return values


@asynccontextmanager
async def create_child_context(
    operation_name: str, **additional_context: Any
) -> AsyncIterator[ExecutionContext]:
    """
    Create child execution context for sub-operations.

    Args:
        operation_name: Name of the child operation
        **additional_context: Additional context variables

    Yields:
        Child execution context
    """
    # Get current context values
    current_values = get_context_values()

    # Create child context with current values as parent
    async with execution_context(
        request_id=current_values.get("request_id"),
        user_id=current_values.get("user_id"),
        session_id=current_values.get("session_id"),
        container_id=current_values.get("container_id"),
        component_name=current_values.get("component_name"),
        operation_name=operation_name,
        **additional_context,
    ) as ctx:
        yield ctx


# Convenience functions for common patterns
@asynccontextmanager
async def with_request_context(
    request_id: str, user_id: Optional[str] = None, session_id: Optional[str] = None
) -> AsyncIterator[ExecutionContext]:
    """Create context for request handling."""
    async with execution_context(
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        operation_name="request_handling",
    ) as ctx:
        yield ctx


@asynccontextmanager
async def with_component_context(
    component_name: str,
    container_id: Optional[str] = None,
    operation_name: Optional[str] = None,
) -> AsyncIterator[ExecutionContext]:
    """Create context for component operations."""
    async with execution_context(
        component_name=component_name,
        container_id=container_id,
        operation_name=operation_name or f"{component_name}_operation",
    ) as ctx:
        yield ctx
