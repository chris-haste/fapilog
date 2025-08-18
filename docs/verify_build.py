#!/usr/bin/env python3
"""
Build verification script for fapilog documentation.

This script verifies that the documentation build produced the expected output.
"""

import sys
from pathlib import Path
from typing import List


def verify_build_output() -> List[str]:
    """Verify that documentation build produced expected output."""
    build_dir = Path("_build/html")

    if not build_dir.exists():
        return ["Build directory does not exist"]

    required_files = ["index.html", "genindex.html", "search.html"]

    missing_files = []
    for file in required_files:
        if not (build_dir / file).exists():
            missing_files.append(file)

    return missing_files


def verify_build_structure() -> List[str]:
    """Verify the overall build structure."""
    build_dir = Path("_build/html")

    if not build_dir.exists():
        return ["Build directory does not exist"]

    issues = []

    # Check if static files are present
    static_dir = build_dir / "_static"
    if not static_dir.exists():
        issues.append("Static files directory missing")

    # Check if CSS files are present
    css_files = list(build_dir.glob("**/*.css"))
    if not css_files:
        issues.append("No CSS files found")

    # Check if JavaScript files are present
    js_files = list(build_dir.glob("**/*.js"))
    if not js_files:
        issues.append("No JavaScript files found")

    return issues


def verify_api_documentation() -> List[str]:
    """Verify that API documentation was generated."""
    build_dir = Path("_build/html")

    if not build_dir.exists():
        return ["Build directory does not exist"]

    issues = []

    # Check for API documentation landing page
    api_index = build_dir / "api-reference" / "index.html"
    if not api_index.exists():
        issues.append("API reference index not found")

    return issues


def main() -> int:
    """Main entry point."""
    print("🔍 Verifying documentation build...")

    # Check if we're in the docs directory
    if not Path("conf.py").exists():
        print("Error: This script must be run from the docs/ directory")
        return 1

    # Check if build exists
    if not Path("_build").exists():
        print("Error: Build directory not found. Run build.sh first.")
        return 1

    all_issues = []

    # Verify basic build output
    missing_files = verify_build_output()
    if missing_files:
        all_issues.extend([f"Missing required file: {f}" for f in missing_files])

    # Verify build structure
    structure_issues = verify_build_structure()
    all_issues.extend(structure_issues)

    # Verify API documentation
    api_issues = verify_api_documentation()
    all_issues.extend(api_issues)

    if all_issues:
        print(f"\n❌ Found {len(all_issues)} issues:")
        for issue in all_issues:
            print(f"  - {issue}")
        return 1
    else:
        print("\n✅ Build verification passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
