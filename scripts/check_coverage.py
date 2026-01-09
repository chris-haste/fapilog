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
from typing import Optional
from xml.etree import ElementTree


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
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "--cov=src/fapilog",
                "--cov-branch",
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

        # Extract coverage percentage from XML (more stable than stdout parsing)
        coverage_percentage = extract_coverage_from_xml(Path("coverage.xml"))
        if coverage_percentage is None:
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


def extract_coverage_from_xml(xml_path: Path) -> Optional[float]:
    """Extract coverage percentage from coverage.xml."""
    if not xml_path.exists():
        return None

    try:
        root = ElementTree.parse(xml_path).getroot()
    except (ElementTree.ParseError, OSError):
        return None

    lines_valid = root.get("lines-valid")
    lines_covered = root.get("lines-covered")
    branches_valid = root.get("branches-valid", "0")
    branches_covered = root.get("branches-covered", "0")
    if lines_valid is not None and lines_covered is not None:
        try:
            lines_valid_int = int(lines_valid)
            lines_covered_int = int(lines_covered)
            branches_valid_int = int(branches_valid)
            branches_covered_int = int(branches_covered)
        except ValueError:
            return None
        total_valid = lines_valid_int + branches_valid_int
        total_covered = lines_covered_int + branches_covered_int
        if total_valid == 0:
            return 0.0
        return (total_covered / total_valid) * 100.0

    line_rate = root.get("line-rate")
    if line_rate is None:
        return None
    try:
        return float(line_rate) * 100.0
    except ValueError:
        return None


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
    coverage_met = coverage >= args.min_coverage
    success = tests_passed and coverage_met

    if not success:
        if not tests_passed:
            # Tests failed - this is the primary issue
            print("FAILED: Tests did not pass")
            print(f"{Colors.RED}{Colors.BOLD}Tests: Failed{Colors.END}")
            if coverage > 0:
                if coverage_met:
                    print(
                        f"{Colors.YELLOW}   Coverage: {coverage:.1f}% (would pass, but tests failed){Colors.END}"
                    )
                else:
                    print(
                        f"{Colors.RED}   Coverage: {coverage:.1f}% (also below {args.min_coverage:.1f}% threshold){Colors.END}"
                    )
            print(f"\n{Colors.BLUE}💡 To fix:{Colors.END}")
            print(
                f"{Colors.BLUE}   1. Run 'pytest -v' to see failing tests{Colors.END}"
            )
            print(f"{Colors.BLUE}   2. Fix the failing tests{Colors.END}")
        elif coverage > 0:
            # Tests passed but coverage is below threshold
            print(
                f"FAILED: Coverage {coverage:.1f}% < {args.min_coverage:.1f}% required"
            )
            print(
                f"{Colors.RED}{Colors.BOLD}Coverage: {coverage:.1f}% (Failed - Required: {args.min_coverage:.1f}%){Colors.END}"
            )
            print(
                f"{Colors.RED}   Shortfall: {args.min_coverage - coverage:.1f}%{Colors.END}"
            )
            print(f"\n{Colors.BLUE}💡 To improve coverage:{Colors.END}")
            print(f"{Colors.BLUE}   1. Add tests for uncovered code{Colors.END}")
            print(f"{Colors.BLUE}   2. Remove unused code{Colors.END}")
            print(
                f"{Colors.BLUE}   3. Run 'pytest --cov=src/fapilog --cov-branch --cov-report=html' for detailed report{Colors.END}"
            )
        else:
            print("FAILED: Could not run coverage tests")
            print(f"{Colors.RED}{Colors.BOLD}Coverage: Failed to run tests{Colors.END}")

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
