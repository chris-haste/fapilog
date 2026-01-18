"""
Enterprise compliance configuration validation for Fapilog v3.

Validates compliance policies, data handling, and audit configurations against
baseline enterprise expectations. Uses lightweight rules (not legal guidance).
"""

from __future__ import annotations

from fapilog.core.plugin_config import ValidationIssue, ValidationResult

# Note: No Optional imports currently needed
from pydantic import BaseModel, Field

from .audit import ComplianceLevel, CompliancePolicy


class DataHandlingSettings(BaseModel):
    """Settings for sensitive data handling and controls."""

    pii_redaction_enabled: bool = Field(default=True)
    phi_redaction_enabled: bool = Field(default=False)
    encryption_at_rest: bool = Field(default=True)
    encryption_in_transit: bool = Field(default=True)
    allow_default_credentials: bool = Field(default=False)
    min_password_length: int = Field(default=12, ge=8)
    allowed_data_classifications: list[str] = Field(
        default_factory=lambda: [
            "public",
            "internal",
            "confidential",
            "restricted",
        ]
    )


class AuditConfig(BaseModel):
    """Audit trail-specific configuration validation envelope."""

    policy: CompliancePolicy


def _require(
    condition: bool, field: str, message: str, result: ValidationResult
) -> None:
    """Append an error issue if condition is False."""
    if not condition:
        result.add_issue(ValidationIssue(field=field, message=message))


def validate_compliance_policy(policy: CompliancePolicy) -> ValidationResult:
    """Validate a CompliancePolicy against baseline enterprise rules.

    This function is automatically called during AuditTrail.start() when the
    policy is enabled. Validation issues are emitted as warnings rather than
    errors, allowing the audit trail to start while alerting users to
    potential compliance gaps.

    You can also call this function directly for pre-flight checks or testing:

        from fapilog_audit import (
            validate_compliance_policy,
            CompliancePolicy,
            ComplianceLevel,
        )

        policy = CompliancePolicy(level=ComplianceLevel.HIPAA, ...)
        result = validate_compliance_policy(policy)
        if not result.ok:
            for issue in result.issues:
                print(f"{issue.field}: {issue.message}")

    Validated rules:
        - retention_days >= 30
        - archive_after_days >= 7
        - require_integrity_check must be True
        - Framework-specific requirements (HIPAA, GDPR, etc.)

    Note:
        encrypt_audit_logs is not currently validated because encryption
        is not yet implemented. See Story 4.29 for encryption roadmap.

    Args:
        policy: The CompliancePolicy to validate.

    Returns:
        ValidationResult with ok=True if valid, or ok=False with issues list.
    """
    result = ValidationResult(ok=True)

    # General rules when enabled
    if policy.enabled:
        _require(
            policy.retention_days >= 30,
            "retention_days",
            "must be >= 30",
            result,
        )
        _require(
            policy.archive_after_days >= 7,
            "archive_after_days",
            "must be >= 7",
            result,
        )

        # Integrity check recommended
        _require(
            policy.require_integrity_check,
            "require_integrity_check",
            "must be enabled",
            result,
        )
        # Note: encrypt_audit_logs validation is skipped because encryption
        # is not yet implemented. See Story 4.29 for encryption roadmap.

    # Framework-specific baseline checks
    if policy.level in {
        ComplianceLevel.PCI_DSS,
        ComplianceLevel.SOC2,
        ComplianceLevel.ISO27001,
    }:
        # Note: encrypt_audit_logs validation is skipped because encryption
        # is not yet implemented. See Story 4.29 for encryption roadmap.
        _require(
            policy.require_integrity_check,
            "integrity",
            "required for level",
            result,
        )

    if policy.level == ComplianceLevel.HIPAA:
        _require(
            policy.hipaa_minimum_necessary,
            "hipaa_minimum_necessary",
            "required",
            result,
        )

    if policy.level == ComplianceLevel.GDPR:
        _require(
            policy.gdpr_data_subject_rights,
            "gdpr_data_subject_rights",
            "required",
            result,
        )

    return result


def validate_data_handling(
    *,
    level: ComplianceLevel,
    settings: DataHandlingSettings,
) -> ValidationResult:
    """Validate data handling settings against a compliance level.

    This is an opt-in utility function for validating DataHandlingSettings
    against enterprise security baselines. It is NOT automatically called
    during startup - call it explicitly when needed.

    Example:
        from fapilog_audit import (
            validate_data_handling,
            ComplianceLevel,
            DataHandlingSettings,
        )

        settings = DataHandlingSettings(pii_redaction_enabled=True)
        result = validate_data_handling(
            level=ComplianceLevel.GDPR,
            settings=settings,
        )
        if not result.ok:
            for issue in result.issues:
                print(f"{issue.field}: {issue.message}")

    Validated rules:
        - encryption_in_transit must be True
        - encryption_at_rest must be True
        - allow_default_credentials must be False
        - min_password_length >= 12
        - Framework-specific requirements (HIPAA requires PHI redaction, etc.)

    Args:
        level: The compliance level to validate against.
        settings: The DataHandlingSettings to validate.

    Returns:
        ValidationResult with ok=True if valid, or ok=False with issues list.
    """
    result = ValidationResult(ok=True)

    # Baseline security controls
    _require(
        settings.encryption_in_transit,
        "encryption_in_transit",
        "must be true",
        result,
    )
    _require(
        settings.encryption_at_rest,
        "encryption_at_rest",
        "must be true",
        result,
    )
    _require(
        not settings.allow_default_credentials,
        "allow_default_credentials",
        "must be false",
        result,
    )
    _require(
        settings.min_password_length >= 12,
        "min_password_length",
        "must be >= 12",
        result,
    )

    if level == ComplianceLevel.HIPAA:
        _require(
            settings.phi_redaction_enabled,
            "phi_redaction_enabled",
            "required",
            result,
        )

    if level == ComplianceLevel.GDPR:
        _require(
            settings.pii_redaction_enabled,
            "pii_redaction_enabled",
            "required",
            result,
        )

    if level == ComplianceLevel.PCI_DSS:
        _require(
            settings.encryption_at_rest,
            "encryption_at_rest",
            "required for PCI-DSS",
            result,
        )

    return result


def validate_audit_config(audit: AuditConfig) -> ValidationResult:
    """Validate audit configuration wrapper."""
    # Currently delegates to CompliancePolicy validation
    return validate_compliance_policy(audit.policy)
