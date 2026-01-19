#!/usr/bin/env python3
"""Validate documentation accuracy for critical claims.

This script checks that documentation accurately reflects code behavior,
particularly for security-sensitive features like redaction.

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
from typing import Any


@dataclass
class CheckResult:
    """Result of a documentation check."""

    file: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    skipped: bool = False


# Default checks for fapilog documentation
# Note: Story 3.7 changed url_credentials to be enabled by default for secure defaults
CHECKS: list[dict[str, Any]] = [
    {
        "file": "docs/redaction-guarantees.md",
        # url_credentials is now enabled by default (Story 3.7)
        "must_contain": ["secure default", "by default", "preset"],
        "must_not_contain": [],
    },
    {
        "file": "docs/user-guide/redaction-guarantee.md",
        # url_credentials is now enabled by default (Story 3.7)
        "must_contain": ["secure default", "by default"],
        "must_not_contain": [],
    },
    {
        "file": "docs/core-concepts/envelope.md",
        "must_contain": [],
        "must_not_contain": [r"flattened.*metadata", r"merged at top level"],
    },
]


def check_file(check: dict[str, Any]) -> CheckResult:
    """Check a single file against its constraints.

    Args:
        check: Dictionary with 'file', 'must_contain', and 'must_not_contain' keys.

    Returns:
        CheckResult indicating pass/fail status and any errors.
    """
    file_path = Path(check["file"])
    if not file_path.exists():
        return CheckResult(file=str(file_path), passed=True, skipped=True)

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
        file=str(file_path),
        passed=len(errors) == 0,
        errors=errors,
    )


def run_checks(checks: list[dict[str, Any]]) -> int:
    """Run all documentation checks.

    Args:
        checks: List of check configurations.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    all_passed = True

    for check in checks:
        result = check_file(check)
        if result.skipped:
            print(f"SKIP: {result.file} not found")
            continue
        if result.passed:
            print(f"PASS: {result.file}")
        else:
            print(f"FAIL: {result.file}")
            for error in result.errors:
                print(f"  - {error}")
            all_passed = False

    return 0 if all_passed else 1


def main() -> int:
    """Main entry point."""
    return run_checks(CHECKS)


if __name__ == "__main__":
    sys.exit(main())
