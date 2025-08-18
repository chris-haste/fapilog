"""
Security configuration envelope combining encryption and access control.

Provides top-level validation entrypoints required by Story 1.4d.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .access_control import AccessControlSettings, validate_access_control
from .encryption import EncryptionSettings, validate_encryption_async
from .plugin_config import ValidationIssue, ValidationResult


class SecuritySettings(BaseModel):
    """Aggregated security settings for the library."""

    encryption: EncryptionSettings = Field(
        default_factory=EncryptionSettings,
        description="Cryptography, key management, and data protection settings",
    )
    access_control: AccessControlSettings = Field(
        default_factory=AccessControlSettings,
        description="Authentication/authorization and role-based access control",
    )


async def validate_security(settings: SecuritySettings) -> ValidationResult:
    """Validate security configuration including async checks.

    Combines encryption and access control validation and aggregates issues.
    """

    result = ValidationResult(ok=True)

    # Encryption (async)
    enc_result = await validate_encryption_async(settings.encryption)
    for issue in enc_result.issues:
        result.add_issue(
            ValidationIssue(
                field=f"encryption.{issue.field}",
                message=issue.message,
                severity=issue.severity,
            )
        )

    # Access control (sync)
    ac_result = validate_access_control(settings.access_control)
    for issue in ac_result.issues:
        result.add_issue(
            ValidationIssue(
                field=f"access_control.{issue.field}",
                message=issue.message,
                severity=issue.severity,
            )
        )

    return result
