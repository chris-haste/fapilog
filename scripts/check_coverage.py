#!/usr/bin/env python3
"""
Check code coverage and enforce minimum coverage threshold.

This script runs pytest with coverage and ensures the code coverage
meets the minimum threshold of 90%.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"  # End color formatting


def run_coverage() -> tuple[bool, float]:
    """Run tests with coverage and return success status and coverage percentage."""
    try:
        # Set up environment with PYTHONPATH for src
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        # Run pytest with coverage
        # Allow CI to tune loop-stall bound to reduce flakiness during coverage
        if "FAPILOG_TEST_MAX_LOOP_STALL_SECONDS" not in env:
            env["FAPILOG_TEST_MAX_LOOP_STALL_SECONDS"] = "0.035"

        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "--cov=src/fapilog",
                "--cov-report=term-missing",
                "--cov-report=xml",
                # Don't use --cov-fail-under; we do threshold check ourselves
                # to avoid floating-point precision edge cases
                "tests/",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            env=env,
        )

        # Extract coverage percentage from output
        coverage_percentage = extract_coverage_from_output(result.stdout)

        # Round to 1 decimal place to match display and avoid floating-point issues
        coverage_percentage = round(coverage_percentage, 1)

        # returncode == 0 means all tests passed; coverage check is done in main()
        return result.returncode == 0, coverage_percentage

    except FileNotFoundError:
        print(
            "❌ pytest not found. Please install it with: pip install pytest pytest-cov"
        )
        return False, 0.0
    except Exception as e:
        print(f"❌ Error running coverage: {e}")
        return False, 0.0


def extract_coverage_from_output(output: str) -> float:
    """Extract coverage percentage from pytest output."""
    for line in output.split("\n"):
        if "TOTAL" in line and "%" in line:
            # Look for pattern like "TOTAL    123    45    67%"
            parts = line.split()
            for part in parts:
                if "%" in part:
                    try:
                        return float(part.replace("%", ""))
                    except ValueError:
                        continue
    return 0.0


def check_tests_exist() -> bool:
    """Check if test files exist."""
    tests_dir = Path("tests")
    if not tests_dir.exists():
        print("❌ Tests directory 'tests/' not found")
        return False

    # Look for test files
    test_files = list(tests_dir.rglob("test_*.py")) + list(tests_dir.rglob("*_test.py"))
    if not test_files:
        print("❌ No test files found in tests/ directory")
        print("   Please add test files following the pattern test_*.py or *_test.py")
        return False

    return True


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check code coverage and enforce minimum threshold"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=90.0,
        help="Minimum coverage percentage required (default: 90.0)",
    )
    parser.add_argument(
        "--skip-if-no-tests",
        action="store_true",
        help="Skip coverage check if no tests are found (useful during initial development)",
    )

    args = parser.parse_args()

    # Check if tests exist
    if not check_tests_exist():
        if args.skip_if_no_tests:
            print(
                f"{Colors.YELLOW}⚠️  No tests found, skipping coverage check{Colors.END}"
            )
            return 0
        else:
            print(f"{Colors.RED}❌ No tests found{Colors.END}")
            print(
                f"{Colors.BLUE}💡 Add --skip-if-no-tests to allow commits without tests during initial development{Colors.END}"
            )
            return 1

    # Run coverage
    tests_passed, coverage = run_coverage()

    # Check both: tests must pass AND coverage must meet threshold
    success = tests_passed and coverage >= args.min_coverage

    if not success:
        if coverage > 0:
            # Print status message for pre-commit
            print(
                f"FAILED: Coverage {coverage:.1f}% < {args.min_coverage:.1f}% required"
            )
            # Print with red color for failure
            print(
                f"{Colors.RED}{Colors.BOLD}Coverage: {coverage:.1f}% (Failed - Required: {args.min_coverage:.1f}%){Colors.END}"
            )
            print(
                f"{Colors.RED}   Shortfall: {args.min_coverage - coverage:.1f}%{Colors.END}"
            )
        else:
            print("FAILED: Could not run coverage tests")
            print(f"{Colors.RED}{Colors.BOLD}Coverage: Failed to run tests{Colors.END}")

        print(f"\n{Colors.BLUE}💡 To improve coverage:{Colors.END}")
        print(f"{Colors.BLUE}   1. Add tests for uncovered code{Colors.END}")
        print(f"{Colors.BLUE}   2. Remove unused code{Colors.END}")
        print(
            f"{Colors.BLUE}   3. Run 'pytest --cov=src/fapilog --cov-report=html' for detailed report{Colors.END}"
        )

        return 1

    # Print status message for pre-commit
    if coverage >= args.min_coverage + 5:
        print(
            f"PASSED: Coverage {coverage:.1f}% (🎉 Excellent! +{coverage - args.min_coverage:.1f}%)"
        )
    else:
        print(
            f"PASSED: Coverage {coverage:.1f}% (✅ +{coverage - args.min_coverage:.1f}%)"
        )

    # Print with green color for success
    print(f"{Colors.GREEN}{Colors.BOLD}Coverage: {coverage:.1f}% (Passed){Colors.END}")
    if coverage >= args.min_coverage + 5:
        print(
            f"{Colors.GREEN}   🎉 Excellent coverage! ({coverage - args.min_coverage:.1f}% above minimum){Colors.END}"
        )
    elif coverage >= args.min_coverage:
        print(
            f"{Colors.GREEN}   ✅ Good coverage! ({coverage - args.min_coverage:.1f}% above minimum){Colors.END}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
