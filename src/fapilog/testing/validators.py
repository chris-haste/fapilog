"""
Protocol validators for testing fapilog plugins.

Provides utilities to validate that plugins correctly implement their protocols.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of protocol validation."""

    valid: bool
    plugin_type: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.valid:
            raise ProtocolViolationError(
                f"Plugin violates {self.plugin_type} protocol: "
                + "; ".join(self.errors)
            )


class ProtocolViolationError(Exception):
    """Raised when a plugin violates its protocol."""

    pass


def validate_sink(sink: Any) -> ValidationResult:
    """Validate that a sink implements BaseSink protocol correctly.

    Checks:
    - Required 'name' attribute exists and is a string
    - Required methods exist and are async
    - Methods have correct signatures
    - Lifecycle methods don't raise on call
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check name attribute
    if not hasattr(sink, "name"):
        errors.append("Missing required 'name' attribute")
    elif not isinstance(getattr(sink, "name", None), str):
        errors.append("'name' attribute must be a string")

    # Check required methods
    required_methods = ["write"]
    for method_name in required_methods:
        if not hasattr(sink, method_name):
            errors.append(f"Missing required method: {method_name}")
            continue

        method = getattr(sink, method_name)
        if not asyncio.iscoroutinefunction(method):
            errors.append(f"{method_name} must be async")

    # Check optional lifecycle and health_check methods
    optional_methods = ["start", "stop", "health_check"]
    for method_name in optional_methods:
        if hasattr(sink, method_name):
            method = getattr(sink, method_name)
            if not asyncio.iscoroutinefunction(method):
                warnings.append(f"{method_name} should be async")
        elif method_name == "health_check":
            warnings.append("health_check not implemented; defaulting to healthy")

    # Informational: fast-path support
    if not hasattr(sink, "write_serialized"):
        warnings.append(
            "Sink does not implement write_serialized() fast path; "
            "consider adding it for serialize_in_flush=True"
        )

    # Check write signature
    if hasattr(sink, "write"):
        sig = inspect.signature(sink.write)
        params = list(sig.parameters.keys())
        if len(params) < 1 or (len(params) == 1 and params[0] == "self"):
            errors.append("write must accept entry parameter")

    return ValidationResult(
        valid=len(errors) == 0,
        plugin_type="BaseSink",
        errors=errors,
        warnings=warnings,
    )


def validate_enricher(enricher: Any) -> ValidationResult:
    """Validate that an enricher implements BaseEnricher protocol correctly."""
    errors: list[str] = []
    warnings: list[str] = []

    # Check name attribute
    if not hasattr(enricher, "name"):
        errors.append("Missing required 'name' attribute")
    elif not isinstance(getattr(enricher, "name", None), str):
        errors.append("'name' attribute must be a string")

    required_methods = ["enrich"]
    for method_name in required_methods:
        if not hasattr(enricher, method_name):
            errors.append(f"Missing required method: {method_name}")
            continue

        method = getattr(enricher, method_name)
        if not asyncio.iscoroutinefunction(method):
            errors.append(f"{method_name} must be async")

    # Check optional lifecycle and health_check methods
    optional_methods = ["start", "stop", "health_check"]
    for method_name in optional_methods:
        if hasattr(enricher, method_name):
            method = getattr(enricher, method_name)
            if not asyncio.iscoroutinefunction(method):
                warnings.append(f"{method_name} should be async")
        elif method_name == "health_check":
            warnings.append("health_check not implemented; defaulting to healthy")

    # Check enrich signature
    if hasattr(enricher, "enrich"):
        sig = inspect.signature(enricher.enrich)
        params = list(sig.parameters.keys())
        if "event" not in params and "entry" not in params:
            # Allow any parameter name
            pass

    return ValidationResult(
        valid=len(errors) == 0,
        plugin_type="BaseEnricher",
        errors=errors,
        warnings=warnings,
    )


def validate_redactor(redactor: Any) -> ValidationResult:
    """Validate that a redactor implements BaseRedactor protocol correctly."""
    errors: list[str] = []
    warnings: list[str] = []

    # Check name attribute
    if not hasattr(redactor, "name"):
        errors.append("Redactor must have 'name' attribute")

    required_methods = ["redact"]
    for method_name in required_methods:
        if not hasattr(redactor, method_name):
            errors.append(f"Missing required method: {method_name}")
            continue

        method = getattr(redactor, method_name)
        if not asyncio.iscoroutinefunction(method):
            errors.append(f"{method_name} must be async")

    # Check optional lifecycle and health_check methods
    optional_methods = ["start", "stop", "health_check"]
    for method_name in optional_methods:
        if hasattr(redactor, method_name):
            method = getattr(redactor, method_name)
            if not asyncio.iscoroutinefunction(method):
                warnings.append(f"{method_name} should be async")
        elif method_name == "health_check":
            warnings.append("health_check not implemented; defaulting to healthy")

    return ValidationResult(
        valid=len(errors) == 0,
        plugin_type="BaseRedactor",
        errors=errors,
        warnings=warnings,
    )


def validate_processor(processor: Any) -> ValidationResult:
    """Validate that a processor implements BaseProcessor protocol correctly."""
    errors: list[str] = []
    warnings: list[str] = []

    # Check name attribute
    if not hasattr(processor, "name"):
        errors.append("Missing required 'name' attribute")
    elif not isinstance(getattr(processor, "name", None), str):
        errors.append("'name' attribute must be a string")

    required_methods = ["process"]
    for method_name in required_methods:
        if not hasattr(processor, method_name):
            errors.append(f"Missing required method: {method_name}")
            continue

        method = getattr(processor, method_name)
        if not asyncio.iscoroutinefunction(method):
            errors.append(f"{method_name} must be async")

    optional_methods = ["start", "stop", "health_check", "process_many"]
    for method_name in optional_methods:
        if hasattr(processor, method_name):
            method = getattr(processor, method_name)
            if not asyncio.iscoroutinefunction(method):
                warnings.append(f"{method_name} should be async")
        elif method_name == "health_check":
            warnings.append("health_check not implemented; defaulting to healthy")

    return ValidationResult(
        valid=len(errors) == 0,
        plugin_type="BaseProcessor",
        errors=errors,
        warnings=warnings,
    )


def validate_filter(filter_plugin: Any) -> ValidationResult:
    """Validate that a filter implements BaseFilter protocol correctly."""
    errors: list[str] = []
    warnings: list[str] = []

    if not hasattr(filter_plugin, "name"):
        errors.append("Missing required 'name' attribute")
    elif not isinstance(getattr(filter_plugin, "name", None), str):
        errors.append("'name' attribute must be a string")

    required_methods = ["filter"]
    for method_name in required_methods:
        if not hasattr(filter_plugin, method_name):
            errors.append(f"Missing required method: {method_name}")
            continue
        method = getattr(filter_plugin, method_name)
        if not asyncio.iscoroutinefunction(method):
            errors.append(f"{method_name} must be async")

    optional_methods = ["start", "stop", "health_check"]
    for method_name in optional_methods:
        if hasattr(filter_plugin, method_name):
            method = getattr(filter_plugin, method_name)
            if not asyncio.iscoroutinefunction(method):
                warnings.append(f"{method_name} should be async")
        elif method_name == "health_check":
            warnings.append("health_check not implemented; defaulting to healthy")

    if hasattr(filter_plugin, "filter"):
        sig = inspect.signature(filter_plugin.filter)
        params = [param for name, param in sig.parameters.items() if name != "self"]
        if len(params) == 0:
            errors.append("filter must accept event parameter")

    return ValidationResult(
        valid=len(errors) == 0,
        plugin_type="BaseFilter",
        errors=errors,
        warnings=warnings,
    )


async def validate_plugin_lifecycle(plugin: Any) -> ValidationResult:
    """Validate that a plugin's lifecycle methods work correctly.

    Actually calls start() and stop() to verify they don't raise.
    """
    errors: list[str] = []
    warnings: list[str] = []
    plugin_type = "unknown"

    # Detect type
    if hasattr(plugin, "write"):
        plugin_type = "sink"
    elif hasattr(plugin, "enrich"):
        plugin_type = "enricher"
    elif hasattr(plugin, "redact"):
        plugin_type = "redactor"
    elif hasattr(plugin, "filter"):
        plugin_type = "filter"
    elif hasattr(plugin, "process"):
        plugin_type = "processor"

    # Test start
    if hasattr(plugin, "start"):
        try:
            await plugin.start()
        except Exception as e:
            errors.append(f"start() raised: {e}")

    # Test stop
    if hasattr(plugin, "stop"):
        try:
            await plugin.stop()
        except Exception as e:
            errors.append(f"stop() raised: {e}")

    # Test stop is idempotent
    if hasattr(plugin, "stop"):
        try:
            await plugin.stop()  # Second call should not raise
        except Exception as e:
            warnings.append(f"stop() not idempotent: {e}")

    return ValidationResult(
        valid=len(errors) == 0,
        plugin_type=plugin_type,
        errors=errors,
        warnings=warnings,
    )


# Mark as used for static analysis
_VULTURE_USED: tuple[object, ...] = (
    ValidationResult,
    ValidationResult.raise_if_invalid,
    ProtocolViolationError,
    validate_sink,
    validate_enricher,
    validate_redactor,
    validate_processor,
    validate_filter,
    validate_plugin_lifecycle,
)
