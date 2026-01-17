"""
Fapilog v3 Core Module.

This module provides the core async error handling hierarchy with comprehensive
features including sink circuit breakers, retry mechanisms, and context
preservation for enterprise-grade logging systems.
"""

from .access_control import AccessControlSettings, validate_access_control
from .circuit_breaker import CircuitState, SinkCircuitBreaker, SinkCircuitBreakerConfig
from .concurrency import BackpressurePolicy, NonBlockingRingQueue
from .config import load_settings
from .context import (
    ContextManager,
    ExecutionContext,
    add_context_metadata,
    create_child_context,
    execution_context,
    get_context_manager,
    get_context_values,
    get_current_error_context,
    get_current_execution_context,
    increment_retry_count,
    preserve_context,
    set_circuit_breaker_state,
    with_component_context,
    with_context,
    with_request_context,
)
from .defaults import (
    get_default_log_level,
    is_ci_environment,
    is_tty_environment,
    should_fallback_sink,
)
from .encryption import EncryptionSettings, validate_encryption_async
from .environment import (
    EnvironmentType,
    detect_environment,
    get_environment_config,
)
from .errors import (
    AsyncErrorContext,
    AuthenticationError,
    AuthorizationError,
    ComponentError,
    ConfigurationError,
    # Specific error types
    ContainerError,
    # Error categories and enums
    ErrorCategory,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    ExternalServiceError,
    # Base error classes
    FapilogError,
    NetworkError,
    PluginError,
    PluginExecutionError,
    PluginLoadError,
    SinkWriteError,
    TimeoutError,
    ValidationError,
    container_id_var,
    create_error_context,
    get_error_context,
    # Context variables
    request_id_var,
    session_id_var,
    # Context functions
    set_error_context,
    user_id_var,
)
from .events import LogEvent
from .logger import DrainResult
from .observability import ObservabilitySettings, validate_observability
from .plugin_config import (
    ValidationIssue,
    ValidationResult,
    check_dependencies,
    validate_plugin_configuration,
    validate_quality_gates,
)
from .retry import (
    AsyncRetrier,
    RetryCallable,
    RetryConfig,
    RetryExhaustedError,
    retry_async,
)
from .security import SecuritySettings, validate_security
from .settings import LATEST_CONFIG_SCHEMA_VERSION, CoreSettings, Settings
from .types import (
    DurationField,
    OptionalDurationField,
    OptionalRotationDurationField,
    OptionalSizeField,
    RotationDurationField,
    SizeField,
)

__all__ = [
    # Error handling core
    "FapilogError",
    "AsyncErrorContext",
    "ErrorCategory",
    "ErrorSeverity",
    "ErrorRecoveryStrategy",
    # Specific error types
    "ContainerError",
    "ComponentError",
    "PluginError",
    "PluginLoadError",
    "PluginExecutionError",
    "SinkWriteError",
    "NetworkError",
    "TimeoutError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "ExternalServiceError",
    "ConfigurationError",
    # Context management
    "ExecutionContext",
    "ContextManager",
    "execution_context",
    "preserve_context",
    "with_context",
    "get_current_execution_context",
    "get_current_error_context",
    "add_context_metadata",
    "increment_retry_count",
    "set_circuit_breaker_state",
    "get_context_values",
    "create_child_context",
    "with_request_context",
    "with_component_context",
    "get_context_manager",
    # Context variables
    "request_id_var",
    "user_id_var",
    "session_id_var",
    "container_id_var",
    # Context functions
    "set_error_context",
    "get_error_context",
    "create_error_context",
    # Circuit breaker
    "CircuitState",
    "SinkCircuitBreaker",
    "SinkCircuitBreakerConfig",
    # Retry mechanism
    "AsyncRetrier",
    "RetryCallable",
    "RetryConfig",
    "RetryExhaustedError",
    "retry_async",
    # Configuration
    "Settings",
    "CoreSettings",
    "SecuritySettings",
    "ObservabilitySettings",
    "EncryptionSettings",
    "AccessControlSettings",
    "LATEST_CONFIG_SCHEMA_VERSION",
    "load_settings",
    "SizeField",
    "DurationField",
    "OptionalSizeField",
    "OptionalDurationField",
    "RotationDurationField",
    "OptionalRotationDurationField",
    "get_default_log_level",
    "is_ci_environment",
    "is_tty_environment",
    "should_fallback_sink",
    # Environment detection (Story 10.8)
    "EnvironmentType",
    "detect_environment",
    "get_environment_config",
    # Plugin configuration validation
    "ValidationIssue",
    "ValidationResult",
    "validate_quality_gates",
    "validate_plugin_configuration",
    "check_dependencies",
    # Security & Observability validation
    "validate_security",
    "validate_observability",
    "validate_encryption_async",
    "validate_access_control",
    # Concurrency utilities
    "BackpressurePolicy",
    "NonBlockingRingQueue",
    # Event model and drain result
    "LogEvent",
    "DrainResult",
]
