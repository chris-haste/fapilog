"""
Access control configuration models and validation for Fapilog v3.

Validates role-based access control and authentication/authorization flags.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .plugin_config import ValidationIssue, ValidationResult


class AccessControlSettings(BaseModel):
    """Settings for access control and authorization."""

    enabled: bool = Field(
        default=True,
        description="Enable access control checks across the system",
    )
    # Choose an auth mode; integration is out of scope for core library
    auth_mode: Literal["none", "basic", "token", "oauth2"] = Field(
        default="token",
        description="Authentication mode used by integrations (library-agnostic)",
    )
    # Role-based access control
    allowed_roles: list[str] = Field(
        default_factory=lambda: ["admin", "system"],
        description="List of roles granted access to protected operations",
    )
    require_admin_for_sensitive_ops: bool = Field(
        default=True,
        description="Require admin role for sensitive or destructive operations",
    )
    # Authorization switches
    allow_anonymous_read: bool = Field(
        default=False,
        description="Permit read access without authentication (discouraged)",
    )
    allow_anonymous_write: bool = Field(
        default=False,
        description="Permit write access without authentication (never recommended)",
    )


def validate_access_control(settings: AccessControlSettings) -> ValidationResult:
    """Validate access control configuration and return a ValidationResult."""
    result = ValidationResult(ok=True)

    if not settings.enabled:
        result.add_issue(
            ValidationIssue(
                field="enabled",
                message="access control disabled (not recommended)",
                severity="warn",
            )
        )
        return result

    # Basic guardrails
    if settings.auth_mode == "none":
        result.add_issue(
            ValidationIssue(
                field="auth_mode",
                message=(
                    "auth_mode=none is not allowed when access control is enabled"
                ),
            )
        )

    # Must have at least one role defined
    if not settings.allowed_roles:
        result.add_issue(
            ValidationIssue(
                field="allowed_roles", message="must define at least one role"
            )
        )

    # Anonymous writes are never allowed in enterprise environments
    if settings.allow_anonymous_write:
        result.add_issue(
            ValidationIssue(
                field="allow_anonymous_write",
                message="must be false in enterprise settings",
            )
        )

    # Soft guidance to discourage anonymous reads
    if settings.allow_anonymous_read:
        result.add_issue(
            ValidationIssue(
                field="allow_anonymous_read",
                message="anonymous reads are discouraged; prefer authenticated access",
                severity="warn",
            )
        )

    # Ensure sensitive operations require admin when enabled
    if not settings.require_admin_for_sensitive_ops:
        result.add_issue(
            ValidationIssue(
                field="require_admin_for_sensitive_ops",
                message="should be true to protect sensitive operations",
                severity="warn",
            )
        )

    return result
