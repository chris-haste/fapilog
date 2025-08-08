"""
Encryption configuration models and validation for Fapilog v3.

Provides a Pydantic v2 model for encryption settings and validation helpers
to ensure enterprise-grade configuration quality.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .plugin_config import ValidationIssue, ValidationResult
from .validation import ensure_path_exists


class EncryptionSettings(BaseModel):
    """Settings controlling encryption for sensitive data and transport.

    This model is intentionally conservative with defaults matching
    enterprise expectations.
    """

    enabled: bool = Field(default=True, description="Enable encryption features")
    algorithm: Literal[
        "AES-256",
        "ChaCha20-Poly1305",
        "AES-128",
    ] = Field(
        default="AES-256",
        description="Primary encryption algorithm",
    )

    # How the encryption key material is obtained
    key_source: Literal["env", "file", "kms", "vault"] | None = Field(
        default=None,
        description="Source for key material",
    )

    # Source-specific fields
    env_var_name: str | None = Field(
        default=None,
        description="Environment variable holding key material",
    )
    key_file_path: str | None = Field(
        default=None,
        description="Filesystem path to key material",
    )
    key_id: str | None = Field(
        default=None,
        description="Key identifier for KMS/Vault sources",
    )

    # Lifecycle
    rotate_interval_days: int = Field(
        default=90, ge=0, description="Recommended key rotation interval"
    )

    # Transport security baseline (used by validation only)
    min_tls_version: Literal["1.2", "1.3"] = Field(
        default="1.2",
        description="Minimum TLS version for transport",
    )


def validate_encryption(settings: EncryptionSettings) -> ValidationResult:
    """Validate encryption settings synchronously.

    Returns a ValidationResult with detailed issues. This function avoids I/O.
    Use `validate_encryption_async` for file existence checks when `file`
    key_source is used.
    """

    result = ValidationResult(ok=True)

    if not settings.enabled:
        # Encryption disabled is allowed but discouraged; record a warning
        result.add_issue(
            ValidationIssue(
                field="enabled",
                message="encryption disabled (not recommended)",
                severity="warn",
            )
        )
        return result

    # When enabled, key_source must be defined
    if settings.key_source is None:
        # Allow missing key_source by default; warn to encourage configuration
        result.add_issue(
            ValidationIssue(
                field="key_source",
                message="missing key source; set env/file/kms/vault",
                severity="warn",
            )
        )
        return result

    # Source-specific requirements
    if settings.key_source == "env":
        env_name = settings.env_var_name or ""
        if not env_name.strip():
            result.add_issue(
                ValidationIssue(
                    field="env_var_name", message="required for key_source=env"
                )
            )
    elif settings.key_source == "file":
        key_path = settings.key_file_path or ""
        if not key_path.strip():
            result.add_issue(
                ValidationIssue(
                    field="key_file_path", message="required for key_source=file"
                )
            )
    elif settings.key_source in {"kms", "vault"}:
        key_id = settings.key_id or ""
        if not key_id.strip():
            result.add_issue(
                ValidationIssue(
                    field="key_id", message="required for key_source=kms/vault"
                )
            )

    # Basic algorithm sanity check (AES-128 discouraged)
    if settings.algorithm == "AES-128":
        result.add_issue(
            ValidationIssue(
                field="algorithm",
                message="AES-128 is discouraged; prefer AES-256",
                severity="warn",
            )
        )

    # Soft guidance on key rotation intervals
    if settings.rotate_interval_days and settings.rotate_interval_days > 365:
        result.add_issue(
            ValidationIssue(
                field="rotate_interval_days",
                message="consider rotating keys at least annually",
                severity="warn",
            )
        )

    # Soft guidance on TLS baseline
    if settings.min_tls_version == "1.2":
        result.add_issue(
            ValidationIssue(
                field="min_tls_version",
                message="TLS 1.3 recommended where possible",
                severity="warn",
            )
        )

    return result


async def validate_encryption_async(settings: EncryptionSettings) -> ValidationResult:
    """Async validation that includes I/O checks (e.g., key file existence)."""
    result = validate_encryption(settings)

    # If file-based key is configured and a path is provided, verify it exists
    if (
        settings.enabled
        and settings.key_source == "file"
        and settings.key_file_path
        and all(i.field != "key_file_path" for i in result.issues)
    ):
        try:
            await ensure_path_exists(
                settings.key_file_path,
                message="key file not found",
            )
        except FileNotFoundError as e:
            result.add_issue(ValidationIssue(field="key_file_path", message=str(e)))

    return result
