#!/usr/bin/env python3
"""
Release Guardrails Check

This script checks that release commits have proper version bumps and changelog updates.
It can be used in CI/CD pipelines and as a pre-commit hook.

Usage:
    python scripts/check_release_guardrails.py [--commit-msg "chore(release): v1.2.3"]
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


def extract_version_from_commit(commit_msg: str) -> Optional[str]:
    """Extract version from commit message if it's a release commit."""
    pattern = r"^chore\(release\): v(\d+\.\d+\.\d+)$"
    match = re.fullmatch(pattern, commit_msg)
    return match.group(1) if match else None


def get_pyproject_version() -> str:
    """Extract version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")

    with open(pyproject_path) as f:
        content = f.read()

    # Look for version = "X.Y.Z" pattern
    pattern = r'^version\s*=\s*"([^"]+)"'
    for line in content.split("\n"):
        match = re.match(pattern, line.strip())
        if match:
            return match.group(1)

    raise ValueError("Version not found in pyproject.toml")


def check_changelog_version(version: str) -> bool:
    """Check if version exists in CHANGELOG.md."""
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        print("❌ CHANGELOG.md not found")
        return False

    with open(changelog_path) as f:
        content = f.read()

    # Look for version section like "## [X.Y.Z]"
    pattern = rf"^## \[{re.escape(version)}\]"
    return bool(re.search(pattern, content, re.MULTILINE))


def check_release_guardrails(commit_msg: Optional[str] = None) -> Tuple[bool, str]:
    """
    Check release guardrails.

    Returns:
        Tuple of (success: bool, message: str)
    """
    # If no commit message provided, try to get from git
    if commit_msg is None:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                capture_output=True,
                text=True,
                check=True,
            )
            commit_msg = result.stdout.strip()
        except subprocess.CalledProcessError:
            return False, "Failed to get commit message from git"

    # Check if this is a release commit
    version = extract_version_from_commit(commit_msg)
    if not version:
        return True, f"Not a release commit: {commit_msg}"

    print(f"🔍 Checking release guardrails for version {version}")

    # Check version in pyproject.toml
    try:
        pyproject_version = get_pyproject_version()
        if pyproject_version != version:
            return False, (
                f"Version mismatch: expected {version}, "
                f"found {pyproject_version} in pyproject.toml"
            )
        print(f"✅ Version {version} matches pyproject.toml")
    except (FileNotFoundError, ValueError) as e:
        return False, f"Error reading pyproject.toml: {e}"

    # Check changelog
    if not check_changelog_version(version):
        return False, f"Version {version} not found in CHANGELOG.md"
    print(f"✅ Version {version} found in CHANGELOG.md")

    return True, f"All checks passed for version {version}"


def main():
    parser = argparse.ArgumentParser(description="Check release guardrails")
    parser.add_argument(
        "--commit-msg", help="Commit message to check (default: get from git)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    # Ignore any additional arguments (like file paths from pre-commit)
    parser.add_argument("files", nargs="*", help="Files to check (ignored)")

    args = parser.parse_args()

    success, message = check_release_guardrails(args.commit_msg)

    if args.verbose:
        print(f"Result: {message}")

    if not success:
        print(f"❌ {message}")
        sys.exit(1)
    else:
        print(f"✅ {message}")


if __name__ == "__main__":
    main()
