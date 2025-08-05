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
                "--cov-report=term-missing",
                "--cov-report=xml",
                "--cov-fail-under=90",
                "tests/",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            env=env,
        )

        # Extract coverage percentage from output
        coverage_percentage = extract_coverage_from_output(result.stdout)

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

    print("🔍 Checking code coverage...")

    # Check if tests exist
    if not check_tests_exist():
        if args.skip_if_no_tests:
            print("⚠️  No tests found, skipping coverage check")
            return 0
        else:
            print(
                "💡 Add --skip-if-no-tests to allow commits without tests during initial development"
            )
            return 1

    # Run coverage
    success, coverage = run_coverage()

    if not success:
        if coverage > 0:
            print("❌ Code coverage check failed!")
            print(f"   Current coverage: {coverage:.1f}%")
            print(f"   Required coverage: {args.min_coverage:.1f}%")
            print(f"   Shortfall: {args.min_coverage - coverage:.1f}%")
        else:
            print("❌ Failed to run coverage tests")

        print("\n💡 To improve coverage:")
        print("   1. Add tests for uncovered code")
        print("   2. Remove unused code")
        print(
            "   3. Run 'pytest --cov=src/fapilog --cov-report=html' for detailed report"
        )

        return 1

    print("✅ Code coverage check passed!")
    print(f"   Current coverage: {coverage:.1f}%")
    print(f"   Required coverage: {args.min_coverage:.1f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
