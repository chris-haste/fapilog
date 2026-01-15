#!/usr/bin/env python3
"""
Check diff coverage for changed lines only.

This script runs pytest with coverage and uses diff-cover to ensure
that changed lines meet the minimum coverage threshold (90% by default).

This is faster than full coverage and more fair - you're only responsible
for covering the code you changed.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


class Colors:
    """ANSI color codes."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def get_changed_files() -> list[str]:
    """Get list of Python files changed compared to the merge base."""
    try:
        # Get the merge base with main/master
        result = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try master if main doesn't exist
            result = subprocess.run(
                ["git", "merge-base", "HEAD", "origin/master"],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            # Fallback to HEAD~1 for commits on main
            merge_base = "HEAD~1"
        else:
            merge_base = result.stdout.strip()

        # Get changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", merge_base, "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []

        # Also include staged files not yet committed
        staged = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
        )
        staged_files = (
            staged.stdout.strip().split("\n") if staged.stdout.strip() else []
        )

        # Combine and filter for Python source files
        all_files = result.stdout.strip().split("\n") + staged_files
        return [
            f for f in all_files if f.endswith(".py") and f.startswith("src/") and f
        ]
    except Exception:
        return []


def run_coverage() -> bool:
    """Run tests with coverage and generate XML report."""
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "--cov=src/fapilog",
            "--cov-branch",
            "--cov-report=xml",
            "--cov-report=term-missing:skip-covered",
            "-q",
            "tests/",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=env,
    )

    if result.returncode != 0:
        print(f"{Colors.RED}Tests failed:{Colors.END}")
        if result.stdout:
            # Show only failure summary, not full output
            lines = result.stdout.split("\n")
            for line in lines:
                if "FAILED" in line or "ERROR" in line or "error" in line.lower():
                    print(f"  {line}")
        if result.stderr:
            print(result.stderr)
        return False

    return True


def check_diff_coverage(min_coverage: float) -> tuple[bool, float | None, str]:
    """
    Run diff-cover and check if changed lines meet threshold.

    Returns (success, coverage_percentage, message)
    """
    coverage_xml = Path("coverage.xml")
    if not coverage_xml.exists():
        return False, None, "coverage.xml not found - tests may have failed"

    # Run diff-cover
    result = subprocess.run(
        [
            "diff-cover",
            "coverage.xml",
            "--compare-branch=origin/main",
            f"--fail-under={min_coverage}",
        ],
        capture_output=True,
        text=True,
    )

    # Parse the output to extract coverage percentage
    output = result.stdout + result.stderr
    coverage_pct = None

    for line in output.split("\n"):
        if "Coverage:" in line and "%" in line:
            # Extract percentage from lines like "Coverage: 95.5%"
            try:
                pct_str = line.split("Coverage:")[-1].strip().rstrip("%")
                coverage_pct = float(pct_str)
            except (ValueError, IndexError):
                pass
        elif "Diff Coverage" in line and "%" in line:
            # Handle format "Diff Coverage: 95%"
            try:
                pct_str = line.split(":")[-1].strip().rstrip("%")
                coverage_pct = float(pct_str)
            except (ValueError, IndexError):
                pass

    # Check for "No lines with coverage" which means no changed source lines
    if "No lines with coverage" in output or coverage_pct is None:
        return True, None, "No source lines changed - nothing to check"

    success = result.returncode == 0
    return success, coverage_pct, output


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check diff coverage for changed lines"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=90.0,
        help="Minimum coverage percentage for changed lines (default: 90.0)",
    )
    parser.add_argument(
        "--skip-if-no-changes",
        action="store_true",
        default=True,
        help="Skip if no Python source files changed (default: True)",
    )

    args = parser.parse_args()

    # Check for changed source files
    changed_files = get_changed_files()
    if not changed_files and args.skip_if_no_changes:
        print(
            f"{Colors.GREEN}No source files changed - skipping coverage check{Colors.END}"
        )
        return 0

    # Run tests with coverage
    print(f"{Colors.BLUE}Running tests with coverage...{Colors.END}")
    if not run_coverage():
        print(f"{Colors.RED}{Colors.BOLD}FAILED: Tests did not pass{Colors.END}")
        return 1

    # Check diff coverage
    success, coverage_pct, message = check_diff_coverage(args.min_coverage)

    if coverage_pct is None:
        # No lines to check
        print(f"{Colors.GREEN}{message}{Colors.END}")
        return 0

    if success:
        print(
            f"{Colors.GREEN}{Colors.BOLD}PASSED: Diff coverage {coverage_pct:.1f}%{Colors.END}"
        )
        if coverage_pct >= args.min_coverage + 5:
            print(
                f"{Colors.GREEN}   Excellent! {coverage_pct - args.min_coverage:.1f}% above minimum{Colors.END}"
            )
        return 0
    else:
        print(
            f"{Colors.RED}{Colors.BOLD}FAILED: Diff coverage {coverage_pct:.1f}% < {args.min_coverage:.1f}% required{Colors.END}"
        )
        print(f"\n{Colors.BLUE}To see uncovered lines:{Colors.END}")
        print(
            f"{Colors.BLUE}   diff-cover coverage.xml --compare-branch=origin/main --html-report=diff-cover.html{Colors.END}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
