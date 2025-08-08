"""
Advanced configuration validation patterns for complex scenarios.
"""

from __future__ import annotations

from .plugin_config import ValidationIssue, ValidationResult
from .settings import Settings


async def validate_advanced_settings(settings: Settings) -> ValidationResult:
    """Run cross-field, conditional, and dependency validations.

    This provides additional guardrails beyond basic validators.
    """
    result = ValidationResult(ok=True)

    # Conditional: If metrics are enabled globally, observability.metrics must
    # be enabled
    if settings.core.enable_metrics and not settings.observability.metrics.enabled:
        result.add_issue(
            ValidationIssue(
                field="observability.metrics.enabled",
                message="must be true when core.enable_metrics is true",
            )
        )

    # Cross-field: Access control must contain 'admin' role if enabled
    ac = settings.security.access_control
    if ac.enabled and "admin" not in {r.lower() for r in ac.allowed_roles}:
        result.add_issue(
            ValidationIssue(
                field="security.access_control.allowed_roles",
                message="must include 'admin' when access control is enabled",
            )
        )

    # Informational: Tracing enabled without metrics can be noisy
    if (
        settings.observability.tracing.enabled
        and not settings.observability.metrics.enabled
    ):
        result.add_issue(
            ValidationIssue(
                field="observability.tracing.enabled",
                message=("tracing enabled without metrics may reduce value"),
                severity="warn",
            )
        )

    return result
