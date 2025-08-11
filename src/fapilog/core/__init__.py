"""
Fapilog v3 Core Module.

This module provides the core async error handling hierarchy with comprehensive
features including circuit breakers, retry mechanisms, fallback patterns,
audit trails, and context preservation for enterprise-grade logging systems.
"""

from .access_control import AccessControlSettings, validate_access_control
from .audit import (
    AuditEvent,
    AuditEventType,
    AuditLogLevel,
    AuditTrail,
    ComplianceLevel,
    CompliancePolicy,
    audit_error,
    audit_security_event,
    get_audit_trail,
)
from .circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerManager,
    CircuitBreakerOpenError,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker_manager,
)
from .compliance import (
    AuditConfig,
    DataHandlingSettings,
    validate_audit_config,
    validate_compliance_policy,
    validate_data_handling,
)
from .concurrency import (
    AsyncBoundedExecutor,
    AsyncWorkStealingExecutor,
    BackpressurePolicy,
    LockFreeRingBuffer,
    NonBlockingRingQueue,
)
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
from .encryption import EncryptionSettings, validate_encryption_async
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
from .fallback import (
    AsyncFallbackWrapper,
    CacheFallback,
    ChainedFallback,
    FallbackConfig,
    FallbackError,
    FallbackManager,
    FallbackProvider,
    FallbackStrategy,
    FallbackTrigger,
    FunctionFallback,
    StaticValueFallback,
    fallback,
    get_fallback_manager,
    with_fallback,
)
from .marketplace import MarketplaceSettings
from .observability import ObservabilitySettings, validate_observability
from .plugin_config import (
    ValidationIssue,
    ValidationResult,
    check_dependencies,
    validate_plugin_configuration,
    validate_quality_gates,
)
from .retry import (
    DATABASE_RETRY_CONFIG,
    EXTERNAL_SERVICE_RETRY_CONFIG,
    # Predefined configurations
    NETWORK_RETRY_CONFIG,
    AsyncRetrier,
    JitterType,
    RetryConfig,
    RetryExhaustedError,
    RetryStrategy,
    retry,
    retry_async,
)
from .security import SecuritySettings, validate_security
from .settings import LATEST_CONFIG_SCHEMA_VERSION, CoreSettings, Settings

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
    "AsyncCircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerManager",
    "CircuitBreakerOpenError",
    "CircuitState",
    "circuit_breaker",
    "get_circuit_breaker_manager",
    # Retry mechanism
    "AsyncRetrier",
    "RetryConfig",
    "RetryExhaustedError",
    "RetryStrategy",
    "JitterType",
    "retry_async",
    "retry",
    "NETWORK_RETRY_CONFIG",
    "DATABASE_RETRY_CONFIG",
    "EXTERNAL_SERVICE_RETRY_CONFIG",
    # Fallback mechanisms
    "AsyncFallbackWrapper",
    "FallbackConfig",
    "FallbackError",
    "FallbackManager",
    "FallbackProvider",
    "FallbackStrategy",
    "FallbackTrigger",
    "StaticValueFallback",
    "FunctionFallback",
    "CacheFallback",
    "ChainedFallback",
    "fallback",
    "get_fallback_manager",
    "with_fallback",
    # Configuration
    "Settings",
    "CoreSettings",
    "SecuritySettings",
    "ObservabilitySettings",
    "EncryptionSettings",
    "AccessControlSettings",
    "LATEST_CONFIG_SCHEMA_VERSION",
    "load_settings",
    # Compliance configuration validation
    "AuditConfig",
    "DataHandlingSettings",
    "validate_compliance_policy",
    "validate_data_handling",
    "validate_audit_config",
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
    # Marketplace configuration
    "MarketplaceSettings",
    # Concurrency utilities
    "BackpressurePolicy",
    "AsyncBoundedExecutor",
    "AsyncWorkStealingExecutor",
    "LockFreeRingBuffer",
    "NonBlockingRingQueue",
    # Audit trails
    "AuditEvent",
    "AuditEventType",
    "AuditLogLevel",
    "AuditTrail",
    "ComplianceLevel",
    "CompliancePolicy",
    "audit_error",
    "audit_security_event",
    "get_audit_trail",
]
