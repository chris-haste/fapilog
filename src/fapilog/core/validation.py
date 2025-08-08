"""
Pydantic Validation Patterns for Fapilog v3.

This module provides comprehensive validation patterns using Pydantic v2
with async field validation, quality gates, and enterprise compliance validation.
"""

import asyncio
import re
from typing import Any, Awaitable, Callable, Dict, List, Set

from pydantic import BaseModel, Field
from pydantic.functional_validators import AfterValidator

from .errors import ErrorSeverity, ValidationError


class ValidationRule(BaseModel):
    """Base validation rule definition."""

    name: str
    description: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    enabled: bool = True


class FieldValidationRule(ValidationRule):
    """Field-specific validation rule."""

    field_name: str
    validator_func: str  # Function name for validation
    validator_args: Dict[str, Any] = Field(default_factory=dict)


class ModelValidationRule(ValidationRule):
    """Model-level validation rule."""

    model_name: str
    validator_func: str  # Function name for validation
    dependencies: List[str] = Field(default_factory=list)


class AsyncValidator:
    """
    Async validation framework for configuration quality gates.

    Provides async validation capabilities for complex validation scenarios
    that require external service calls, file system access, or database queries.
    """

    def __init__(self) -> None:
        """Initialize async validator."""
        self._field_validators: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._model_validators: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {}
        self._validation_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    def register_field_validator(self, name: str, validator_func: Callable) -> None:
        """Register an async field validator."""
        self._field_validators[name] = validator_func

    def register_model_validator(self, name: str, validator_func: Callable) -> None:
        """Register an async model validator."""
        self._model_validators[name] = validator_func

    async def validate_field_async(
        self, field_name: str, value: Any, **kwargs: Any
    ) -> Any:
        """
        Validate a field value asynchronously.

        Args:
            field_name: Name of the field
            value: Value to validate
            **kwargs: Additional validation parameters

        Returns:
            Validated value

        Raises:
            ValidationError: If validation fails
        """
        # Check cache first
        cache_key = f"{field_name}:{hash(str(value))}"
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]

        # Find appropriate validator
        validator_func = self._field_validators.get(field_name)
        if not validator_func:
            return value  # No validator, pass through

        try:
            # Execute async validation
            validated_value = await validator_func(value, **kwargs)

            # Cache result
            self._validation_cache[cache_key] = validated_value

            return validated_value

        except Exception as e:
            raise ValidationError(
                f"Async validation failed for field '{field_name}': {e}",
                field_name=field_name,
                field_value=str(value),
                cause=e,
            ) from e

    async def validate_model_async(
        self, model_name: str, model_data: Dict[str, Any], **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Validate a model asynchronously.

        Args:
            model_name: Name of the model
            model_data: Model data to validate
            **kwargs: Additional validation parameters

        Returns:
            Validated model data

        Raises:
            ValidationError: If validation fails
        """
        validator_func = self._model_validators.get(model_name)
        if not validator_func:
            return model_data  # No validator, pass through

        try:
            # Execute async validation
            validated_data: Dict[str, Any] = await validator_func(model_data, **kwargs)
            return validated_data

        except Exception as e:
            raise ValidationError(
                f"Async model validation failed for '{model_name}': {e}",
                model_name=model_name,
                cause=e,
            ) from e

    def clear_cache(self) -> None:
        """Clear validation cache."""
        self._validation_cache.clear()


# Global async validator instance
_async_validator = AsyncValidator()


def get_async_validator() -> AsyncValidator:
    """Get global async validator instance."""
    return _async_validator


# Common validation patterns
def validate_url_format(url: str) -> str:
    """Validate URL format."""
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    if not url_pattern.match(url):
        raise ValueError(f"Invalid URL format: {url}")

    return url


def validate_port_number(port: int) -> int:
    """Validate port number range."""
    if not (1 <= port <= 65535):
        raise ValueError(f"Port number must be between 1 and 65535, got {port}")

    return port


def validate_file_path(path: str) -> str:
    """Validate file path format."""
    from pathlib import Path

    try:
        path_obj = Path(path)
        # Basic validation - ensure it's a valid path format
        str(path_obj.resolve())
        return path
    except Exception as e:
        raise ValueError(f"Invalid file path: {e}") from e


def validate_regex_pattern(pattern: str) -> str:
    """Validate regex pattern compilation."""
    try:
        re.compile(pattern)
        return pattern
    except re.error as e:
        raise ValueError(f"Invalid regex pattern '{pattern}': {e}") from e


def validate_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JSON schema format."""
    required_fields = ["type"]

    if not isinstance(schema, dict):
        raise ValueError("JSON schema must be a dictionary")

    for field in required_fields:
        if field not in schema:
            raise ValueError(f"JSON schema missing required field: {field}")

    return schema


# Async validation functions
async def validate_url_accessibility(url: str, timeout: float = 10.0) -> str:
    """Validate URL accessibility asynchronously."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.head(url)
            if response.status_code >= 400:
                raise ValueError(f"URL returned status {response.status_code}")
        return url
    except httpx.RequestError as e:
        raise ValueError(f"URL not accessible: {e}") from e


async def validate_file_exists(file_path: str) -> str:
    """Validate file existence asynchronously."""
    from pathlib import Path

    path = Path(file_path)
    exists = await asyncio.to_thread(path.exists)

    if not exists:
        raise ValueError(f"File does not exist: {file_path}")

    return file_path


async def validate_directory_writable(dir_path: str) -> str:
    """Validate directory write access asynchronously."""
    import tempfile
    from pathlib import Path

    path = Path(dir_path)

    # Check if directory exists
    exists = await asyncio.to_thread(path.exists)
    if not exists:
        raise ValueError(f"Directory does not exist: {dir_path}")

    # Check if it's a directory
    is_dir = await asyncio.to_thread(path.is_dir)
    if not is_dir:
        raise ValueError(f"Path is not a directory: {dir_path}")

    # Test write access
    try:
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
    except Exception as e:
        raise ValueError(f"Directory not writable: {e}") from e

    return dir_path


async def validate_database_connection(connection_string: str) -> str:
    """Validate database connection asynchronously."""
    # This is a placeholder - in real implementation, you would
    # attempt to connect to the database

    # Basic format validation
    if not connection_string.startswith(("postgresql://", "mysql://", "sqlite://")):
        raise ValueError("Unsupported database connection string format")

    # TODO: Implement actual connection testing
    return connection_string


# Register async validators
_async_validator.register_field_validator(
    "url_accessibility", validate_url_accessibility
)
_async_validator.register_field_validator("file_exists", validate_file_exists)
_async_validator.register_field_validator(
    "directory_writable", validate_directory_writable
)
_async_validator.register_field_validator(
    "database_connection", validate_database_connection
)


# Custom Pydantic validators
def create_url_validator() -> AfterValidator:
    """Create URL format validator."""
    return AfterValidator(validate_url_format)


def create_port_validator() -> AfterValidator:
    """Create port number validator."""
    return AfterValidator(validate_port_number)


def create_path_validator() -> AfterValidator:
    """Create file path validator."""
    return AfterValidator(validate_file_path)


def create_regex_validator() -> AfterValidator:
    """Create regex pattern validator."""
    return AfterValidator(validate_regex_pattern)


# Quality gate validators
class QualityGateValidator:
    """
    Quality gate validator for plugin and configuration validation.

    Implements quality gates that ensure configurations meet
    enterprise standards and best practices.
    """

    def __init__(self) -> None:
        """Initialize quality gate validator."""
        self._quality_rules: List[ValidationRule] = []
        self._thresholds: Dict[str, float] = {
            "security_score": 0.8,
            "performance_score": 0.7,
            "compliance_score": 0.9,
            "reliability_score": 0.8,
        }

    def add_quality_rule(self, rule: ValidationRule) -> None:
        """Add a quality gate rule."""
        self._quality_rules.append(rule)

    def set_threshold(self, metric: str, threshold: float) -> None:
        """Set quality threshold for a metric."""
        self._thresholds[metric] = threshold

    async def validate_configuration_quality(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate configuration against quality gates.

        Args:
            config_data: Configuration to validate

        Returns:
            Quality assessment results

        Raises:
            ValidationError: If quality gates fail
        """
        passed: bool = True
        scores: Dict[str, float] = {}
        violations: List[str] = []
        recommendations: List[str] = []

        # Security quality assessment
        security_score = await self._assess_security_quality(config_data)
        scores["security"] = security_score

        if security_score < self._thresholds["security_score"]:
            passed = False
            violations.append(
                f"Security score {security_score:.2f} below threshold {self._thresholds['security_score']:.2f}"
            )

        # Performance quality assessment
        performance_score = await self._assess_performance_quality(config_data)
        scores["performance"] = performance_score

        if performance_score < self._thresholds["performance_score"]:
            passed = False
            violations.append(
                f"Performance score {performance_score:.2f} below threshold {self._thresholds['performance_score']:.2f}"
            )

        # Compliance quality assessment
        compliance_score = await self._assess_compliance_quality(config_data)
        scores["compliance"] = compliance_score

        if compliance_score < self._thresholds["compliance_score"]:
            passed = False
            violations.append(
                f"Compliance score {compliance_score:.2f} below threshold {self._thresholds['compliance_score']:.2f}"
            )

        # Overall quality check
        if not passed:
            raise ValidationError(
                f"Configuration failed quality gates: {'; '.join(violations)}",
                quality_scores=scores,
                violations=violations,
            )

        return {
            "passed": passed,
            "scores": scores,
            "violations": violations,
            "recommendations": recommendations,
        }

    async def _assess_security_quality(self, config_data: Dict[str, Any]) -> float:
        """Assess security quality of configuration."""
        score = 1.0

        # Check for security features
        security_config = config_data.get("security", {})

        # Encryption assessment
        if not security_config.get("encryption_enabled", False):
            score -= 0.3

        # Authentication assessment
        if not security_config.get("authentication_enabled", False):
            score -= 0.2

        # Input validation assessment
        if not security_config.get("validate_input_schemas", True):
            score -= 0.2

        # Sensitive data masking
        if not security_config.get("mask_sensitive_fields", True):
            score -= 0.1

        return max(0.0, score)

    async def _assess_performance_quality(self, config_data: Dict[str, Any]) -> float:
        """Assess performance quality of configuration."""
        score = 1.0

        core_config = config_data.get("core", {})

        # Buffer size assessment
        buffer_size = core_config.get("buffer_size", 1000)
        if buffer_size < 100:
            score -= 0.2
        elif buffer_size > 50000:
            score -= 0.1

        # Async logging assessment
        if not core_config.get("async_logging", True):
            score -= 0.3

        # Circuit breaker assessment
        if not core_config.get("circuit_breaker_enabled", True):
            score -= 0.2

        return max(0.0, score)

    async def _assess_compliance_quality(self, config_data: Dict[str, Any]) -> float:
        """Assess compliance quality of configuration."""
        score = 1.0

        compliance_config = config_data.get("compliance", {})

        # Audit trail assessment
        if not compliance_config.get("audit_enabled", False):
            score -= 0.4

        # Data classification assessment
        if not compliance_config.get("data_classification_enabled", False):
            score -= 0.2

        # Retention policy assessment
        if not compliance_config.get("retention_policy_enabled", False):
            score -= 0.2

        return max(0.0, score)


# Global quality gate validator
_quality_gate_validator = QualityGateValidator()


def get_quality_gate_validator() -> QualityGateValidator:
    """Get global quality gate validator instance."""
    return _quality_gate_validator


# Compliance validation patterns
class ComplianceValidator:
    """
    Compliance validator for enterprise standards.

    Validates configurations against various compliance standards
    like SOX, PCI-DSS, SOC2, ISO27001, etc.
    """

    def __init__(self) -> None:
        """Initialize compliance validator."""
        self._standards: Dict[str, Callable] = {
            "sox": self._validate_sox_compliance,
            "pci_dss": self._validate_pci_dss_compliance,
            "soc2": self._validate_soc2_compliance,
            "iso27001": self._validate_iso27001_compliance,
            "hipaa": self._validate_hipaa_compliance,
            "gdpr": self._validate_gdpr_compliance,
        }

    async def validate_compliance(
        self, standards: Set[str], config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate configuration against compliance standards.

        Args:
            standards: Set of compliance standards to validate
            config_data: Configuration data

        Returns:
            Compliance validation results

        Raises:
            ValidationError: If compliance validation fails
        """
        compliant: bool = True
        standard_results: Dict[str, Dict[str, Any]] = {}
        violations: List[str] = []

        for standard in standards:
            if standard not in self._standards:
                violations.append(f"Unknown compliance standard: {standard}")
                compliant = False
                continue

            try:
                standard_result = await self._standards[standard](config_data)
                standard_results[standard] = standard_result

                if not standard_result["compliant"]:
                    compliant = False
                    violations.extend(standard_result["violations"])

            except Exception as e:
                violations.append(f"Error validating {standard}: {e}")
                compliant = False

        if not compliant:
            raise ValidationError(
                f"Configuration failed compliance validation: {'; '.join(violations)}",
                compliance_results={
                    "compliant": compliant,
                    "standard_results": standard_results,
                    "violations": violations,
                },
            )

        return {
            "compliant": compliant,
            "standard_results": standard_results,
            "violations": violations,
        }

    async def _validate_sox_compliance(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate SOX compliance requirements."""
        violations = []

        # SOX requires audit trails
        compliance_config = config_data.get("compliance", {})
        if not compliance_config.get("audit_enabled", False):
            violations.append("SOX requires audit trail to be enabled")

        # SOX requires data integrity
        if not compliance_config.get("audit_integrity_checks", False):
            violations.append("SOX requires audit integrity checks")

        # SOX requires access controls
        security_config = config_data.get("security", {})
        if not security_config.get("authentication_enabled", False):
            violations.append("SOX requires authentication to be enabled")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }

    async def _validate_pci_dss_compliance(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate PCI-DSS compliance requirements."""
        violations = []

        # PCI-DSS requires encryption
        security_config = config_data.get("security", {})
        if not security_config.get("encryption_enabled", False):
            violations.append("PCI-DSS requires encryption to be enabled")

        # PCI-DSS requires access controls
        if not security_config.get("authentication_enabled", False):
            violations.append("PCI-DSS requires authentication")

        # PCI-DSS requires data masking
        if not security_config.get("mask_sensitive_fields", True):
            violations.append("PCI-DSS requires sensitive data masking")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }

    async def _validate_soc2_compliance(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate SOC2 compliance requirements."""
        violations = []

        # SOC2 requires audit trails
        compliance_config = config_data.get("compliance", {})
        if not compliance_config.get("audit_enabled", False):
            violations.append("SOC2 requires audit trail")

        # SOC2 requires encryption
        security_config = config_data.get("security", {})
        if not security_config.get("encryption_enabled", False):
            violations.append("SOC2 requires encryption")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }

    async def _validate_iso27001_compliance(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate ISO27001 compliance requirements."""
        violations = []

        # ISO27001 requires comprehensive security controls
        security_config = config_data.get("security", {})
        if not security_config.get("encryption_enabled", False):
            violations.append("ISO27001 requires encryption")

        if not security_config.get("authentication_enabled", False):
            violations.append("ISO27001 requires authentication")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }

    async def _validate_hipaa_compliance(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate HIPAA compliance requirements."""
        violations = []

        # HIPAA requires encryption
        security_config = config_data.get("security", {})
        if not security_config.get("encryption_enabled", False):
            violations.append("HIPAA requires encryption for PHI")

        # HIPAA requires audit trails
        compliance_config = config_data.get("compliance", {})
        if not compliance_config.get("audit_enabled", False):
            violations.append("HIPAA requires audit trails")

        # HIPAA requires access controls
        if not security_config.get("authentication_enabled", False):
            violations.append("HIPAA requires access controls")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }

    async def _validate_gdpr_compliance(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate GDPR compliance requirements."""
        violations = []

        # GDPR requires data classification
        compliance_config = config_data.get("compliance", {})
        if not compliance_config.get("data_classification_enabled", False):
            violations.append("GDPR requires data classification")

        # GDPR requires PII detection
        if not compliance_config.get("pii_detection_enabled", False):
            violations.append("GDPR requires PII detection")

        # GDPR requires retention policies
        if not compliance_config.get("retention_policy_enabled", False):
            violations.append("GDPR requires data retention policies")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
        }


# Global compliance validator
_compliance_validator = ComplianceValidator()


def get_compliance_validator() -> ComplianceValidator:
    """Get global compliance validator instance."""
    return _compliance_validator
