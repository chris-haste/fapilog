#!/usr/bin/env python3
"""
Lint test files for weak assertion patterns.

Detects:
- WA001: assert x >= 0 (always true for unsigned values)
- WA002: assert x >= 1 (may be too weak if exact count is known)
- WA003: assert x is not None (without behavioral assertion)

Usage:
    python scripts/lint_test_assertions.py tests/
    python scripts/lint_test_assertions.py tests/unit/test_core_logger.py
    python scripts/lint_test_assertions.py tests/ --baseline .weak-assertion-baseline.txt
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Violation:
    """A weak assertion violation found in test code."""

    file: Path
    line: int
    code: str
    message: str
    suggestion: str


class WeakAssertionVisitor(ast.NodeVisitor):
    """AST visitor to detect weak assertion patterns."""

    def __init__(self, filepath: Path, source_lines: list[str]) -> None:
        self.filepath = filepath
        self.source_lines = source_lines
        self.violations: list[Violation] = []
        self._current_function: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = None

    def visit_Assert(self, node: ast.Assert) -> None:
        self._check_comparison(node)
        self._check_is_not_none(node)
        self.generic_visit(node)

    def _check_comparison(self, node: ast.Assert) -> None:
        """Check for >= 0 or >= 1 patterns."""
        test = node.test

        if not isinstance(test, ast.Compare):
            return

        # Check for x >= 0 or x >= 1
        if len(test.ops) == 1 and isinstance(test.ops[0], ast.GtE):
            if len(test.comparators) == 1:
                right = test.comparators[0]

                # Check for >= 0
                if isinstance(right, ast.Constant) and right.value == 0:
                    self._add_violation(
                        node,
                        "WA001",
                        "Assertion `>= 0` is always true for non-negative values",
                        "Use `== expected_value` with a computed expected value",
                    )

                # Check for >= 1
                elif isinstance(right, ast.Constant) and right.value == 1:
                    self._add_violation(
                        node,
                        "WA002",
                        "Assertion `>= 1` may be too weak if exact count is known",
                        "Consider `== expected_count` if the count is deterministic",
                    )

    def _check_is_not_none(self, node: ast.Assert) -> None:
        """Check for bare `is not None` assertions."""
        test = node.test

        if isinstance(test, ast.Compare):
            if len(test.ops) == 1 and isinstance(test.ops[0], ast.IsNot):
                if len(test.comparators) == 1:
                    right = test.comparators[0]
                    if isinstance(right, ast.Constant) and right.value is None:
                        self._add_violation(
                            node,
                            "WA003",
                            "Assertion `is not None` should be followed by behavioral check",
                            "Add assertion on the actual value (e.g., assert x.field == 'expected')",
                        )

    def _has_noqa(self, lineno: int, code: str) -> bool:
        """Check if line has a noqa comment suppressing this code."""
        if lineno < 1 or lineno > len(self.source_lines):
            return False
        line = self.source_lines[lineno - 1]
        # Check for # noqa: WA001 or # noqa (blanket)
        if "# noqa" in line:
            # Blanket noqa
            if "# noqa:" not in line and "# noqa " not in line:
                return True
            # Specific code suppression
            if f"# noqa: {code}" in line:
                return True
            # Check comma-separated codes like # noqa: WA001, WA002
            noqa_idx = line.find("# noqa:")
            if noqa_idx != -1:
                noqa_part = line[noqa_idx + 7 :].strip()
                codes = [c.strip() for c in noqa_part.split(",")]
                if code in codes:
                    return True
        return False

    def _add_violation(
        self, node: ast.Assert, code: str, message: str, suggestion: str
    ) -> None:
        # Check for suppression comment
        if self._has_noqa(node.lineno, code):
            return

        self.violations.append(
            Violation(
                file=self.filepath,
                line=node.lineno,
                code=code,
                message=message,
                suggestion=suggestion,
            )
        )


def lint_file(filepath: Path) -> list[Violation]:
    """Lint a single file for weak assertions."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        source_lines = source.splitlines()
    except SyntaxError:
        return []
    except Exception:
        return []

    visitor = WeakAssertionVisitor(filepath, source_lines)
    visitor.visit(tree)
    return visitor.violations


def lint_directory(directory: Path) -> list[Violation]:
    """Lint all test files in a directory."""
    violations = []

    for filepath in directory.rglob("test_*.py"):
        # Skip common non-project directories
        if any(
            part in [".venv", "venv", ".env", "__pycache__", ".git"]
            for part in filepath.parts
        ):
            continue
        violations.extend(lint_file(filepath))

    return violations


def load_baseline(baseline_path: Path) -> set[str]:
    """Load baseline violations from file.

    Returns a set of "file:line" strings that are baselined.
    """
    if not baseline_path.exists():
        return set()

    baselined = set()
    for line in baseline_path.read_text().splitlines():
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        # Extract file:line from entry (ignore trailing comment)
        if "#" in line:
            line = line.split("#")[0].strip()
        if ":" in line:
            baselined.add(line)
    return baselined


def format_baseline_key(violation: Violation) -> str:
    """Format a violation as a baseline key (file:line)."""
    return f"{violation.file}:{violation.line}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lint test files for weak assertion patterns"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["tests/"],
        help="Paths to check (default: tests/)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Baseline file with known violations to exclude",
    )
    parser.add_argument(
        "--generate-baseline",
        action="store_true",
        help="Generate baseline file to stdout",
    )
    parser.add_argument(
        "--show-fixed",
        action="store_true",
        help="Show violations that have been fixed (in baseline but not found)",
    )

    args = parser.parse_args()

    # Collect all violations
    all_violations: list[Violation] = []

    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Error: {path} does not exist", file=sys.stderr)
            return 1

        if path.is_file():
            all_violations.extend(lint_file(path))
        elif path.is_dir():
            all_violations.extend(lint_directory(path))

    # Sort violations by file and line
    all_violations.sort(key=lambda v: (str(v.file), v.line))

    # Generate baseline mode
    if args.generate_baseline:
        print("# Weak assertion baseline - track cleanup progress")
        print(
            "# Generated by: python scripts/lint_test_assertions.py --generate-baseline"
        )  # noqa: E501
        print(f"# Total: {len(all_violations)} violations")
        print("#")
        print("# Codes:")
        print("#   WA001: assert x >= 0 (always true)")
        print("#   WA002: assert x >= 1 (may be too weak)")
        print("#   WA003: assert x is not None (standalone)")
        print()

        for v in all_violations:
            print(f"{v.file}:{v.line}  # {v.code}")

        return 0

    # Load baseline if provided
    baselined: set[str] = set()
    if args.baseline:
        baselined = load_baseline(args.baseline)

    # Filter out baselined violations
    new_violations = [
        v for v in all_violations if format_baseline_key(v) not in baselined
    ]

    # Check for fixed violations (in baseline but not found)
    found_keys = {format_baseline_key(v) for v in all_violations}
    fixed_violations = baselined - found_keys

    # Report results
    if args.show_fixed and fixed_violations:
        print(
            f"Fixed violations (can be removed from baseline): {len(fixed_violations)}"
        )
        for key in sorted(fixed_violations):
            print(f"  {key}")
        print()

    if not new_violations:
        if args.baseline:
            print(f"No new weak assertions found (baseline: {len(baselined)} known)")
        else:
            print("No weak assertions found")
        return 0

    print(f"Found {len(new_violations)} weak assertion(s):\n")

    for v in new_violations:
        print(f"{v.file}:{v.line}: [{v.code}] {v.message}")
        print(f"  Suggestion: {v.suggestion}")
        print()

    if args.baseline:
        print(f"(Baseline has {len(baselined)} known violations)")
    print("To suppress a specific violation, add `# noqa: WA00X` to the line")

    return 1


if __name__ == "__main__":
    sys.exit(main())
