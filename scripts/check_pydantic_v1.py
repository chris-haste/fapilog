#!/usr/bin/env python3
"""
Check for deprecated Pydantic v1 syntax patterns.

This script scans Python files for Pydantic v1 patterns that should be
updated to Pydantic v2 syntax.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Patterns that indicate Pydantic v1 syntax
PYDANTIC_V1_PATTERNS = [
    # @validator decorator (should be @field_validator)
    (r"@validator\s*\(", "@validator decorator should be @field_validator"),
    # Config class inside model (should be model_config)
    (r"class Config:", "Config class should be replaced with model_config"),
    # use_enum_values = True (should be in model_config)
    (r"use_enum_values\s*=\s*True", "use_enum_values should be in model_config"),
    # validate_assignment = True (should be in model_config)
    (
        r"validate_assignment\s*=\s*True",
        "validate_assignment should be in model_config",
    ),
    # extra = "forbid" (should be in model_config)
    (r'extra\s*=\s*["\']forbid["\']', "extra should be in model_config"),
    # parse_obj (should be model_validate)
    (r"\.parse_obj\s*\(", ".parse_obj should be .model_validate"),
    # parse_raw (should be model_validate_json)
    (r"\.parse_raw\s*\(", ".parse_raw should be .model_validate_json"),
    # dict() method (should be model_dump)
    (r"\.dict\s*\(", ".dict() should be .model_dump()"),
    # json() method (should be model_dump_json)
    (r"\.json\s*\(", ".json() should be .model_dump_json()"),
    # Config class with old syntax
    (
        r"class Config:\s*\n\s*use_enum_values\s*=",
        "Config class should use model_config",
    ),
]


def check_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Check a single file for Pydantic v1 patterns."""
    issues: List[Tuple[int, str, str]] = []

    # Skip this check script itself to avoid false positives
    if file_path.name == "check_pydantic_v1.py":
        return issues

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            for pattern, message in PYDANTIC_V1_PATTERNS:
                if re.search(pattern, line):
                    issues.append((line_num, line.strip(), message))

    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)

    return issues


def check_directory(directory: Path) -> List[Tuple[Path, int, str, str]]:
    """Check all Python files in a directory for Pydantic v1 patterns."""
    all_issues: List[Tuple[Path, int, str, str]] = []

    for py_file in directory.rglob("*.py"):
        if py_file.name.startswith("."):
            continue
        # Skip virtual environment and other common non-project directories
        if any(
            part in [".venv", "venv", ".env", "__pycache__", ".git"]
            for part in py_file.parts
        ):
            continue

        issues = check_file(py_file)
        for line_num, line, message in issues:
            all_issues.append((py_file, line_num, line, message))

    return all_issues


def main() -> int:
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check for deprecated Pydantic v1 syntax patterns"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["src/", "tests/"],
        help="Paths to check (default: src/ tests/)",
    )

    args = parser.parse_args()

    all_issues: List[Tuple[Path, int, str, str]] = []

    for path_str in args.paths:
        path = Path(path_str)
        if path.exists():
            if path.is_file():
                file_issues = check_file(path)
                for line_num, line, message in file_issues:
                    all_issues.append((path, line_num, line, message))
            elif path.is_dir():
                dir_issues = check_directory(path)
                all_issues.extend(dir_issues)
        else:
            print(f"Warning: Path {path_str} does not exist", file=sys.stderr)

    if all_issues:
        print("❌ Pydantic v1 syntax patterns detected:")
        print()

        for file_path, line_num, line, message in all_issues:
            print(f"  {file_path}:{line_num}")
            print(f"    {line}")
            print(f"    → {message}")
            print()

        print("Please update to Pydantic v2 syntax:")
        print("  - @validator → @field_validator")
        print("  - class Config: → model_config = ConfigClass()")
        print("  - .parse_obj() → .model_validate()")
        print("  - .dict() → .model_dump()")
        print("  - .json() → .model_dump_json()")
        print("  - .copy() → .model_copy()")

        return 1
    else:
        print("✅ No Pydantic v1 syntax patterns detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
