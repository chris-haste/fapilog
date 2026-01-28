#!/usr/bin/env python3
"""Validate documentation accuracy for critical claims.

This script checks that documentation accurately reflects code behavior,
particularly for security-sensitive features and defaults.

Checks are organized into categories:
1. DOC_CHECKS: Verify documentation files exist and contain required content
2. CODE_CHECKS: Verify documented defaults match actual code values

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
# CODE BLOCK EXTRACTION
# =============================================================================


def extract_python_blocks(content: str) -> list[str]:
    """Extract Python code blocks from markdown content.

    Args:
        content: Markdown content to parse.

    Returns:
        List of Python code block contents (without fence markers).
    """
    # Match ```python or ``` python (with optional space)
    pattern = r"```(?:python|py)\s*\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
    return matches


# =============================================================================
# ASYNC USAGE VALIDATION
# =============================================================================


def check_async_usage(file_path: Path) -> CheckResult:
    """Check for incorrect async logger usage in Python code blocks.

    Validates:
    1. get_logger() (sync) should NOT be used with await
    2. get_async_logger() should be used with await
    3. await should not appear at module level (outside async functions)

    Args:
        file_path: Path to the markdown file to check.

    Returns:
        CheckResult with any detected async usage errors.
    """
    if not file_path.exists():
        return CheckResult(name=str(file_path), passed=True, skipped=True)

    content = file_path.read_text()
    code_blocks = extract_python_blocks(content)
    errors: list[str] = []

    for i, block in enumerate(code_blocks, 1):
        block_errors = _check_block_async_usage(block, i)
        errors.extend(block_errors)

    return CheckResult(
        name=f"async_usage:{file_path}",
        passed=len(errors) == 0,
        errors=errors,
    )


def _check_block_async_usage(code: str, block_num: int) -> list[str]:
    """Check a single code block for async usage issues.

    Args:
        code: Python code content.
        block_num: Block number for error reporting.

    Returns:
        List of error messages.
    """
    errors: list[str] = []
    lines = code.split("\n")

    # Track state
    uses_sync_logger = False
    uses_async_logger = False
    uses_runtime_async = False

    # Detect logger type from imports and assignments (skip comments)
    for line in lines:
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue
        # Remove inline comments for detection
        code_part = stripped.split("#")[0].strip()
        # Check imports
        if "get_logger" in code_part and "get_async_logger" not in code_part:
            uses_sync_logger = True
        if "get_async_logger" in code_part:
            uses_async_logger = True
        if "runtime_async" in code_part:
            uses_runtime_async = True

    # Track indentation to determine if we're inside an async function
    # Module level = 0 indentation, inside function = indented
    async_def_indent: int | None = None  # Indent level where async def was declared

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue

        # Skip comment-only lines
        if stripped.startswith("#"):
            continue

        # Remove inline comments for analysis
        code_part = stripped.split("#")[0].strip()
        if not code_part:
            continue

        # Calculate current indentation (number of leading spaces)
        current_indent = len(line) - len(line.lstrip())

        # Track async def declarations
        if code_part.startswith("async def ") or code_part.startswith(
            "@asynccontextmanager"
        ):
            async_def_indent = current_indent
        elif code_part.startswith("def ") and async_def_indent is not None:
            # Regular def at same or lower indent exits async context
            if current_indent <= async_def_indent:
                async_def_indent = None

        # Check if we're inside an async function (indented more than async def)
        in_async_context = (
            async_def_indent is not None and current_indent > async_def_indent
        )

        # Check for await at module level (outside async context)
        if "await " in code_part and not in_async_context:
            # Special case: await inside "async with" on same line is OK
            if not code_part.startswith("async with "):
                errors.append(
                    f"Block {block_num}, line {line_num}: "
                    f"'await' used outside async context (module level await)"
                )

        # Check for await on sync logger
        if uses_sync_logger and not uses_async_logger and not uses_runtime_async:
            # Look for await logger.<method>
            if re.search(r"await\s+logger\.", code_part):
                errors.append(
                    f"Block {block_num}, line {line_num}: "
                    f"'await' used with sync logger from get_logger() - "
                    f"either remove 'await' or use get_async_logger()"
                )

    return errors


# =============================================================================
# DOCUMENTATION FILE CHECKS
# =============================================================================
# Verify documentation files exist and contain required content/disclaimers.
# Each check can have:
#   - file: path to the documentation file
#   - must_contain: list of strings that must be present (case-insensitive)
#   - must_not_contain: list of regex patterns that must NOT be present
#   - required: if True, fail when file is missing; if False (default), skip

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

        # Check default signature mode is HMAC (secure default)
        default_mode = WebhookSinkConfig.model_fields["signature_mode"].default
        if default_mode != SignatureMode.HMAC:
            errors.append(
                f"WebhookSinkConfig.signature_mode: expected HMAC, got {default_mode}"
            )

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


def check_example_async_usage() -> CheckResult:
    """Validate async logger usage in all example documentation files.

    Checks docs/examples/*.md for:
    - get_logger() (sync) used incorrectly with await
    - await used at module level outside async context
    """
    examples_dir = Path("docs/examples")
    if not examples_dir.exists():
        return CheckResult(
            name="Example async usage validation",
            passed=True,
            skipped=True,
        )

    all_errors: list[str] = []

    for md_file in sorted(examples_dir.glob("**/*.md")):
        result = check_async_usage(md_file)
        if not result.passed:
            for error in result.errors:
                all_errors.append(f"{md_file.name}: {error}")

    return CheckResult(
        name="Example async usage validation",
        passed=len(all_errors) == 0,
        errors=all_errors,
    )


# =============================================================================
# MAIN EXECUTION
# =============================================================================

CODE_CHECKS: list[Callable[[], CheckResult]] = [
    check_settings_defaults,
    check_webhook_signature_default,
    check_external_plugins_disabled_default,
    check_example_async_usage,
]


def check_file(check: dict[str, Any]) -> CheckResult:
    """Check a single documentation file against its constraints.

    Args:
        check: Dictionary with 'file', 'must_contain', 'must_not_contain',
               and optional 'required' keys.

    Returns:
        CheckResult indicating pass/fail status and any errors.
    """
    file_path = Path(check["file"])
    # Default: skip missing files (backwards compatible)
    # Set required=True in DOC_CHECKS for critical files that must exist
    required = check.get("required", False)

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


def run_checks(checks: list[dict[str, Any]]) -> int:
    """Run documentation checks and return exit code.

    Args:
        checks: List of check configurations.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    all_passed = True

    for check in checks:
        result = check_file(check)
        if result.skipped:
            print(f"SKIP: {result.name} not found")
            continue
        if result.passed:
            print(f"PASS: {result.name}")
        else:
            print(f"FAIL: {result.name}")
            for error in result.errors:
                print(f"  - {error}")
            all_passed = False

    return 0 if all_passed else 1


def run_all_checks() -> int:
    """Run all documentation and code checks."""
    all_passed = True
    total_checks = 0
    passed_checks = 0

    print("=" * 60)
    print("DOCUMENTATION FILE CHECKS")
    print("=" * 60)

    for check in DOC_CHECKS:
        result = check_file(check)
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
