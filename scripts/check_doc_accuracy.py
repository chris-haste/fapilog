#!/usr/bin/env python3
"""Validate documentation accuracy for critical claims.

This script checks that documentation accurately reflects code behavior,
particularly for security-sensitive features, defaults, and guarantees.

Checks are organized into categories:
1. DOC_CHECKS: Verify documentation files exist and contain required content
2. CODE_CHECKS: Verify documented defaults match actual code values
3. BEHAVIOR_CHECKS: Verify documented behavioral claims match code patterns

Usage:
    python scripts/check_doc_accuracy.py

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class CheckResult:
    """Result of a documentation check."""

    name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    skipped: bool = False


# =============================================================================
# DOCUMENTATION FILE CHECKS
# =============================================================================
# Verify documentation files exist and contain required content/disclaimers.
# Each check can have:
#   - file: path to the documentation file
#   - must_contain: list of strings that must be present (case-insensitive)
#   - must_not_contain: list of regex patterns that must NOT be present
#   - required: if True (default), fail when file is missing; if False, skip

DOC_CHECKS: list[dict[str, Any]] = [
    # --- Redaction documentation (security-critical) ---
    {
        "file": "docs/redaction/index.md",
        "required": True,
        "must_contain": ["disclaimer", "best-effort", "field names"],
        "must_not_contain": [],
    },
    {
        "file": "docs/redaction/behavior.md",
        "required": True,
        "must_contain": ["disclaimer", "what gets redacted"],
        "must_not_contain": [],
    },
    {
        "file": "docs/redaction/testing.md",
        "required": True,
        "must_contain": [],
        "must_not_contain": [],
    },
    # --- Reliability documentation ---
    {
        "file": "docs/user-guide/reliability-defaults.md",
        "required": True,
        "must_contain": [
            "same-thread",  # Must document same-thread drop behavior
            "drop",  # Must mention drop semantics
            "backpressure",  # Must document backpressure
        ],
        "must_not_contain": [],
    },
    # --- Configuration documentation ---
    {
        "file": "docs/user-guide/configuration.md",
        "required": True,
        "must_contain": [
            "plugin security",  # Must document plugin security
            "allow_external",  # Must mention the setting
            "arbitrary code",  # Must warn about code execution
        ],
        "must_not_contain": [],
    },
    # --- Envelope documentation (optional but accurate if present) ---
    {
        "file": "docs/core-concepts/envelope.md",
        "required": False,
        "must_contain": [],
        "must_not_contain": [r"flattened.*metadata", r"merged at top level"],
    },
]


# =============================================================================
# CODE DEFAULT CHECKS
# =============================================================================
# Verify that documented default values match actual code defaults.
# These checks import code and verify Field defaults or class attributes.


def check_settings_defaults() -> CheckResult:
    """Verify documented defaults in reliability-defaults.md match Settings."""
    errors: list[str] = []

    try:
        from fapilog.core.settings import CoreSettings, Settings

        # Documented in reliability-defaults.md
        core_defaults = [
            ("max_queue_size", 10000),
            ("backpressure_wait_ms", 50),
            ("drop_on_full", True),
            ("batch_max_size", 256),
            ("batch_timeout_seconds", 0.25),
            ("redaction_max_depth", 6),
            ("redaction_max_keys_scanned", 5000),
            ("exceptions_enabled", True),
            ("internal_logging_enabled", False),
            ("error_dedupe_window_seconds", 5.0),
        ]

        # Check CoreSettings defaults
        for field_name, expected_value in core_defaults:
            if field_name not in CoreSettings.model_fields:
                errors.append(f"CoreSettings.{field_name} not found in model fields")
                continue

            actual_default = CoreSettings.model_fields[field_name].default
            if actual_default != expected_value:
                errors.append(
                    f"CoreSettings.{field_name}: "
                    f"documented={expected_value}, actual={actual_default}"
                )

        # Check PluginsSettings defaults (nested in Settings)
        plugins_model = Settings.PluginsSettings
        if "allow_external" not in plugins_model.model_fields:
            errors.append("Settings.PluginsSettings.allow_external not found")
        else:
            actual = plugins_model.model_fields["allow_external"].default
            if actual is not False:
                errors.append(
                    f"Settings.PluginsSettings.allow_external: "
                    f"documented=False, actual={actual}"
                )

    except ImportError as e:
        errors.append(f"Could not import settings: {e}")

    return CheckResult(
        name="Settings defaults match documentation",
        passed=len(errors) == 0,
        errors=errors,
    )


def check_webhook_signature_default() -> CheckResult:
    """Verify webhook sink defaults to HMAC signature mode."""
    errors: list[str] = []

    try:
        from fapilog.plugins.sinks.webhook import SignatureMode, WebhookSinkConfig

        # Check default signature mode
        default_mode = WebhookSinkConfig.model_fields["signature_mode"].default
        if default_mode != SignatureMode.HMAC:
            errors.append(
                f"WebhookSinkConfig.signature_mode: expected HMAC, got {default_mode}"
            )

        # Verify HEADER mode no longer exists (removed for security)
        if hasattr(SignatureMode, "HEADER"):
            errors.append("SignatureMode.HEADER should be removed (security risk)")

    except ImportError as e:
        errors.append(f"Could not import webhook sink: {e}")

    return CheckResult(
        name="Webhook signature defaults to HMAC",
        passed=len(errors) == 0,
        errors=errors,
    )


def check_external_plugins_disabled_default() -> CheckResult:
    """Verify external plugins are disabled by default (security)."""
    errors: list[str] = []

    try:
        from fapilog.core.settings import Settings

        plugins_model = Settings.PluginsSettings
        default_allow_external = plugins_model.model_fields["allow_external"].default
        if default_allow_external is not False:
            errors.append(
                f"PluginsSettings.allow_external should default to False, "
                f"got {default_allow_external}"
            )

    except ImportError as e:
        errors.append(f"Could not import settings: {e}")

    return CheckResult(
        name="External plugins disabled by default",
        passed=len(errors) == 0,
        errors=errors,
    )


# =============================================================================
# BEHAVIORAL CHECKS
# =============================================================================
# Verify documented behavioral claims exist in the code.


def check_same_thread_drop_behavior() -> CheckResult:
    """Verify same-thread drop behavior is implemented (not just documented)."""
    errors: list[str] = []

    # Check that logger.py contains same-thread detection and drop logic
    logger_path = Path("src/fapilog/core/logger.py")
    if not logger_path.exists():
        errors.append("src/fapilog/core/logger.py not found")
    else:
        content = logger_path.read_text()
        # Should detect same-thread scenario
        if "same" not in content.lower() or "thread" not in content.lower():
            errors.append("logger.py should reference same-thread behavior")
        # Should have immediate drop path
        if "drop" not in content.lower():
            errors.append("logger.py should have drop logic")

    return CheckResult(
        name="Same-thread drop behavior implemented",
        passed=len(errors) == 0,
        errors=errors,
    )


def check_graceful_shutdown_handler() -> CheckResult:
    """Verify graceful shutdown handler is implemented."""
    errors: list[str] = []

    shutdown_path = Path("src/fapilog/core/shutdown.py")
    if not shutdown_path.exists():
        errors.append("src/fapilog/core/shutdown.py not found")
    else:
        content = shutdown_path.read_text()
        # Should use atexit for graceful shutdown
        if "atexit" not in content:
            errors.append("shutdown.py should use atexit for graceful drain")
        # Should handle signals
        if "signal" not in content.lower():
            errors.append("shutdown.py should handle signals")

    return CheckResult(
        name="Graceful shutdown handler implemented",
        passed=len(errors) == 0,
        errors=errors,
    )


def check_redos_protection() -> CheckResult:
    """Verify ReDoS protection is implemented in regex redactor."""
    errors: list[str] = []

    regex_path = Path("src/fapilog/plugins/redactors/regex_mask.py")
    if not regex_path.exists():
        errors.append("src/fapilog/plugins/redactors/regex_mask.py not found")
    else:
        content = regex_path.read_text()
        # Should have pattern validation
        if "allow_unsafe_patterns" not in content:
            errors.append(
                "regex_mask.py should have allow_unsafe_patterns escape hatch"
            )
        # Should detect dangerous patterns
        if "catastrophic" not in content.lower() and "redos" not in content.lower():
            # Check for pattern validation logic
            if "validate" not in content.lower():
                errors.append("regex_mask.py should validate patterns for ReDoS")

    return CheckResult(
        name="ReDoS protection in regex redactor",
        passed=len(errors) == 0,
        errors=errors,
    )


# =============================================================================
# MAIN EXECUTION
# =============================================================================

CODE_CHECKS: list[Callable[[], CheckResult]] = [
    check_settings_defaults,
    check_webhook_signature_default,
    check_external_plugins_disabled_default,
    check_same_thread_drop_behavior,
    check_graceful_shutdown_handler,
    check_redos_protection,
]


def check_doc_file(check: dict[str, Any]) -> CheckResult:
    """Check a single documentation file against its constraints."""
    file_path = Path(check["file"])
    required = check.get("required", True)

    if not file_path.exists():
        if required:
            return CheckResult(
                name=str(file_path),
                passed=False,
                errors=["Required file is missing"],
            )
        return CheckResult(name=str(file_path), passed=True, skipped=True)

    content = file_path.read_text()
    errors: list[str] = []

    # Check must_contain patterns (case-insensitive plain text)
    for pattern in check.get("must_contain", []):
        if pattern.lower() not in content.lower():
            errors.append(f"Missing required text: '{pattern}'")

    # Check must_not_contain patterns (case-insensitive regex)
    for pattern in check.get("must_not_contain", []):
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Found prohibited pattern: '{pattern}'")

    return CheckResult(
        name=str(file_path),
        passed=len(errors) == 0,
        errors=errors,
    )


def run_all_checks() -> int:
    """Run all documentation and code checks."""
    all_passed = True
    total_checks = 0
    passed_checks = 0

    print("=" * 60)
    print("DOCUMENTATION FILE CHECKS")
    print("=" * 60)

    for check in DOC_CHECKS:
        result = check_doc_file(check)
        total_checks += 1
        if result.skipped:
            print(f"SKIP: {result.name} (optional, not found)")
        elif result.passed:
            print(f"PASS: {result.name}")
            passed_checks += 1
        else:
            print(f"FAIL: {result.name}")
            for error in result.errors:
                print(f"  - {error}")
            all_passed = False

    print()
    print("=" * 60)
    print("CODE DEFAULT & BEHAVIOR CHECKS")
    print("=" * 60)

    for check_fn in CODE_CHECKS:
        result = check_fn()
        total_checks += 1
        if result.skipped:
            print(f"SKIP: {result.name}")
        elif result.passed:
            print(f"PASS: {result.name}")
            passed_checks += 1
        else:
            print(f"FAIL: {result.name}")
            for error in result.errors:
                print(f"  - {error}")
            all_passed = False

    print()
    print("=" * 60)
    print(f"SUMMARY: {passed_checks}/{total_checks} checks passed")
    print("=" * 60)

    return 0 if all_passed else 1


def main() -> int:
    """Main entry point."""
    return run_all_checks()


if __name__ == "__main__":
    sys.exit(main())
