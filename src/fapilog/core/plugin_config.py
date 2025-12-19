"""
Plugin configuration validation and quality gates for Fapilog v3.

Provides validation utilities for plugin configuration including:
- Quality gates (metadata completeness, schema presence, defaults validity)
- Compatibility checks (re-uses metadata compatibility validation)
- Security checks for sensitive keys
- Dependency checks for presence and version constraints
"""

from __future__ import annotations

import importlib.metadata
import os
from typing import Any, Mapping, Type, Union

from packaging.requirements import Requirement
from packaging.version import InvalidVersion, Version

from ..core.errors import ConfigurationError
from ..plugins.metadata import (
    PluginInfo,
    PluginMetadata,
    validate_fapilog_compatibility,
)


class ValidationIssue:
    def __init__(self, *, field: str, message: str, severity: str = "error") -> None:
        self.field = field
        self.message = message
        self.severity = severity

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


class ValidationResult:
    def __init__(
        self, *, ok: bool, issues: list[ValidationIssue] | None = None
    ) -> None:
        self.ok = ok
        self.issues = issues or []

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.ok = False

    def raise_if_error(self, *, plugin_name: str) -> None:
        if not self.ok:
            details = "; ".join(f"{i.field}: {i.message}" for i in self.issues)
            msg = f"Plugin '{plugin_name}' configuration validation failed: {details}"
            raise ConfigurationError(msg)


def _check_schema_required(
    schema: Mapping[str, Any],
    config: Mapping[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required = list(schema.get("required", []))
    for key in required:
        if key not in config:
            issues.append(ValidationIssue(field=key, message="required key missing"))
    return issues


ClassInfo = Union[Type[object], tuple[Type[object], ...]]

_TYPE_MAP: dict[str, ClassInfo] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _check_schema_types(
    schema: Mapping[str, Any], config: Mapping[str, Any]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    props = schema.get("properties", {})
    for key, value in config.items():
        if key in props and isinstance(props[key], Mapping):
            expected = props[key].get("type")
            if expected in _TYPE_MAP:
                py_type = _TYPE_MAP[expected]
                if not isinstance(value, py_type):
                    issues.append(
                        ValidationIssue(
                            field=key,
                            message=f"expected type {expected}",
                        )
                    )
    return issues


def _check_security(config: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sensitive_keys = {"password", "secret", "token", "api_key"}
    for key, value in config.items():
        if any(sk in key.lower() for sk in sensitive_keys):
            # Basic heuristic: require at least 8 chars if string
            if isinstance(value, str) and len(value) < 8:
                issues.append(
                    ValidationIssue(
                        field=key,
                        message="sensitive value too short (min 8 characters)",
                    )
                )
    return issues


def _parse_installed_versions() -> dict[str, Version]:
    versions: dict[str, Version] = {}
    for dist in importlib.metadata.distributions():
        try:
            versions[dist.metadata["Name"].lower()] = Version(dist.version)
        except InvalidVersion:
            continue
    return versions


def check_dependencies(
    metadata: PluginMetadata,
) -> tuple[list[str], list[str]]:
    """Check plugin dependency presence and version constraints.

    Returns (missing, conflicts) lists of requirement strings.
    """
    missing: list[str] = []
    conflicts: list[str] = []
    installed = _parse_installed_versions()

    for req_str in metadata.dependencies:
        try:
            req = Requirement(req_str)
        except Exception:
            conflicts.append(req_str)
            continue

        name = req.name.lower()
        if name not in installed:
            missing.append(req_str)
            continue

        # Version specifier check
        if req.specifier and installed[name] not in req.specifier:
            conflicts.append(req_str)

    return missing, conflicts


def validate_quality_gates(
    plugin_metadata: PluginMetadata,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    # Basic metadata completeness
    if not plugin_metadata.description:
        issues.append(
            ValidationIssue(
                field="description",
                message="missing description",
                severity="warn",
            )
        )
    if not plugin_metadata.author:
        issues.append(
            ValidationIssue(
                field="author",
                message="missing author",
                severity="warn",
            )
        )
    # Config schema should exist for configurable plugins
    if plugin_metadata.default_config and not plugin_metadata.config_schema:
        issues.append(
            ValidationIssue(
                field="config_schema",
                message="missing config_schema for defaults",
            )
        )
    return issues


def validate_plugin_configuration(
    plugin: PluginInfo,
    config: Mapping[str, Any] | None = None,
) -> ValidationResult:
    """Validate a plugin's configuration.

    If config is not provided, uses plugin.metadata.default_config.
    """
    metadata = plugin.metadata
    result = ValidationResult(ok=True)

    # Compatibility check (opt-in strictness)
    strict_compat = os.getenv("FAPILOG_STRICT_PLUGIN_COMPAT", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if strict_compat and not validate_fapilog_compatibility(metadata):
        result.add_issue(
            ValidationIssue(
                field="compatibility",
                message=("incompatible with current Fapilog"),
            )
        )

    # Quality gates
    for issue in validate_quality_gates(metadata):
        # Warnings don't fail unless severity is 'error'
        result.add_issue(issue)

    # Dependency checks
    missing, conflicts = check_dependencies(metadata)
    for r in missing:
        result.add_issue(ValidationIssue(field="dependencies", message=f"missing {r}"))
    for r in conflicts:
        result.add_issue(ValidationIssue(field="dependencies", message=f"conflict {r}"))

    # Schema checks if schema provided
    schema = metadata.config_schema or {}
    use_config = config or metadata.default_config or {}
    if schema:
        for issue in _check_schema_required(schema, use_config):
            result.add_issue(issue)
        for issue in _check_schema_types(schema, use_config):
            result.add_issue(issue)

    # Security checks
    for issue in _check_security(use_config):
        result.add_issue(issue)

    return result
