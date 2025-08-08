"""
Enterprise compliance configuration validation for Fapilog v3.

Validates compliance policies, data handling, and audit configurations against
baseline enterprise expectations. Uses lightweight rules (not legal guidance).
"""

from __future__ import annotations

# Note: No Optional imports currently needed
from pydantic import BaseModel, Field

from .audit import ComplianceLevel, CompliancePolicy
from .plugin_config import ValidationIssue, ValidationResult


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
    """Validate a CompliancePolicy against baseline enterprise rules."""
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

        # Encryption and integrity generally recommended
        _require(
            policy.encrypt_audit_logs,
            "encrypt_audit_logs",
            "must be enabled",
            result,
        )
        _require(
            policy.require_integrity_check,
            "require_integrity_check",
            "must be enabled",
            result,
        )

    # Framework-specific baseline checks
    if policy.level in {
        ComplianceLevel.PCI_DSS,
        ComplianceLevel.SOC2,
        ComplianceLevel.ISO27001,
    }:
        _require(
            policy.encrypt_audit_logs,
            "encrypt_audit_logs",
            "required for level",
            result,
        )
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
    """Validate data handling settings against a compliance level."""
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
