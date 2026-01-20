#!/usr/bin/env python3
"""Check that plugin min_fapilog_version doesn't exceed current version.

This pre-commit hook ensures plugins don't claim compatibility with unreleased
versions of fapilog.
"""

import re
import sys
from pathlib import Path
from typing import List

# Current released version (update on release)
CURRENT_VERSION = "0.4.0"

# Pattern to match min_fapilog_version in plugin metadata
VERSION_PATTERN = re.compile(r'"min_fapilog_version":\s*"([^"]+)"')


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers.

    Args:
        version: Version string like "0.3.5" or "1.0"

    Returns:
        Tuple of version components as integers
    """
    return tuple(int(x) for x in version.split("."))


def check_plugin_file(file_path: Path, current_version: str) -> List[str]:
    """Check a single plugin file for version violations.

    Args:
        file_path: Path to the plugin file
        current_version: Current fapilog version to compare against

    Returns:
        List of error messages, empty if no violations
    """
    errors: List[str] = []
    current = parse_version(current_version)

    try:
        content = file_path.read_text()
        for match in VERSION_PATTERN.finditer(content):
            claimed = match.group(1)
            if parse_version(claimed) > current:
                errors.append(f"{file_path}: claims {claimed} > {current_version}")
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return errors


def check_plugins_directory(directory: Path, current_version: str) -> List[str]:
    """Check all plugin files in a directory for version violations.

    Args:
        directory: Root directory to search for plugins
        current_version: Current fapilog version to compare against

    Returns:
        List of all error messages from all files
    """
    all_errors: List[str] = []

    for py_file in directory.rglob("*.py"):
        if py_file.name.startswith("."):
            continue
        # Skip __pycache__ directories
        if "__pycache__" in py_file.parts:
            continue

        errors = check_plugin_file(py_file, current_version)
        all_errors.extend(errors)

    return all_errors


def main() -> int:
    """Main entry point for the version check.

    Returns:
        0 if no violations, 1 if violations found
    """
    # Directories containing plugins
    plugin_dirs = [
        Path("src/fapilog/plugins"),
        Path("packages"),  # Extracted packages like fapilog-audit
    ]

    all_errors: List[str] = []

    for plugins_dir in plugin_dirs:
        if not plugins_dir.exists():
            continue
        errors = check_plugins_directory(plugins_dir, CURRENT_VERSION)
        all_errors.extend(errors)

    if all_errors:
        print("❌ Plugin version errors:")
        for error in all_errors:
            print(f"  {error}")
        print()
        print(f"Plugins cannot claim min_fapilog_version > {CURRENT_VERSION}")
        print("Update CURRENT_VERSION in this script when releasing new versions.")
        return 1

    print(f"✅ All plugins claim valid versions (<= {CURRENT_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
